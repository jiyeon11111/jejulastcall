"""장소 데이터 로딩.

1) data/places.json 의 시드 데이터를 읽고
2) data/analysis/ 폴더에 팀 분석 결과 CSV가 있으면 그 값으로 덮어쓴다.

  data/analysis/place_metrics.csv
      place_id,popularity,conversion,quiet          (필요한 열만 있어도 됨, 0~1)
  data/analysis/congestion_hourly.csv
      place_id,hour,is_weekday,congestion           (hour 0~23, is_weekday 1/0, congestion 0~1)
  data/analysis/travel_observed.csv
      origin_id,dest_id,car_min,...                 (공항 ↔ 지점 실측 이동시간. id는 airport | area:<id> | place:<id>)
  data/analysis/region_index.csv
      region,I_spend,저집중도,사분면,...               (lastcall_analysis.py quad 의 out/quadrant_12m.csv 그대로)

시간대 혼잡 자료가 없으면 빈 배열/None을 반환한다. 예시 혼잡은 만들지 않는다.
위 CSV들은 backend/scripts/integrate_team_data.py가 data/drive/ 원표에서 만든다.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
ANALYSIS_DIR = DATA_DIR / "analysis"

# 카테고리별 시간대 상대 혼잡 패턴 (0~23시, 0~1). 예시값.
_PROFILES: dict[str, list[float]] = {
    "beach":      [0, 0, 0, 0, 0, 0, .05, .1, .15, .25, .4, .55, .65, .75, .85, .9, .85, .7, .55, .35, .2, .1, .05, 0],
    "oreum":      [0, 0, 0, 0, 0, .1, .35, .55, .65, .6, .5, .4, .35, .35, .4, .5, .6, .55, .3, .1, 0, 0, 0, 0],
    "walk":       [0, 0, 0, 0, 0, .05, .15, .25, .3, .35, .4, .45, .45, .5, .55, .55, .5, .45, .4, .25, .1, .05, 0, 0],
    "forest":     [0, 0, 0, 0, 0, 0, 0, .1, .3, .5, .65, .7, .65, .7, .7, .6, .45, .25, .05, 0, 0, 0, 0, 0],
    "heritage":   [0, 0, 0, 0, 0, 0, 0, .05, .15, .3, .4, .45, .4, .45, .5, .45, .35, .2, .05, 0, 0, 0, 0, 0],
    "restaurant": [0, 0, 0, 0, 0, 0, .05, .15, .2, .2, .3, .6, .95, .8, .45, .3, .3, .55, .85, .75, .45, .2, .05, 0],
    "cafe":       [0, 0, 0, 0, 0, 0, .05, .1, .2, .3, .4, .45, .55, .7, .85, .9, .8, .6, .45, .35, .25, .15, .05, 0],
}
WEEKEND_FACTOR = 1.15


@dataclass
class Place:
    id: str
    name: str
    region: str
    zone: str  # core(조천) | expansion(구좌) | route(공항 가는 길)
    category: str
    lat: float
    lng: float
    open: str
    close: str
    stay_min: int
    stay_max: int
    popularity: float | None
    conversion: float | None
    quiet: float | None
    station: bool = False
    outlets: int = 0
    seats: int = 0
    wifi: bool = False
    luggage: str | None = None
    # 출처: verified=True 면 팀이 확인한 실제 장소. source: kakao-map-2026-09-28 | real-name-unverified | placeholder
    verified: bool = False
    source: str = "placeholder"
    kakao_reviews: int | None = None
    enabled: bool = True
    # 시간대 혼잡도 [평일 24개, 주말 24개]
    congestion_weekday: list[float] = field(default_factory=list)
    congestion_weekend: list[float] = field(default_factory=list)
    metrics_source: str = "sample"

    region_code: str | None = None
    work_grade: str | None = None
    review_count: int | None = None
    review_source: str | None = None
    closed_weekdays: list[int] = field(default_factory=list)
    weekday_hours: dict[str, list[str]] = field(default_factory=dict)
    hours_status: str = "미확인"
    stay_source: str = "기존 시드 계획값"
    source_url: str = ""
    address: str = ""
    review_notes: str = ""
    region_spend_index: float | None = None
    region_low_concentration: float | None = None
    region_spend_per_visit: float | None = None
    region_concentration: float | None = None
    region_period: str | None = None
    suitability: float | None = None
    last_entry: str | None = None
    day_last_entry: dict[str, str] = field(default_factory=dict)
    day_hours: dict[str, list[str]] = field(default_factory=dict)
    break_times: list[list[str]] = field(default_factory=list)
    cuisine: str | None = None
    order_closed_windows: list[list[str]] = field(default_factory=list)
    operating_source_url: str = ""
    checked_on: str = ""
    phone: str = ""

    def hours(self, weekday: bool, day_of_week: int | None = None) -> tuple[str, str]:
        if day_of_week is not None and str(day_of_week) in self.day_hours:
            return tuple(self.day_hours[str(day_of_week)])
        pair = self.weekday_hours.get("weekday" if weekday else "weekend")
        return (pair[0], pair[1]) if pair else (self.open, self.close)

    def congestion(self, hour: int, weekday: bool) -> float | None:
        series = self.congestion_weekday if weekday else self.congestion_weekend
        return series[max(0, min(23, hour))] if series else None


@dataclass
class Point:
    name: str
    lat: float
    lng: float


@dataclass
class Area:
    id: str
    name: str
    region: str
    lat: float
    lng: float
    # 권역 지수 (region_index.csv 가 있을 때만 채워짐, 0~1)
    spend_index: float | None = None   # 방문 대비 소비 지수 (I_spend)
    low_crowd: float | None = None     # 저집중도 (1 - 차량 도착 집중도)
    quadrant: str | None = None        # 숨은 알짜 / 이미 인기 / 관심 밖 / 방문 대비 소비 낮음
    spend_per_visit: float | None = None
    concentration: float | None = None
    period: str | None = None


@dataclass
class Repository:
    places: dict[str, Place]
    areas: dict[str, Area]
    airport: Point
    rental_hub: Point


def _sample_congestion(category: str, popularity: float, weekday: bool) -> list[float]:
    profile = _PROFILES.get(category, _PROFILES["walk"])
    scale = 0.35 + 0.75 * popularity
    factor = 1.0 if weekday else WEEKEND_FACTOR
    return [round(min(1.0, v * scale * factor), 3) for v in profile]


def _apply_csv_overrides(places: dict[str, Place]) -> None:
    metrics = ANALYSIS_DIR / "place_metrics.csv"
    if metrics.exists():
        with metrics.open(encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                p = places.get(row.get("place_id", ""))
                if not p:
                    continue
                for key in ("popularity", "conversion", "quiet"):
                    if row.get(key) not in (None, ""):
                        setattr(p, key, float(row[key]))
                p.metrics_source = "analysis"

    hourly = ANALYSIS_DIR / "congestion_hourly.csv"
    if hourly.exists():
        with hourly.open(encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                p = places.get(row.get("place_id", ""))
                if not p:
                    continue
                hour = int(row["hour"])
                value = float(row["congestion"])
                if str(row.get("is_weekday", "1")).strip() in ("1", "true", "True"):
                    p.congestion_weekday[hour] = value
                else:
                    p.congestion_weekend[hour] = value
                p.metrics_source = "analysis"


def _strip_region(name: str) -> str:
    return str(name).strip().replace("읍", "").replace("면", "").replace("동", "")


def _apply_region_index(areas: dict[str, Area]) -> None:
    """lastcall_analysis.py quad 결과(quadrant_12m.csv)를 areas 에 붙인다. 읍면동 이름은 '조천읍'→'조천' 으로 맞춘다."""
    path = ANALYSIS_DIR / "region_index.csv"
    if not path.exists():
        return
    with path.open(encoding="utf-8-sig") as f:
        rows = {_strip_region(r.get("region", "")): r for r in csv.DictReader(f)}
    for a in areas.values():
        r = rows.get(_strip_region(a.region))
        if not r:
            continue
        if r.get("I_spend") not in (None, ""):
            a.spend_index = round(float(r["I_spend"]), 3)
        if r.get("저집중도") not in (None, ""):
            a.low_crowd = round(float(r["저집중도"]), 3)
        if r.get("사분면"):
            a.quadrant = r["사분면"]
        a.spend_per_visit = float(r['spend_per_visit']) if r.get('spend_per_visit') else None
        a.concentration = float(r['concentration']) if r.get('concentration') else None
        a.period = r.get('period')


def _load_observed_travel(repo: "Repository") -> None:
    """travel_observed.csv 의 실측값을 이동시간 모델에 등록한다."""
    from . import travel

    travel.provider.airport = (repo.airport.lat, repo.airport.lng)
    travel.provider.observed.clear()
    path = ANALYSIS_DIR / "travel_observed.csv"
    if not path.exists():
        return

    def point(key: str) -> tuple[float, float] | None:
        if key == "airport":
            return (repo.airport.lat, repo.airport.lng)
        kind, _, ident = key.partition(":")
        if kind == "area" and ident in repo.areas:
            return (repo.areas[ident].lat, repo.areas[ident].lng)
        if kind == "place" and ident in repo.places:
            return (repo.places[ident].lat, repo.places[ident].lng)
        return None

    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            a, b = point(row.get("origin_id", "")), point(row.get("dest_id", ""))
            if a and b and row.get("car_min"):
                travel.provider.observe(a, b, int(float(row["car_min"])),
                                        directed=row.get('directed') == '1')


@lru_cache(maxsize=1)
def load() -> Repository:
    raw = json.loads((DATA_DIR / "places.json").read_text(encoding="utf-8"))
    places: dict[str, Place] = {}
    supplement = DATA_DIR / "supplemental_places.json"
    extra = json.loads(supplement.read_text(encoding="utf-8")) if supplement.exists() else []
    for item in raw["places"] + extra:
        p = Place(**item)
        if not p.enabled:
            continue
        # No hourly measurements were collected. Do not manufacture congestion.
        places[p.id] = p
    _apply_csv_overrides(places)
    areas = {a["id"]: Area(**a) for a in raw["areas"]}
    _apply_region_index(areas)
    for p in places.values():
        area = next((a for a in areas.values() if a.region == p.region and a.spend_index is not None), None)
        if area:
            p.region_spend_index = area.spend_index
            p.region_low_concentration = area.low_crowd
            p.region_spend_per_visit = area.spend_per_visit
            p.region_concentration = area.concentration
            p.region_period = area.period
            p.metrics_source = 'analysis'
    repo = Repository(
        places=places,
        areas=areas,
        airport=Point(**raw["airport"]),
        rental_hub=Point(**raw["rental_hub"]),
    )
    _load_observed_travel(repo)
    return repo
