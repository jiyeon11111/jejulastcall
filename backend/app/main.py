"""제주 라스트콜 API

실행:  uvicorn app.main:app --reload --port 8000
문서:  http://localhost:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import engine
from .models import CheckRequest, CheckResponse, PlaceDetail, PlanRequest, PlanResponse
from .repository import load
from .repository import DATA_DIR
import json

app = FastAPI(
    title="제주 라스트콜 API",
    description="떠나기 전 남은 시간을, 덜 알려진 제주에서 — 비행기·렌터카 반납 시간을 지키는 코스 계산",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/areas")
def areas() -> list[dict]:
    """출발 지역 목록 (조천 중심 + 구좌 + 제주시내)"""
    return [vars(a) for a in load().areas.values()]


@app.get('/api/rental-hubs')
def rental_hubs() -> list[dict]:
    return json.loads((DATA_DIR / 'rental_hubs.json').read_text(encoding='utf-8'))


@app.get("/api/modes")
def modes() -> list[dict]:
    return [
        {"id": "tour", "label": "관광", "title": "한 곳이라도 더 둘러보기", "description": "시간 안에 둘러볼 산책길과 카페"},
        {"id": "work", "label": "일", "title": "제주에서 일 마무리하기", "description": "검색 조사에서 작업 적합도가 높은 카페"},
        {"id": "rest", "label": "휴식", "title": "마지막은 여유롭게", "description": "이동시간을 고려한 산책길과 카페"},
    ]


@app.post("/api/plan", response_model=PlanResponse)
def plan(req: PlanRequest) -> PlanResponse:
    """여행 정보 + 모드 → 시간 안에 공항까지 갈 수 있는 라스트콜 코스"""
    try:
        return engine.plan(req)
    except engine.PlanError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/api/check", response_model=CheckResponse)
def check(req: CheckRequest) -> CheckResponse:
    """지금 여기서 출발하면 공항에 제때 도착하는가? (입력 화면 미리보기·진행 모드에서 사용)"""
    try:
        return engine.check(req)
    except engine.PlanError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/api/places/{place_id}", response_model=PlaceDetail)
def place(
    place_id: str,
    hour: int | None = Query(None, ge=0, le=23),
    weekday: bool | None = None,
    transport: str = "car",
) -> PlaceDetail:
    """장소 상세: 시간대별 혼잡도, 공항까지 시간, 데이터 근거"""
    try:
        return engine.place_detail(place_id, hour, weekday, transport)
    except engine.PlanError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
