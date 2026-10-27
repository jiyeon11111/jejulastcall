"""제주 라스트콜 핵심 계산.

질문 하나에 답하는 엔진이다: "지금 이 코스로 움직여도 비행기 시간에 맞춰 공항에 도착할 수 있는가?"

1. 선택한 반납 지점, 반납 처리·셔틀 시간과 공항 목표를 함께 계산한다.
2. 장소 순서와 실제 체류시간을 시뮬레이션한다.
3. 두 마감에 안전 버퍼 + 추가 여유를 남기는 코스만 자동 추천한다.
4. 장소 적합도, 유효 체류시간, 다양성과 이동 부담으로 코스를 비교한다.
5. 영업시간·체류 상한 때문에 남는 시간은 그대로 표시한다.
"""

from __future__ import annotations

import math
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from itertools import permutations

from . import config
from .models import (
    Alternative,
    Badge,
    CheckRequest,
    CheckResponse,
    Checkpoint,
    HourValue,
    PlaceBrief,
    PlaceDetail,
    PlanRequest,
    PlanResponse,
    Reachable,
    TimelineItem,
    TripInput,
)
from .repository import Place, Repository, load, DATA_DIR
from .timeutil import current_minutes, duration_text, fmt, is_weekday_today, parse
from .translate import (
    CATEGORY_LABEL,
    congestion_level,
    status_headline,
    stop_badges,
    stop_reason,
)
from .travel import provider


class PlanError(ValueError):
    """사용자 입력으로는 계산할 수 없는 상황 (422로 응답)"""


# ── 컨텍스트 ────────────────────────────────────────────


@dataclass
class Context:
    repo: Repository
    now: int
    flight: int
    weekday: bool
    transport: str
    rental: bool
    rental_return: int | None
    origin: tuple[float, float]
    origin_name: str
    airport_target: int
    checkin_close: int
    mode: str = "tour"
    day_of_week: int = 0
    meal_preference: str = "auto"
    selected_hub: dict | None = None
    rental_process_min: int = 15
    rental_shuttle_min: int = 10

    @property
    def airport(self) -> tuple[float, float]:
        return (self.repo.airport.lat, self.repo.airport.lng)

    @property
    def hub(self) -> tuple[float, float]:
        if not self.selected_hub:
            raise PlanError('렌터카 반납 지점이 선택되지 않았어요')
        return (self.selected_hub['lat'], self.selected_hub['lng'])


def build_context(req: TripInput, mode: str = "tour") -> Context:
    repo = load()
    now = parse(req.now) if req.now else current_minutes()
    flight = parse(req.flight_time)
    if flight <= now:
        raise PlanError("비행기 출발 시간이 이미 지났어요. 시간을 다시 확인해 주세요.")

    rental_return = None
    if req.rental:
        rental_return = parse(req.rental_return_time or "")
        if rental_return <= now:
            raise PlanError("렌터카 반납 시간이 이미 지났어요.")
        if rental_return > flight:
            raise PlanError("렌터카 반납 시간이 비행기 출발보다 늦어요.")

    if req.origin_area:
        area = repo.areas.get(req.origin_area)
        if not area:
            raise PlanError(f"알 수 없는 지역이에요: {req.origin_area}")
        origin, origin_name = (area.lat, area.lng), area.name
    else:
        origin, origin_name = (req.origin_lat, req.origin_lng), "현재 위치"  # type: ignore[assignment]

    before = (
        config.AIRPORT_ARRIVE_BEFORE_MIN_WITH_BAGGAGE
        if req.has_baggage
        else config.AIRPORT_ARRIVE_BEFORE_MIN_NO_BAGGAGE
    )
    airport_target = parse(req.airport_arrival_time) if req.airport_arrival_time else flight - before
    if (req.airport_arrival_time and airport_target <= now) or airport_target > flight - config.CHECKIN_CLOSE_BEFORE_MIN:
        raise PlanError('공항 도착 목표는 현재 이후, 설정된 수속 마감 이전이어야 해요')
    hubs = json.loads((DATA_DIR / 'rental_hubs.json').read_text(encoding='utf-8')) if req.rental else []
    selected_hub = next((h for h in hubs if h['id'] == req.rental_hub_id), None)
    if req.rental and selected_hub is None:
        raise PlanError('선택한 렌터카 지점을 찾을 수 없어요')
    day = req.day_of_week if req.day_of_week is not None else datetime.now(ZoneInfo('Asia/Seoul')).weekday()
    if req.day_of_week is None and req.weekday is not None and (day < 5) != req.weekday:
        day = 0 if req.weekday else 5
    return Context(
        repo=repo,
        now=now,
        flight=flight,
        weekday=day < 5,
        transport="car" if req.rental else (req.transport or "taxi"),
        rental=req.rental,
        rental_return=rental_return,
        origin=origin,  # type: ignore[arg-type]
        origin_name=origin_name,
        airport_target=airport_target,
        checkin_close=flight - config.CHECKIN_CLOSE_BEFORE_MIN,
        mode=mode,
        meal_preference=getattr(req, "meal_preference", "auto"),
        day_of_week=day,
        selected_hub=selected_hub,
        rental_process_min=req.rental_process_min,
        rental_shuttle_min=req.rental_shuttle_min,
    )


# ── 마지막 구간 (차고지/공항) ───────────────────────────


@dataclass
class Finish:
    depart: int
    travel: int
    hub_arrive: int | None
    airport_eta: int
    margin: int
    buffer: int
    checkpoints: list[Checkpoint]

    @property
    def ok(self) -> bool:
        return self.margin >= self.buffer


def finish(ctx: Context, pos: tuple[float, float], depart: int) -> Finish:
    if ctx.rental:
        travel = provider.minutes(pos, ctx.hub, depart, "car")
        hub_arrive = depart + travel
        airport_eta = hub_arrive + ctx.rental_process_min + ctx.rental_shuttle_min
        m_rental = ctx.rental_return - hub_arrive  # type: ignore[operator]
        m_airport = ctx.airport_target - airport_eta
        checkpoints = [
            Checkpoint(label="렌터카 반납 마감", time=fmt(ctx.rental_return), eta=fmt(hub_arrive), margin_min=m_rental),
            Checkpoint(label="공항 도착 목표(이 시각까지)", time=fmt(ctx.airport_target), eta=fmt(airport_eta), margin_min=m_airport),
        ]
        margin = min(m_rental, m_airport)
    else:
        travel = provider.minutes(pos, ctx.airport, depart, ctx.transport)
        hub_arrive = None
        airport_eta = depart + travel
        margin = ctx.airport_target - airport_eta
        checkpoints = [
            Checkpoint(label="공항 도착 목표(이 시각까지)", time=fmt(ctx.airport_target), eta=fmt(airport_eta), margin_min=margin)
        ]
    buffer = max(config.SAFETY_BUFFER_MIN, math.ceil(travel * config.SAFETY_BUFFER_RATIO))
    return Finish(depart, travel, hub_arrive, airport_eta, margin, buffer, checkpoints)


def status_of(margin: int, buffer: int) -> str:
    if margin < buffer:
        return "late"
    if margin < buffer + config.COMFORT_EXTRA_MIN:
        return "tight"
    return "safe"


def latest_departure(ctx: Context, pos: tuple[float, float], earliest: int) -> int | None:
    """pos에서 늦어도 몇 시에 출발하면 되는지 (안전 버퍼 포함). 불가능하면 None."""
    if not finish(ctx, pos, earliest).ok:
        return None
    lo, hi = earliest, ctx.flight
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if finish(ctx, pos, mid).ok:
            lo = mid
        else:
            hi = mid - 1
    return lo


# ── 코스 시뮬레이션 ─────────────────────────────────────


@dataclass
class Visit:
    place: Place
    travel_in: int
    arrive: int
    leave: int

    @property
    def stay(self) -> int:
        return self.leave - self.arrive


@dataclass
class Schedule:
    visits: list[Visit]
    fin: Finish
    start: int = 0

    @property
    def total_travel(self) -> int:
        return sum(v.travel_in for v in self.visits) + self.fin.travel


def _pos(p: Place) -> tuple[float, float]:
    return (p.lat, p.lng)


def simulate(
    ctx: Context,
    seq: list[Place],
    stays: list[int] | None = None,
    start: int | None = None,
    start_pos: tuple[float, float] | None = None,
) -> Schedule | None:
    t = ctx.now if start is None else start
    pos = ctx.origin if start_pos is None else start_pos
    visits: list[Visit] = []
    for i, p in enumerate(seq):
        if not p.enabled or ctx.day_of_week in p.closed_weekdays:
            return None
        travel = provider.minutes(pos, _pos(p), t, ctx.transport)
        arrive = t + travel
        opens, closes = map(parse, p.hours(ctx.weekday, ctx.day_of_week))
        if arrive < opens:
            if opens - arrive > 20:  # 20분 넘게 기다려야 하면 제외
                return None
            arrive = opens
        stay = stays[i] if stays else p.stay_min
        for begins, ends in p.break_times:
            left, right = parse(begins), parse(ends)
            if left <= arrive < right:
                if right - arrive > 20:
                    return None
                arrive = right
            if arrive < left and arrive + stay > left:
                return None
        last_entry = p.day_last_entry.get(str(ctx.day_of_week), p.last_entry)
        if any(parse(left) < arrive < parse(right) for left, right in p.order_closed_windows):
            return None
        if last_entry and arrive > parse(last_entry):
            return None
        if arrive + stay > closes:
            return None
        visits.append(Visit(p, travel, arrive, arrive + stay))
        t, pos = arrive + stay, _pos(p)
    return Schedule(visits, finish(ctx, pos, t), ctx.now if start is None else start)


# ── 점수 ────────────────────────────────────────────────

SIGHTS = {"beach", "oreum", "walk", "forest", "heritage"}

MODE_CATEGORIES = {
    "tour": {"beach", "oreum", "walk", "forest", "heritage", "museum", "restaurant", "cafe"},
    "work": {"cafe", "restaurant", "walk", "beach", "forest", "heritage", "oreum"},
    "rest": {"walk", "forest", "beach", "heritage", "oreum", "cafe"},
}


def place_score(p: Place, mode: str, hour: int, weekday: bool) -> float:
    spend, seasonal, fit_weight, _ = config.MODE_WEIGHTS[mode]
    # Region context remains labelled as regional, never store conversion.
    score = (spend * p.region_spend_index if p.region_spend_index is not None else 0)
    score += seasonal * p.region_low_concentration if p.region_low_concentration is not None else 0
    if mode == 'work':
        fit = {'상': 1.0, '중': 0.5, '하': 0.0}.get(p.work_grade, 0.0)
    else:
        fit = p.suitability if p.suitability is not None else 0.0
    return score + fit_weight * fit


def _prefix_ok(seq: tuple[Place, ...]) -> bool:
    """_valid_sequence 규칙 중 뒤에 장소를 더 붙여도 다시 성립할 수 없는 것만 검사."""
    cats = [p.category for p in seq]
    if cats.count("restaurant") > 1 or cats.count("cafe") > 1:
        return False
    groups = ["coast" if c in {"beach", "walk"} else "nature" if c in {"oreum", "forest"} else c for c in cats]
    if len(set(groups)) != len(groups):
        return False
    return not any(a in SIGHTS and b in SIGHTS for a, b in zip(cats, cats[1:]))


def _valid_sequence(seq: tuple[Place, ...], mode: str) -> bool:
    cats = [p.category for p in seq]
    if cats.count("restaurant") > 1:
        return False
    if mode == "work" and not any(p.category == "cafe" and p.work_grade == '상' for p in seq):
        return False
    if cats.count("cafe") > 1:
        return False
    # A beach and a coastal walk are the same experience, despite different labels.
    groups = ["coast" if c in {"beach", "walk"} else "nature" if c in {"oreum", "forest"} else c for c in cats]
    if len(set(groups)) != len(groups):
        return False
    if any(a in SIGHTS and b in SIGHTS for a, b in zip(cats, cats[1:])):
        return False
    return True


def _in_meal_window(t: int) -> bool:
    return 11 * 60 <= t <= 14 * 60 or 17 * 60 <= t <= 19 * 60 + 30


def _score_upper_bound(ctx: Context, s: Schedule) -> float:
    """extend_stays 뒤 course_score가 넘을 수 없는 상한 (탐색 가지치기용, 넉넉하게 잡음)."""
    slack = s.fin.margin - s.fin.buffer - config.COMFORT_EXTRA_MIN + 30
    weights, score = [], 0.0
    for v in s.visits:
        fit = place_score(v.place, ctx.mode, v.arrive // 60, ctx.weekday)
        w = (0.5 + fit) * (1.5 if ctx.mode == "work" and v.place.category == "cafe" else 1.0) / 60
        score += w * v.stay
        room = v.place.stay_max - v.stay
        if config.STRETCH_LAST_CAFE and v is s.visits[-1] and v.place.category == "cafe":
            room = slack
        weights.append((w, max(0, room)))
    for w, room in sorted(weights, reverse=True):
        if w <= 0 or slack <= 0:
            break
        add = min(room, slack)
        score += w * add
        slack -= add
    score += 0.15 * len({v.place.category for v in s.visits})
    score -= 0.15 * len(s.visits)
    score -= config.TRAVEL_PENALTY[ctx.mode] * (s.total_travel / max(config.PEAK_HOURS.values(), default=1.0) - len(s.visits) - 1)
    if any(v.place.category == "restaurant" for v in s.visits):
        score += 100.0 if ctx.meal_preference == "include" else 1.5
    return score + 1e-6


def course_score(ctx: Context, s: Schedule) -> float:
    # Reward useful time at suitable places, never driving or waiting to fill time.
    score = 0.0
    for v in s.visits:
        fit = place_score(v.place, ctx.mode, v.arrive // 60, ctx.weekday)
        focus = 1.5 if ctx.mode == "work" and v.place.category == "cafe" else 1.0
        score += (0.5 + fit) * focus * v.stay / 60
    score += 0.15 * len({v.place.category for v in s.visits})
    score -= 0.15 * len(s.visits)
    score -= config.TRAVEL_PENALTY[ctx.mode] * s.total_travel
    meal = next((v for v in s.visits if v.place.category == "restaurant"), None)
    if meal and (ctx.meal_preference == "include" or _in_meal_window(meal.arrive)):
        score += 100.0 if ctx.meal_preference == "include" else 1.5
    return score


def candidates(ctx: Context, free: int, exclude: set[str]) -> list[Place]:
    allowed = MODE_CATEGORIES[ctx.mode] | ({"restaurant"} if ctx.meal_preference == "include" else set())
    out = []
    for p in ctx.repo.places.values():
        if ctx.day_of_week in p.closed_weekdays:
            continue
        if p.category == "restaurant" and ctx.meal_preference == "skip":
            continue
        if p.id in exclude or p.category not in allowed:
            continue
        if p.zone == "expansion" and free < config.EXPANSION_FREE_MIN:
            continue
        if ctx.mode == "work" and p.category == "cafe" and p.work_grade != '상':
            continue
        opening, closing = p.hours(ctx.weekday, ctx.day_of_week)
        if parse(closing) <= ctx.now or parse(opening) >= ctx.airport_target:
            continue
        out.append(p)
    return out


def _shortlist(ctx: Context, pool: list[Place]) -> list[Place]:
    """카테고리마다 상위 2곳씩 + 전체 상위 4곳 (탐색량을 줄이면서 다양성 유지)"""
    if len(pool) <= 16:
        return sorted(pool, key=lambda p: p.id)
    hour = (ctx.now + 30) // 60
    ranked = sorted(pool, key=lambda p: place_score(p, ctx.mode, hour, ctx.weekday), reverse=True)
    picked = ranked[:4]
    # Keep several meal candidates (not just two) so researched restaurants stay
    # reachable, but cap them: with 19 restaurants the permutation search took
    # 12~18s per request. Ranked by score, then by distance from the origin.
    meals = sorted((p for p in ranked if p.category == "restaurant"),
                   key=lambda p: (-place_score(p, ctx.mode, hour, ctx.weekday),
                                  (p.lat - ctx.origin[0]) ** 2 + (p.lng - ctx.origin[1]) ** 2))
    near = sorted(meals, key=lambda p: (p.lat - ctx.origin[0]) ** 2 + (p.lng - ctx.origin[1]) ** 2)
    for p in meals[:3] + near[:2]:
        if p not in picked:
            picked.append(p)
    for cat in sorted({p.category for p in ranked}):
        for p in [x for x in ranked if x.category == cat][:2]:
            if p not in picked:
                picked.append(p)
    return picked


# ── 남는 시간 채우기 ────────────────────────────────────


def extend_stays(ctx: Context, seq: list[Place], s: Schedule) -> Schedule:
    stays = [v.stay for v in s.visits]
    order = sorted(
        range(len(seq)),
        key=lambda i: (not seq[i].station, seq[i].category != "cafe", -i),
    )
    while True:
        improved = False
        for i in order:
            if stays[i] + 10 > seq[i].stay_max:
                continue
            trial = stays.copy()
            trial[i] += 10
            t = simulate(ctx, seq, trial, start=s.start)
            if t and t.fin.margin >= t.fin.buffer + config.COMFORT_EXTRA_MIN:
                stays, s, improved = trial, t, True
                break
        if not improved:
            break
    # 마지막이 카페면 '거점에서 쉬다 가기': 상한 없이 마감 직전까지 늘린다
    last = len(seq) - 1
    if config.STRETCH_LAST_CAFE and seq and seq[last].category == "cafe":
        step = 30
        while step >= 5:
            trial = stays.copy()
            trial[last] += step
            t = simulate(ctx, seq, trial, start=s.start)
            if t and t.fin.margin >= t.fin.buffer + config.COMFORT_EXTRA_MIN:
                stays, s = trial, t
            else:
                step //= 2
    return s


def leave_by(ctx: Context, s: Schedule, index: int) -> int:
    """index번째 장소에서 늦어도 언제 떠나야 뒤 일정을 지킬 수 있는지"""
    v = s.visits[index]
    rest = [x.place for x in s.visits[index + 1 :]]
    stays = [x.stay for x in s.visits[index + 1 :]]
    limit = parse(v.place.hours(ctx.weekday, ctx.day_of_week)[1])
    for begins, _ in v.place.break_times:
        if parse(begins) >= v.leave:
            limit = min(limit, parse(begins))

    def ok(t: int) -> bool:
        r = simulate(ctx, rest, stays, start=t, start_pos=_pos(v.place))
        return bool(r and r.fin.ok)

    lo, hi = v.leave, min(limit, ctx.flight)
    if not ok(lo):
        return lo
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if ok(mid):
            lo = mid
        else:
            hi = mid - 1
    return lo


# ── 응답 조립 ───────────────────────────────────────────


def brief(p: Place) -> PlaceBrief:
    return PlaceBrief(
        id=p.id,
        name=p.name,
        region=p.region,
        category=p.category,
        category_label=CATEGORY_LABEL.get(p.category, p.category),
        lat=p.lat,
        lng=p.lng,
        station=p.station,
        verified=p.verified,
        source=p.source,
        kakao_reviews=p.kakao_reviews,
    )


def _to_airport(ctx: Context, p: Place, depart: int) -> int:
    return provider.minutes(_pos(p), ctx.airport, depart, "car" if ctx.transport == "car" else ctx.transport)


def build_timeline(ctx: Context, s: Schedule | None, direct: Finish) -> list[TimelineItem]:
    start_time = s.start if s else ctx.now
    items = [TimelineItem(type="start", time=fmt(start_time), title=f"{ctx.origin_name}에서 출발", subtitle="현재 위치 · 출발 전 여유시간 활용" if start_time > ctx.now else "현재 위치")]
    fin = s.fin if s else direct
    for i, v in enumerate(s.visits if s else []):
        cong = v.place.congestion(v.arrive // 60, ctx.weekday)
        to_air = _to_airport(ctx, v.place, v.leave)
        lb = leave_by(ctx, s, i)  # type: ignore[arg-type]
        items.append(TimelineItem(type="move", title=f"{v.place.name}까지", minutes=v.travel_in, transport=ctx.transport))  # type: ignore[arg-type]
        items.append(
            TimelineItem(
                type="stop",
                time=fmt(v.arrive),
                end_time=fmt(v.leave),
                title=v.place.name,
                subtitle=f"{CATEGORY_LABEL.get(v.place.category, '')} · {duration_text(v.stay)} 머물기",
                stop_index=i,
                place=brief(v.place),
                badges=[Badge(**b) for b in stop_badges(v.place, cong, to_air, lb, ctx.mode)],
                reason=(
                    "식사시간에 맞춰 한 끼를 먹는 구간이에요. 대기·주문 마감은 방문 전 확인해 주세요." if v.place.category == "restaurant" else
                    "관람과 정원을 둘러보는 구간이에요. 유료 입장과 운영시간을 확인해 주세요." if v.place.category == "museum" else
                    "이동 사이에 앉아서 쉬는 시간이에요." if v.place.category == "cafe" else
                    "풍경을 즐기며 가볍게 걷는 구간이에요. 비슷한 산책은 중복해서 넣지 않았어요." if v.place.category in {"beach", "walk"} else
                    stop_reason(v.place, cong, v.arrive, to_air, ctx.mode)
                ),
                leave_by=fmt(lb),
            )
        )
    if ctx.rental:
        items.append(TimelineItem(type="move", title=ctx.selected_hub['name'] + ' 반납 지점까지', minutes=fin.travel, transport="car"))
        items.append(
            TimelineItem(
                type="rental",
                time=fmt(fin.hub_arrive or 0),
                end_time=fmt((fin.hub_arrive or 0) + ctx.rental_process_min),
                title='렌터카 반납 · ' + ctx.selected_hub['name'],
                subtitle=f"반납 마감 {fmt(ctx.rental_return or 0)} · 검차 {ctx.rental_process_min}분(입력값) · {ctx.selected_hub['address']}",
            )
        )
        items.append(TimelineItem(type="move", title="공항 셔틀(입력 소요시간)", minutes=ctx.rental_shuttle_min))
    else:
        items.append(TimelineItem(type="move", title="제주공항까지", minutes=fin.travel, transport=ctx.transport))  # type: ignore[arg-type]
    items.append(
        TimelineItem(
            type="airport",
            time=fmt(fin.airport_eta),
            title="제주공항 도착",
            subtitle=f"도착 목표 {fmt(ctx.airport_target)}까지 · 수속 마감 기준 {fmt(ctx.checkin_close)}",
        )
    )
    return items


def _alternatives(ctx: Context, s: Schedule, pool: list[Place]) -> dict[int, list[Alternative]]:
    seq = [v.place for v in s.visits]
    out: dict[int, list[Alternative]] = {}
    for i in range(len(seq)):
        found: list[tuple[float, Schedule, Place]] = []
        for c in pool:
            if c in seq:
                continue
            trial = seq.copy()
            trial[i] = c
            if not _valid_sequence(tuple(trial), ctx.mode):
                continue
            base = simulate(ctx, trial, start=s.start)
            if not base or base.fin.margin < base.fin.buffer + config.COMFORT_EXTRA_MIN:
                continue
            full = extend_stays(ctx, trial, base)
            found.append((course_score(ctx, full), full, c))
        found.sort(key=lambda x: x[0], reverse=True)
        alts = []
        for _, full, c in found[:3]:
            v = full.visits[i]
            cong = c.congestion(v.arrive // 60, ctx.weekday)
            badges = stop_badges(c, cong, _to_airport(ctx, c, v.leave), None, ctx.mode)
            alts.append(
                Alternative(
                    place=brief(c),
                    margin_min=full.fin.margin,
                    margin_delta=full.fin.margin - s.fin.margin,
                    badges=[Badge(**b) for b in badges[:3]],
                )
            )
        out[i] = alts
    return out


def _reachable(ctx: Context, pool: list[Place]) -> list[Reachable]:
    out: list[tuple[float, Reachable]] = []
    for p in pool:
        if not _valid_sequence((p,), ctx.mode):
            continue
        single = simulate(ctx, [p])
        if not single or single.fin.margin < single.fin.buffer + config.COMFORT_EXTRA_MIN:
            continue
        travel = provider.minutes(ctx.origin, _pos(p), ctx.now, ctx.transport)
        arrive = single.visits[0].arrive
        lb = latest_departure(ctx, _pos(p), arrive)
        if lb is None:
            continue
        lb = min(lb, parse(p.hours(ctx.weekday, ctx.day_of_week)[1]))
        for begins, _ in p.break_times:
            if parse(begins) > arrive:
                lb = min(lb, parse(begins))
        max_stay = min(lb - arrive, p.stay_max)
        if max_stay < p.stay_min:
            continue
        cong = p.congestion(arrive // 60, ctx.weekday)
        badges = stop_badges(p, cong, _to_airport(ctx, p, lb), None, ctx.mode)
        out.append(
            (
                place_score(p, ctx.mode, arrive // 60, ctx.weekday),
                Reachable(
                    place=brief(p),
                    travel_min=travel,
                    arrive=fmt(arrive),
                    max_stay_min=max_stay,
                    leave_by=fmt(lb),
                    badges=[Badge(**b) for b in badges[:3]],
                ),
            )
        )
    out.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in out]


def plan(req: PlanRequest) -> PlanResponse:
    ctx = build_context(req, req.mode)
    direct = finish(ctx, ctx.origin, ctx.now)
    free = max(0, direct.margin - direct.buffer)
    exclude = set(req.exclude)
    pool = candidates(ctx, free, exclude)

    best: Schedule | None = None
    if req.sequence is not None:
        allowed_ids = {p.id for p in pool}
        if len(set(req.sequence)) != len(req.sequence) or any(i not in allowed_ids for i in req.sequence):
            raise PlanError('선택한 장소가 휴무이거나 현재 조건에서 추천할 수 없어요.')
        seq = [ctx.repo.places[i] for i in req.sequence]
        if seq and not _valid_sequence(tuple(seq), ctx.mode):
            raise PlanError('이 모드에서 이용할 수 없는 장소 조합이에요.')
        base = simulate(ctx, seq) if seq else None
        if seq and base is None and req.departure_strategy == 'later':
            # A replacement may open later than the original restaurant.
            # Find a feasible departure before applying the latest-start scan.
            for start in range(ctx.now + 1, ctx.airport_target + 1):
                trial = simulate(ctx, seq, start=start)
                if trial and trial.fin.margin >= trial.fin.buffer + config.COMFORT_EXTRA_MIN:
                    base = trial
                    break
        if seq and base is None:
            raise PlanError("영업시간 때문에 이 순서로는 갈 수 없어요.")
        if base is not None:
            best = extend_stays(ctx, seq, base) if base.fin.ok else base
    elif direct.ok:
        short = _shortlist(ctx, pool)
        best_score = -math.inf
        max_stops = config.MAX_STOPS[ctx.mode] + (1 if free >= config.EXTRA_STOP_FREE_MIN else 0)  # 10/27: 휴식·일도 여유 5시간 이상이면 한 곳 더
        # 1) 가능한 코스를 기본 체류로 먼저 계산하고, 체류를 최대로 늘렸을 때의 점수 상한을 구한다.
        # 2) 상한이 높은 코스부터 체류 늘리기(extend_stays, 시간의 대부분)를 하고,
        #    남은 코스의 상한이 현재 최고점보다 낮아지면 멈춘다. 결과는 전수 탐색과 같다.
        # 앞부분이 이미 영업시간상 불가능(simulate None)이거나 중복 규칙에 걸리면
        # 뒤에 장소를 붙여도 마찬가지라 그 가지는 통째로 건너뛴다.
        feasible = []

        def grow(prefix: tuple[int, ...]) -> None:
            for i in range(len(short)):
                if i in prefix:
                    continue
                ids = prefix + (i,)
                combo = tuple(short[j] for j in ids)
                if not _prefix_ok(combo):
                    continue
                s = simulate(ctx, list(combo))
                if s is None:
                    continue
                if _valid_sequence(combo, ctx.mode) and s.fin.margin >= s.fin.buffer + config.COMFORT_EXTRA_MIN:
                    feasible.append((_score_upper_bound(ctx, s), (len(ids), ids), combo, s))
                if len(ids) < max_stops:
                    grow(ids)

        grow(())
        # 점수가 같으면 전수 탐색 때처럼 먼저 나온 순서(idx)를 고른다
        feasible.sort(key=lambda x: (-x[0], x[1]))
        best_idx = (99,)
        for bound, idx, combo, s in feasible:
            if bound < best_score:
                break
            s = extend_stays(ctx, list(combo), s)
            meals = [v for v in s.visits if v.place.category == "restaurant"]
            if ctx.meal_preference == "auto" and any(not _in_meal_window(v.arrive) for v in meals):
                continue
            sc = course_score(ctx, s)
            if sc > best_score or (sc == best_score and idx < best_idx):
                best, best_score, best_idx = s, sc, idx

    if best and best.fin.ok and req.departure_strategy == 'later':
        seq = [v.place for v in best.visits]
        stays = [v.stay for v in best.visits]
        # Scan backwards: opening and rush-hour boundaries are not monotonic.
        # Wait at the origin; never exceed a venue's stay limit to fill time.
        for start in range(ctx.airport_target, ctx.now - 1, -1):
            shifted = simulate(ctx, seq, stays, start=start)
            if shifted and shifted.fin.margin >= shifted.fin.buffer + config.COMFORT_EXTRA_MIN:
                best = shifted
                break
    fin = best.fin if best else direct
    status = status_of(fin.margin, fin.buffer)
    if best and best.visits:
        headline = status_headline(status, fin.airport_eta, fin.margin, "")
    elif direct.ok:
        headline = "지금은 코스보다 공항 쪽으로 이동하는 게 좋아요"
    else:
        headline = "지금 바로 공항으로 가야 해요"

    if status == "late" and fin.airport_eta > ctx.checkin_close:
        subline = f"지금 출발해도 탑승수속 마감({fmt(ctx.checkin_close)}) 뒤에 도착해요." + (
            " 택시로 바꾸면 더 빨라요." if ctx.transport == "bus" else " 항공사에 바로 연락해 보세요."
        )
    elif status == "late" and fin.margin < 0:
        subline = f"지금 출발해도 권장 도착시간보다 {-fin.margin}분 늦어요. 탑승수속은 {fmt(ctx.checkin_close)}에 마감돼요."
    elif status == "late":
        subline = f"차가 막히면 늦을 수 있어요. 탑승수속은 {fmt(ctx.checkin_close)}에 마감돼요."
    elif ctx.rental:
        subline = f"렌터카 {fmt(ctx.rental_return or 0)} 반납, 비행기 {fmt(ctx.flight)} 출발 기준이에요."
    else:
        subline = f"비행기 {fmt(ctx.flight)} 출발, 공항엔 {fmt(ctx.airport_target)}까지 도착하면 돼요."

    unfilled = max(0, fin.margin - fin.buffer - config.COMFORT_EXTRA_MIN) if best else 0
    notes = []
    if best and unfilled >= 60:
        notes.append(f"안전 여유 외에 {duration_text(unfilled)}이 더 남아요. 현재 후보와 영업시간·체류 상한으로는 목표시각에 가까운 코스를 구성하지 못했어요.")
    if req.meal_preference == "include" and (not best or not any(v.place.category == "restaurant" for v in best.visits)):
        notes.append("현재 조건에 맞는 식사 장소를 넣지 못했어요. 식사 포함 요청이 충족되지 않은 코스예요.")
    if best and any(v.place.category == "museum" for v in best.visits):
        notes.append("미술관은 유료 관람이며 야외 정원이 포함돼요. 입장료와 당일 운영 여부를 확인해 주세요.")
    return PlanResponse(
        meal_preference=req.meal_preference,
        unfilled_min=unfilled,
        planning_notes=notes,
        now=fmt(ctx.now),
        departure_time=fmt(best.start if best else ctx.now),
        departure_strategy=req.departure_strategy,
        wait_before_departure_min=(best.start - ctx.now) if best else 0,
        rental_hub=ctx.selected_hub,
        mode=ctx.mode,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        headline=headline,
        subline=subline,
        margin_min=fin.margin,
        buffer_min=fin.buffer,
        free_min=free,
        expansion=free >= config.EXPANSION_FREE_MIN,
        airport_eta=fmt(fin.airport_eta),
        checkpoints=fin.checkpoints,
        direct_travel_min=direct.travel,
        timeline=build_timeline(ctx, best, direct),
        stop_ids=[v.place.id for v in best.visits] if best else [],
        alternatives=_alternatives(ctx, best, pool) if best and best.fin.ok else {},
        reachable=_reachable(ctx, pool) if direct.ok else [],
        data_source="analysis" if any(p.metrics_source == "analysis" for p in ctx.repo.places.values()) else "sample",
    )


def check(req: CheckRequest) -> CheckResponse:
    ctx = build_context(req)
    pos = ctx.origin
    if req.place_id:
        p = ctx.repo.places.get(req.place_id)
        if not p:
            raise PlanError(f"알 수 없는 장소예요: {req.place_id}")
        pos = _pos(p)
    fin = finish(ctx, pos, ctx.now)
    lb = latest_departure(ctx, pos, ctx.now)
    status = status_of(fin.margin, fin.buffer)
    if lb is None:
        message = f"지금 바로 출발해도 {fmt(fin.airport_eta)} 도착이에요. 바로 이동하세요."
    else:
        message = f"늦어도 {fmt(lb)}에는 출발하세요."
    return CheckResponse(
        now=fmt(ctx.now),
        status=status,  # type: ignore[arg-type]
        message=message,
        travel_min=fin.travel,
        airport_eta=fmt(fin.airport_eta),
        margin_min=fin.margin,
        latest_departure=fmt(lb if lb is not None else ctx.now),
        free_min=max(0, (lb or ctx.now) - ctx.now),
        checkpoints=fin.checkpoints,
    )


def place_detail(place_id: str, hour: int | None, weekday: bool | None, transport: str = "car") -> PlaceDetail:
    repo = load()
    p = repo.places.get(place_id)
    if not p:
        raise PlanError(f"알 수 없는 장소예요: {place_id}")
    wk = is_weekday_today() if weekday is None else weekday
    h = hour if hour is not None else current_minutes() // 60
    opening, closing = p.hours(wk)
    opens, closes = parse(opening) // 60, max(parse(opening) // 60, (parse(closing) - 1) // 60)
    hours = [x for x in range(9, 21) if opens <= x <= closes] or list(range(9, 21))
    hourly = [HourValue(hour=x, value=p.congestion(x, wk), level=congestion_level(p.congestion(x, wk))) for x in hours if p.congestion(x, wk) is not None]
    best_hours = [x.hour for x in sorted(hourly, key=lambda x: x.value)[:3]]
    to_air = provider.minutes(_pos(p), (repo.airport.lat, repo.airport.lng), h * 60, transport)
    cong = p.congestion(h, wk)
    facilities: dict[str, str] = {}
    if p.work_grade:
        facilities['작업 적합도(검색 조사)'] = p.work_grade
    if p.cuisine:
        facilities['음식 종류'] = p.cuisine
        facilities['가격·대기시간'] = '미확인 · 방문 전 확인'
    if p.break_times:
        facilities['브레이크타임'] = ', '.join('~'.join(pair) for pair in p.break_times)
    if p.closed_weekdays:
        facilities['정기 휴무'] = ', '.join('월화수목금토일'[day] + '요일' for day in p.closed_weekdays)
    if p.last_entry:
        facilities['마지막 주문·입장'] = p.last_entry
    if p.order_closed_windows:
        facilities['회차별 주문 마감'] = ', '.join(left + ' 마감 / ' + right + ' 재개' for left, right in p.order_closed_windows)
    if p.phone:
        facilities['매장 문의'] = p.phone
    if p.day_hours:
        facilities['요일별 운영'] = ', '.join('월화수목금토일'[int(day)] + ' ' + '~'.join(pair) for day, pair in p.day_hours.items())
    facilities['운영시간'] = f'{opening}~{closing} ({p.hours_status})'
    facilities['좌석·Wi-Fi·콘센트'] = '개별 설비 확인 필요'
    evidence: dict[str, float | str] = {
        '시간대 혼잡': '미확보', '지역 지표 기간': p.region_period or '미확인',
        '차량 표본': '도민 포함 TMAP 이용차량',
        '방문량 표본': '내·외국인 SKT 추정 방문량',
        '장소 출처': p.source_url, '장소 확인': '검색 조사(현장 확인 아님)',
        '체류시간 기준': p.stay_source,
        '이동시간 기준': '이동시간 추정' if p.source.startswith('visitjeju') else '장소→공항: 10/15 14시 출발 카카오맵 예상시간; 다른 구간 추정',
        '이용 안내': p.review_notes or '당일 운영 여부 확인 필요',
    }
    if p.region_spend_per_visit is not None:
        evidence['지역 방문 대비 소비(원, 개인 지출액 아님)'] = round(p.region_spend_per_visit)
    if p.operating_source_url:
        evidence['운영정보 출처'] = p.operating_source_url
        evidence['공개 안내 조회일'] = p.checked_on
    if p.region_concentration is not None:
        evidence['지역 월별 차량 도착 쏠림(최대월/평균)'] = round(p.region_concentration, 4)
    if p.review_count is not None:
        evidence[f'{p.review_source} 리뷰 수(카페 조사)'] = p.review_count
    return PlaceDetail(
        place=brief(p),
        badges=[Badge(**b) for b in stop_badges(p, cong, to_air, None, "work" if p.work_grade == '상' else "tour")],
        hourly=hourly,
        best_hours=sorted(best_hours),
        stay_text=f"{duration_text(p.stay_min)} ~ {duration_text(p.stay_max)}",
        to_airport_min=to_air,
        facilities=facilities,
        evidence=evidence,
    )
