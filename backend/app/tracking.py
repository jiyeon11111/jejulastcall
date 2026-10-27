"""베타 사용 기록 → Supabase.

Render 환경변수 두 개가 있으면 켜지고, 없으면 아무것도 하지 않는다(로컬 개발·테스트용).
  SUPABASE_URL          예: https://abcdxyz.supabase.co
  SUPABASE_SERVICE_KEY  Supabase → Project Settings → API Keys 의 secret 키(sb_secret_...)
                        또는 Legacy 탭의 service_role 키(eyJ...) — 둘 다 된다

비밀 키는 서버에만 둔다. 화면(프론트)은 이 서버의 /api/users·/api/events·/api/feedback 만 부른다.
기록은 별도 스레드로 보내서 코스 계산 응답을 늦추지 않는다. 실패해도 앱 동작에는 영향이 없다.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tracking")


def _config() -> tuple[str, str] | None:
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    return (url, key) if url and key else None


def enabled() -> bool:
    return _config() is not None


def valid_user_id(value: str | None) -> str | None:
    """화면이 만든 익명 ID(UUID)만 받는다. 형식이 다르면 기록하지 않는다."""
    if value and _UUID.match(value.strip().lower()):
        return value.strip().lower()
    return None


def short_session(value: str | None) -> str | None:
    return value.strip()[:64] if value and value.strip() else None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _headers(key: str, prefer: str) -> dict:
    """새 방식 secret 키(sb_secret_...)는 apikey 헤더로만 보낸다.
    예전 service_role 키(eyJ...로 시작하는 JWT)는 Authorization 헤더에도 같이 넣는다."""
    h = {"apikey": key, "Content-Type": "application/json", "Prefer": prefer}
    if key.startswith("eyJ"):
        h["Authorization"] = f"Bearer {key}"
    return h


def _post(table: str, row: dict, upsert: bool = False) -> None:
    cfg = _config()
    if not cfg:
        return
    url, key = cfg
    target = f"{url}/rest/v1/{table}" + ("?on_conflict=id" if upsert else "")
    prefer = "return=minimal" + (",resolution=merge-duplicates" if upsert else "")
    req = urllib.request.Request(
        target,
        data=json.dumps(row, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers=_headers(key, prefer),
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as res:
            res.read()
    except Exception as e:  # 기록 실패는 앱 동작과 무관하게 로그만 남긴다
        detail = ""
        if hasattr(e, "read"):
            try:
                detail = e.read().decode("utf-8", "replace")[:300]  # type: ignore[attr-defined]
            except Exception:
                pass
        print(f"[tracking] {table} 기록 실패: {e} {detail}", flush=True)


def send(table: str, row: dict, upsert: bool = False) -> None:
    """비동기로 한 줄 기록. 설정이 없으면 바로 끝난다."""
    if enabled():
        _pool.submit(_post, table, row, upsert)
