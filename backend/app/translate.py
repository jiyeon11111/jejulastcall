"""분석 지표 → 사용자가 바로 판단할 수 있는 말로 번역.

화면에는 '혼잡지수 0.28' 같은 지표명을 그대로 띄우지 않는다.
원값은 상세 화면의 '데이터 근거' 안에만 넣는다.
"""

from __future__ import annotations

from . import config
from .repository import Place
from .timeutil import fmt

CATEGORY_LABEL = {
    "beach": "바다",
    "oreum": "오름",
    "walk": "산책",
    "forest": "숲길",
    "heritage": "유적",
    "restaurant": "식사",
    "museum": "전시·관람",
    "cafe": "카페",
}


def congestion_level(value: float) -> str:
    if value < 0.35:
        return "low"
    if value < 0.65:
        return "mid"
    return "high"


def congestion_text(value: float) -> str:
    return {"low": "덜 붐빔", "mid": "보통", "high": "붐빔"}[congestion_level(value)]


def badge(text: str, tone: str = "neutral") -> dict:
    """tone: good(협재 바다) / warn(노을귤) / neutral(현무암)"""
    return {"text": text, "tone": tone}


def is_good_to_stay(place: Place, congestion: float) -> bool:
    """카페 유휴도 → '머물기 좋음'"""
    return place.category == "cafe" and congestion < 0.5 and (place.outlets >= 4 or place.quiet >= 0.75)


def stop_badges(place: Place, congestion: float | None, to_airport_min: int, leave_by: int | None, mode: str) -> list[dict]:
    out = []
    if mode == 'work' and place.work_grade:
        out.append(badge('작업 적합도 ' + place.work_grade + ' · 검색 조사'))
    if place.source.startswith('visitjeju'):
        out.append(badge('공개 안내 기준 · 당일 운영 확인 필요', 'warn'))
    if place.hours_status == '주간 방문 가정':
        out.append(badge('주간 방문 기준 · 이용 조건 확인', 'warn'))
    if place.popularity is not None and place.popularity < config.LESSER_KNOWN_MAX:
        out.append(badge('조사 카페 중 리뷰가 적은 곳'))
    out.append(badge(f"공항까지 {to_airport_min}분"))
    if congestion is None:
        out.append(badge('실시간 혼잡 정보 없음'))
    if place.source == "placeholder":
        out.append(badge("예시 장소 · 확인 필요", "warn"))
    if leave_by is not None:
        out.append(badge(f"{fmt(leave_by)}까지 출발", "warn"))
    return out


def stop_reason(place: Place, congestion: float | None, arrive: int, to_airport_min: int, mode: str) -> str:
    parts = ['이동과 체류를 계획한 뒤 반납·공항 도착 여유를 계산했어요']
    if mode == 'work' and place.work_grade:
        parts.append('검색 조사에서 작업 적합도가 ' + place.work_grade + '으로 분류됐어요')
    if place.source.startswith('visitjeju'):
        parts.append('비짓제주 안내 기준이며 당일 운영과 대기는 확인이 필요해요')
    if place.hours_status == '주간 방문 가정':
        parts.append('방문 가능 여부는 출발 전에 확인해 주세요')
    return '. '.join(parts) + '.'


def status_headline(status: str, airport_eta: int, margin: int, deadline_label: str) -> str:
    if status == "late":
        return "지금 바로 공항으로 가야 해요"
    if status == "tight":
        return f"{fmt(airport_eta)} 공항 도착,\n여유가 {margin}분뿐이에요"
    return f"{fmt(airport_eta)} 공항 도착,\n{margin}분 여유 있어요"
