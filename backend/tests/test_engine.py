"""python -m unittest discover -s tests   (또는 pytest)"""

import unittest

from app import config
from app.engine import PlanError, check, place_detail, plan
from app.models import CheckRequest, PlanRequest
from app.timeutil import parse

BASE = dict(
    flight_time="19:30",
    rental=True,
    rental_hub_id='rental-e61c2acf8346',
    rental_location_confirmed=True,
    rental_return_time="17:30",
    origin_area="hamdeok",
    now="11:00",
    weekday=True,
    day_of_week=1,
)


def stops(res):
    return [i for i in res.timeline if i.type == "stop"]


class PlanTests(unittest.TestCase):
    def test_every_mode_returns_safe_course_within_deadlines(self):
        for mode in ("tour", "work", "rest"):
            with self.subTest(mode=mode):
                res = plan(PlanRequest(**BASE, mode=mode))
                self.assertGreaterEqual(len(stops(res)), 1)
                self.assertGreaterEqual(res.margin_min, res.buffer_min)
                rental, airport = res.checkpoints
                self.assertLessEqual(parse(rental.eta), parse("17:30"))
                self.assertLessEqual(parse(airport.eta), parse("18:30"))  # 출발 60분 전

    def test_timeline_is_chronological(self):
        res = plan(PlanRequest(**BASE, mode="tour"))
        times = [parse(i.time) for i in res.timeline if i.time]
        self.assertEqual(times, sorted(times))

    def test_stop_count_respects_mode_limit(self):
        for mode, limit in config.MAX_STOPS.items():
            res = plan(PlanRequest(**BASE, mode=mode))
            extra = 1 if res.free_min >= config.EXTRA_STOP_FREE_MIN else 0  # 10/27: 모든 모드 공통
            self.assertLessEqual(len(stops(res)), limit + extra)

    def test_work_mode_includes_cafe_with_outlets(self):
        res = plan(PlanRequest(**BASE, mode="work"))
        self.assertTrue(any(s.place.category == "cafe" for s in stops(res)))

    def test_rest_mode_skips_restaurants(self):
        res = plan(PlanRequest(**BASE, mode="rest"))
        self.assertFalse(any(s.place.category == "restaurant" for s in stops(res)))

    def test_gujwa_only_when_enough_free_time(self):
        short = plan(PlanRequest(**{**BASE, "flight_time": "16:30", "rental_return_time": "15:00"}, mode="tour"))
        self.assertFalse(short.expansion)
        self.assertFalse(any(s.place.region == "구좌" for s in stops(short)))
        long = plan(PlanRequest(**BASE, mode="tour"))
        self.assertTrue(long.expansion)

    def test_too_late_returns_no_course(self):
        res = plan(PlanRequest(**{**BASE, "origin_area": "sehwa", "flight_time": "13:00", "rental_return_time": "12:00"}, mode="tour"))
        self.assertEqual(res.status, "late")
        self.assertEqual(stops(res), [])

    def test_fixed_sequence_is_evaluated(self):
        res = plan(PlanRequest(**BASE, mode="tour", sequence=["seoubong", "yerim-13"]))
        self.assertEqual(res.stop_ids, ["seoubong", "yerim-13"])

    def test_exclude_removes_place(self):
        first = plan(PlanRequest(**BASE, mode="tour"))
        removed = first.stop_ids[0]
        again = plan(PlanRequest(**BASE, mode="tour", exclude=[removed]))
        self.assertNotIn(removed, again.stop_ids)

    def test_alternatives_keep_course_feasible(self):
        res = plan(PlanRequest(**BASE, mode="tour"))
        for alts in res.alternatives.values():
            for alt in alts:
                self.assertGreaterEqual(alt.margin_min, config.SAFETY_BUFFER_MIN)

    def test_no_rental_bus_is_slower_than_taxi(self):
        common = {**BASE, "rental": False, "rental_return_time": None}
        taxi = check(CheckRequest(**common, transport="taxi"))
        bus = check(CheckRequest(**common, transport="bus"))
        self.assertGreater(bus.travel_min, taxi.travel_min)

    def test_ui_text_has_no_raw_metric_names(self):
        res = plan(PlanRequest(**BASE, mode="tour"))
        for s in stops(res):
            for b in s.badges:
                self.assertNotIn("지수", b.text)
                self.assertNotIn("0.", b.text)


class InputTests(unittest.TestCase):
    def test_past_flight_rejected(self):
        with self.assertRaises(PlanError):
            plan(PlanRequest(**{**BASE, "flight_time": "10:00"}))

    def test_rental_after_flight_rejected(self):
        with self.assertRaises(PlanError):
            plan(PlanRequest(**{**BASE, "rental_return_time": "20:00"}))

    def test_rental_requires_return_time(self):
        with self.assertRaises(ValueError):
            PlanRequest(**{**BASE, "rental_return_time": None})


class CheckTests(unittest.TestCase):
    def test_latest_departure_is_after_now_when_safe(self):
        res = check(CheckRequest(**BASE))
        self.assertEqual(res.status, "safe")
        self.assertGreater(parse(res.latest_departure), parse("11:00"))

    def test_place_detail_does_not_invent_hourly_series(self):
        d = place_detail("yerim-13", 14, True)
        self.assertEqual(d.hourly, [])
        self.assertNotIn("짐 보관", d.facilities)


if __name__ == "__main__":
    unittest.main()


class DriveSyncTest(unittest.TestCase):
    """구글 드라이브 비교표(카카오맵 9/28)에서 가져온 값이 실제로 쓰이는지"""

    def test_observed_airport_travel_is_used(self):
        from app.repository import load
        from app.travel import provider

        repo = load()
        airport = (repo.airport.lat, repo.airport.lng)
        hamdeok = repo.places["hamdeok-beach"]
        self.assertEqual(provider.minutes((hamdeok.lat, hamdeok.lng), airport, 11 * 60, "car"), 41)
        sehwa = repo.areas["sehwa"]
        self.assertEqual(provider.minutes((sehwa.lat, sehwa.lng), airport, 11 * 60, "car"), 59)

    def test_estimate_close_to_kakao_where_not_observed(self):
        from app.repository import load
        from app.travel import EstimatedTravel

        repo = load()
        fresh = EstimatedTravel()
        fresh.airport = (repo.airport.lat, repo.airport.lng)
        for area_id, kakao in [("jocheon", 33), ("sehwa", 59), ("hamdeok", 38), ("woljeong", 51)]:
            a = repo.areas[area_id]
            est = fresh.minutes((a.lat, a.lng), fresh.airport, 11 * 60, "car")
            self.assertLessEqual(abs(est - kakao), 3, f"{area_id}: est {est} vs kakao {kakao}")

    def test_region_results_and_real_cafes_are_loaded(self):
        from app.repository import load

        repo = load()
        self.assertEqual(repo.places["hamdeok-beach"].metrics_source, "analysis")
        self.assertIsNotNone(repo.places['yerim-13'].popularity)
        self.assertIsNotNone(repo.places['yerim-13'].region_spend_index)
        self.assertNotIn("station-airport", repo.places)  # enabled=false

    def test_placeholder_is_flagged_in_badges(self):
        res = plan(PlanRequest(**BASE, mode="tour"))
        stops = [t for t in res.timeline if t.type == "stop"]
        for t in stops:
            texts = [b.text for b in t.badges]
            if t.place.source == "placeholder":
                self.assertIn("예시 장소 · 확인 필요", texts)
            else:
                self.assertNotIn("예시 장소 · 확인 필요", texts)
