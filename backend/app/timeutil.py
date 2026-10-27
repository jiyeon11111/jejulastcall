from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache

KST = timezone(timedelta(hours=9))


@lru_cache(maxsize=4096)  # 같은 'HH:MM' 문자열을 코스 탐색 중 수십만 번 변환해서 캐시
def parse(hhmm: str) -> int:
    """'19:30' → 1170 (자정 기준 분)"""
    h, m = hhmm.strip().split(":")
    value = int(h) * 60 + int(m)
    if not 0 <= value < 24 * 60:
        raise ValueError(f"잘못된 시각: {hhmm}")
    return value


def fmt(minutes: int) -> str:
    minutes = max(0, minutes)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def duration_text(minutes: int) -> str:
    h, m = divmod(max(0, minutes), 60)
    if h and m:
        return f"{h}시간 {m}분"
    if h:
        return f"{h}시간"
    return f"{m}분"


def now_kst() -> datetime:
    return datetime.now(KST)


def current_minutes() -> int:
    n = now_kst()
    return n.hour * 60 + n.minute


def is_weekday_today() -> bool:
    return now_kst().weekday() < 5
