"""이동시간 추정.

1) data/analysis/travel_observed.csv 에 실측값(카카오맵)이 있는 구간은 그 값을 그대로 쓴다.
2) 없는 구간은 직선거리 × 도로 보정 ÷ 평균속도 + 주차·공항 접근 가산으로 추정한다.
   상수는 드라이브 비교표의 카카오맵 4개 구간(공항→조천 33분·함덕 38분·월정 51분·구좌 59분)에 맞춰 보정했다.
실서비스에서는 TravelProvider 를 카카오모빌리티/TMAP 길찾기 API 구현체로 바꿔 끼우면 된다.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Protocol

from . import config


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _peak_factor(depart_min: int, heading_west: bool) -> float:
    if not heading_west:
        return 1.0
    hour = depart_min // 60
    for (start, end), factor in config.PEAK_HOURS.items():
        if start <= hour < end:
            return factor
    return 1.0


class TravelProvider(Protocol):
    def minutes(self, a: tuple[float, float], b: tuple[float, float], depart_min: int, transport: str) -> int: ...

    def distance_km(self, a: tuple[float, float], b: tuple[float, float]) -> float: ...

    def observe(self, a: tuple[float, float], b: tuple[float, float], car_min: int, directed: bool = False) -> None: ...


@lru_cache(maxsize=4096)
def _key(p: tuple[float, float]) -> tuple[float, float]:
    return (round(p[0], 4), round(p[1], 4))


class EstimatedTravel:
    """API 키 없이 쓰는 추정 모델. observe() 로 넣은 실측 구간은 추정 대신 실측값을 쓴다."""

    def __init__(self) -> None:
        self.observed: dict[tuple[tuple[float, float], tuple[float, float]], int] = {}
        self.airport: tuple[float, float] | None = None
        # 같은 구간·같은 시(hour)·같은 수단은 결과가 같으므로 계산을 재사용 (코스 탐색 속도용)
        self._cache: dict[tuple, int] = {}

    def observe(self, a: tuple[float, float], b: tuple[float, float], car_min: int, directed: bool = False) -> None:
        self.observed[(_key(a), _key(b))] = car_min
        if not directed:
            self.observed[(_key(b), _key(a))] = car_min

    def is_observed(self, a: tuple[float, float], b: tuple[float, float]) -> bool:
        return (_key(a), _key(b)) in self.observed

    def distance_km(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        return haversine_km(a[0], a[1], b[0], b[1]) * config.ROAD_FACTOR

    def _touches_airport(self, a: tuple[float, float], b: tuple[float, float]) -> bool:
        if self.airport is None:
            return False
        return any(haversine_km(*p, *self.airport) < 1.5 for p in (a, b))

    def minutes(self, a: tuple[float, float], b: tuple[float, float], depart_min: int, transport: str) -> int:
        key = (_key(a), _key(b), depart_min // 60, transport, len(self.observed), self.airport)
        hit = self._cache.get(key)
        if hit is None:
            hit = self._cache[key] = self._minutes(a, b, depart_min, transport)
        return hit

    def _minutes(self, a: tuple[float, float], b: tuple[float, float], depart_min: int, transport: str) -> int:
        observed = self.observed.get((_key(a), _key(b)))
        if observed is not None and transport != "bus":
            # 실측값(카카오맵, 저녁 실시간 교통)에는 정체가 이미 들어 있어 피크 보정을 겹치지 않는다
            return observed + (config.TAXI_WAIT_MIN if transport == "taxi" else 0)
        km = self.distance_km(a, b)
        if km < 0.3:
            return 3
        heading_west = b[1] < a[1]  # 제주공항은 동부 권역 기준 서쪽
        if transport == "bus":
            base = km / config.BUS_SPEED_KMH * 60 + config.BUS_WAIT_MIN
        else:
            base = km / config.CAR_SPEED_KMH * 60 + config.CAR_OVERHEAD_MIN
            if self._touches_airport(a, b):
                base += config.AIRPORT_ACCESS_MIN
            if transport == "taxi":
                base += config.TAXI_WAIT_MIN
        return int(math.ceil(base * _peak_factor(depart_min, heading_west)))


provider: TravelProvider = EstimatedTravel()
