"""베타 사용 기록(Supabase) — 가짜 PostgREST 서버로 요청 형식을 확인한다."""
import json
import os
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from fastapi.testclient import TestClient

from app import tracking
from app.main import app

UID = "3f2b8c1e-5a6d-4e7f-9a0b-1c2d3e4f5a6b"
PLAN = {"flight_time": "19:30", "now": "10:00", "origin_area": "hamdeok", "mode": "tour",
        "rental": False, "transport": "taxi", "day_of_week": 1}


class _Fake(BaseHTTPRequestHandler):
    rows: list = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Fake.rows.append((self.path, {k.lower(): v for k, v in self.headers.items()}, body))
        self.send_response(201)
        self.end_headers()

    def log_message(self, *a):
        pass


def _wait(n):
    for _ in range(100):
        if len(_Fake.rows) >= n:
            return
        time.sleep(0.05)


class TrackingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Fake)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        os.environ["SUPABASE_URL"] = f"http://127.0.0.1:{cls.server.server_port}/"
        os.environ["SUPABASE_SERVICE_KEY"] = "sb_secret_test"
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        os.environ.pop("SUPABASE_URL", None)
        os.environ.pop("SUPABASE_SERVICE_KEY", None)

    def setUp(self):
        _Fake.rows.clear()

    def test_health_reports_tracking(self):
        self.assertTrue(self.client.get("/api/health").json()["tracking"])

    def test_register_upserts_user_with_service_key(self):
        r = self.client.post("/api/users", json={"user_id": UID, "nickname": " 지연 ", "consent": True})
        self.assertEqual(r.status_code, 200)
        _wait(1)
        path, headers, body = _Fake.rows[0]
        self.assertEqual(path, "/rest/v1/users?on_conflict=id")
        self.assertEqual(headers["apikey"], "sb_secret_test")
        self.assertNotIn("authorization", headers)  # 새 방식 키는 Authorization에 넣지 않음
        self.assertIn("resolution=merge-duplicates", headers["prefer"])
        self.assertEqual((body["id"], body["nickname"]), (UID, "지연"))

    def test_register_requires_consent_and_uuid(self):
        self.assertEqual(self.client.post("/api/users", json={"user_id": UID, "nickname": "a", "consent": False}).status_code, 422)
        self.assertEqual(self.client.post("/api/users", json={"user_id": "not-a-uuid", "nickname": "a", "consent": True}).status_code, 422)
        time.sleep(0.2)
        self.assertEqual(_Fake.rows, [])

    def test_plan_is_logged_without_coordinates(self):
        h = {"X-User-Id": UID, "X-Session-Id": "s1"}
        res = self.client.post("/api/plan", json=PLAN, headers=h).json()
        _wait(1)
        path, _, row = _Fake.rows[0]
        self.assertEqual(path, "/rest/v1/events")
        self.assertEqual((row["user_id"], row["session_id"], row["type"]), (UID, "s1", "plan"))
        p = row["payload"]
        self.assertEqual(p["kind"], "auto")
        self.assertEqual(p["stop_ids"], res["stop_ids"])
        self.assertEqual(len(p["stop_names"]), len(res["stop_ids"]))
        self.assertTrue(p["demo_time"])
        self.assertNotIn("origin_lat", json.dumps(row))

    def test_swap_and_errors_are_logged(self):
        h = {"X-User-Id": UID}
        self.client.post("/api/plan", json={**PLAN, "sequence": ["yerim-13"]}, headers=h)
        r = self.client.post("/api/plan", json={**PLAN, "sequence": ["no-such-place"]}, headers=h)
        self.assertEqual(r.status_code, 422)
        _wait(2)
        kinds = sorted((row["type"], row["payload"]["kind"]) for _, _, row in _Fake.rows)
        self.assertEqual(kinds, [("plan", "swap"), ("plan_error", "swap")])

    def test_anonymous_requests_are_not_logged(self):
        self.client.post("/api/plan", json=PLAN)
        self.client.post("/api/plan", json=PLAN, headers={"X-User-Id": "junk"})
        self.assertEqual(self.client.post("/api/events", json={"type": "app_open"}).json(), {"ok": False})
        time.sleep(0.3)
        self.assertEqual(_Fake.rows, [])

    def test_events_and_feedback(self):
        h = {"X-User-Id": UID, "X-Session-Id": "s2"}
        self.assertEqual(self.client.post("/api/events", json={"type": "place_detail", "payload": {"place_id": "yerim-13"}}, headers=h).json(), {"ok": True})
        self.assertEqual(self.client.post("/api/events", json={"type": "hack"}, headers=h).status_code, 422)
        r = self.client.post("/api/feedback", json={"rating": 4, "comment": " 좋아요 ", "would_use": True, "mode": "tour",
                                                   "stop_ids": ["yerim-13"], "stop_names": ["아노록커피바"]}, headers=h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.post("/api/feedback", json={"rating": 6}, headers=h).status_code, 422)
        self.assertEqual(self.client.post("/api/feedback", json={"rating": 3}).status_code, 422)
        _wait(2)
        by = {path: row for path, _, row in _Fake.rows}
        self.assertEqual(by["/rest/v1/events"]["payload"], {"place_id": "yerim-13"})
        self.assertEqual((by["/rest/v1/feedback"]["rating"], by["/rest/v1/feedback"]["comment"]), (4, "좋아요"))

    def test_legacy_jwt_key_also_sent_as_bearer(self):
        from app.tracking import _headers
        h = _headers("eyJhbGciOi.test", "return=minimal")
        self.assertEqual((h["apikey"], h["Authorization"]), ("eyJhbGciOi.test", "Bearer eyJhbGciOi.test"))

    def test_tracking_off_without_env(self):
        saved = os.environ.pop("SUPABASE_URL")
        try:
            self.assertFalse(tracking.enabled())
            self.assertEqual(self.client.post("/api/users", json={"user_id": UID, "nickname": "a", "consent": True}).json()["tracking"], False)
        finally:
            os.environ["SUPABASE_URL"] = saved


if __name__ == "__main__":
    unittest.main()
