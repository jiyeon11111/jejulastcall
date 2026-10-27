from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Mode = Literal["tour", "work", "rest"]
Transport = Literal["car", "taxi", "bus"]
Tone = Literal["good", "warn", "neutral"]
Status = Literal["safe", "tight", "late"]


class TripInput(BaseModel):
    """여행 정보 입력 (모든 계산의 공통 입력)"""

    flight_time: str = Field(..., examples=["19:30"], description="비행기 출발 HH:MM")
    has_baggage: bool = Field(True, description="부칠 짐 여부 (공항 도착 권장시간이 달라짐)")
    rental: bool = Field(True, description="렌터카 이용 여부")
    rental_return_time: str | None = Field(None, examples=["17:30"], description="렌터카 반납 예정 HH:MM")
    rental_hub_id: str | None = None
    rental_location_confirmed: bool = False
    rental_process_min: int = Field(15, ge=0, le=120)
    rental_shuttle_min: int = Field(10, ge=0, le=180)
    airport_arrival_time: str | None = None
    transport: Transport | None = Field(None, description="렌터카 없을 때 이동수단 taxi | bus")
    origin_area: str | None = Field(None, examples=["hamdeok"], description="출발 지역 id (/api/areas)")
    origin_lat: float | None = None
    origin_lng: float | None = None
    now: str | None = Field(None, examples=["11:00"], description="기준 시각. 비우면 현재 한국 시각 (데모용)")
    weekday: bool | None = Field(None, description="평일 여부. 비우면 오늘 기준")
    day_of_week: int | None = Field(None, ge=0, le=6, description="방문 요일: 월=0~일=6. 비우면 오늘 기준")

    @model_validator(mode="after")
    def _check(self) -> "TripInput":
        if self.rental and not self.rental_return_time:
            raise ValueError("렌터카를 이용하면 반납 시간이 필요해요")
        if self.rental and (not self.rental_hub_id or not self.rental_location_confirmed):
            raise ValueError('반납 지점을 선택하고 계약서의 반납 주소와 같은지 확인해 주세요')
        if self.origin_area is None and (self.origin_lat is None or self.origin_lng is None):
            raise ValueError("출발 지역(origin_area) 또는 좌표(origin_lat, origin_lng)가 필요해요")
        return self


class PlanRequest(TripInput):
    meal_preference: Literal["auto", "include", "skip"] = "auto"
    mode: Mode = "tour"
    departure_strategy: Literal['now', 'later'] = 'now'
    sequence: list[str] | None = Field(None, description="장소 id 순서를 직접 지정하면 탐색 대신 그 코스를 계산 (바꾸기·빼기용)")
    exclude: list[str] = Field(default_factory=list, description="추천에서 제외할 장소 id")


class CheckRequest(TripInput):
    place_id: str | None = Field(None, description="지정하면 그 장소에서 출발한다고 보고 계산")


class Badge(BaseModel):
    text: str
    tone: Tone = "neutral"


class PlaceBrief(BaseModel):
    id: str
    name: str
    region: str
    category: str
    category_label: str
    lat: float
    lng: float
    station: bool = False
    verified: bool = False
    source: str = "placeholder"
    kakao_reviews: int | None = None


class TimelineItem(BaseModel):
    type: Literal["start", "move", "stop", "rental", "airport"]
    time: str | None = None
    end_time: str | None = None
    title: str
    subtitle: str | None = None
    minutes: int | None = None
    transport: Transport | None = None
    stop_index: int | None = None
    place: PlaceBrief | None = None
    badges: list[Badge] = []
    reason: str | None = None
    leave_by: str | None = None


class Alternative(BaseModel):
    place: PlaceBrief
    margin_min: int
    margin_delta: int
    badges: list[Badge]


class Reachable(BaseModel):
    place: PlaceBrief
    travel_min: int
    arrive: str
    max_stay_min: int
    leave_by: str
    badges: list[Badge]


class Checkpoint(BaseModel):
    label: str
    time: str
    eta: str
    margin_min: int


class PlanResponse(BaseModel):
    meal_preference: Literal["auto", "include", "skip"]
    unfilled_min: int
    planning_notes: list[str]
    now: str
    departure_time: str
    departure_strategy: Literal['now', 'later']
    wait_before_departure_min: int
    rental_hub: dict | None = None
    mode: Mode
    status: Status
    headline: str
    subline: str
    margin_min: int
    buffer_min: int
    free_min: int
    expansion: bool
    airport_eta: str
    checkpoints: list[Checkpoint]
    direct_travel_min: int
    timeline: list[TimelineItem]
    stop_ids: list[str]
    alternatives: dict[int, list[Alternative]]
    reachable: list[Reachable]
    data_source: str


class CheckResponse(BaseModel):
    now: str
    status: Status
    message: str
    travel_min: int
    airport_eta: str
    margin_min: int
    latest_departure: str
    free_min: int
    checkpoints: list[Checkpoint]


class HourValue(BaseModel):
    hour: int
    value: float
    level: Literal["low", "mid", "high"]


class PlaceDetail(BaseModel):
    place: PlaceBrief
    badges: list[Badge]
    hourly: list[HourValue]
    best_hours: list[int]
    stay_text: str
    to_airport_min: int
    facilities: dict[str, str]
    evidence: dict[str, float | str]
