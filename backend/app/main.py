"""제주 라스트콜 API

실행:  uvicorn app.main:app --reload --port 8000
문서:  http://localhost:8000/docs
"""

from __future__ import annotations

import json
import time

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import engine, tracking
from .models import (
    CheckRequest,
    CheckResponse,
    EventIn,
    FeedbackIn,
    PlaceDetail,
    PlanRequest,
    PlanResponse,
    UserIn,
)
from .repository import load
from .repository import DATA_DIR

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
    # tracking: Render에 Supabase 환경변수가 들어갔는지 확인용 (키 값은 내보내지 않음)
    return {"ok": True, "tracking": tracking.enabled()}


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


def _plan_event(req: PlanRequest, res: PlanResponse | None, ms: int, error: str | None) -> dict:
    """코스 요청 한 번을 사용 기록 한 줄로 요약 (개인 위치 좌표는 저장하지 않음)"""
    kind = "swap" if req.sequence is not None else "exclude" if req.exclude else "auto"
    payload = {
        "kind": kind,
        "mode": req.mode,
        "origin_area": req.origin_area or "직접 위치",
        "flight_time": req.flight_time,
        "now": res.now if res else req.now,
        "demo_time": req.now is not None,
        "rental": req.rental,
        "transport": None if req.rental else req.transport,
        "has_baggage": req.has_baggage,
        "meal_preference": req.meal_preference,
        "departure_strategy": req.departure_strategy,
        "ms": ms,
    }
    if res:
        repo = load()
        payload.update(
            status=res.status,
            stop_ids=res.stop_ids,
            stop_names=[repo.places[i].name for i in res.stop_ids if i in repo.places],
            stops=len(res.stop_ids),
            free_min=res.free_min,
            unfilled_min=res.unfilled_min,
            airport_eta=res.airport_eta,
        )
    if error:
        payload["error"] = error[:200]
    return payload


@app.post("/api/plan", response_model=PlanResponse)
def plan(
    req: PlanRequest,
    x_user_id: str | None = Header(None),
    x_session_id: str | None = Header(None),
) -> PlanResponse:
    """여행 정보 + 모드 → 시간 안에 공항까지 갈 수 있는 라스트콜 코스"""
    started = time.perf_counter()
    user = tracking.valid_user_id(x_user_id)
    try:
        res = engine.plan(req)
    except engine.PlanError as e:
        if user:
            tracking.send("events", {"user_id": user, "session_id": tracking.short_session(x_session_id),
                                     "type": "plan_error",
                                     "payload": _plan_event(req, None, int((time.perf_counter() - started) * 1000), str(e))})
        raise HTTPException(status_code=422, detail=str(e)) from e
    if user:
        tracking.send("events", {"user_id": user, "session_id": tracking.short_session(x_session_id), "type": "plan",
                                 "payload": _plan_event(req, res, int((time.perf_counter() - started) * 1000), None)})
    return res


# ── 베타 사용 기록 ──────────────────────────────────────


@app.post("/api/users")
def register(body: UserIn) -> dict:
    """시작 화면에서 닉네임·동의를 받으면 한 번 호출. 같은 ID로 다시 오면 닉네임·접속 시각만 갱신"""
    user = tracking.valid_user_id(body.user_id)
    if not user:
        raise HTTPException(status_code=422, detail="잘못된 사용자 ID예요")
    now = tracking.now_iso()
    tracking.send("users", {"id": user, "nickname": body.nickname, "consent_version": body.consent_version,
                            "consented_at": now, "last_seen_at": now}, upsert=True)
    return {"ok": True, "tracking": tracking.enabled()}


@app.post("/api/events")
def event(body: EventIn, x_user_id: str | None = Header(None), x_session_id: str | None = Header(None)) -> dict:
    user = tracking.valid_user_id(x_user_id)
    if not user:
        return {"ok": False}
    payload = body.payload if len(json.dumps(body.payload, ensure_ascii=False)) <= 2000 else {"truncated": True}
    tracking.send("events", {"user_id": user, "session_id": tracking.short_session(x_session_id),
                             "type": body.type, "payload": payload})
    return {"ok": True}


@app.post("/api/feedback")
def feedback(body: FeedbackIn, x_user_id: str | None = Header(None), x_session_id: str | None = Header(None)) -> dict:
    user = tracking.valid_user_id(x_user_id)
    if not user:
        raise HTTPException(status_code=422, detail="시작 화면에서 닉네임을 먼저 정해 주세요")
    tracking.send("feedback", {"user_id": user, "session_id": tracking.short_session(x_session_id),
                               "rating": body.rating, "comment": body.comment.strip(), "would_use": body.would_use,
                               "mode": body.mode, "stop_ids": body.stop_ids, "stop_names": body.stop_names,
                               "unfilled_min": body.unfilled_min, "origin_area": body.origin_area,
                               "flight_time": body.flight_time})
    return {"ok": True}


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
