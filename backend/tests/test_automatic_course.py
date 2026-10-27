import unittest
from app.engine import plan
from app.models import PlanRequest
from app.repository import load
from app.timeutil import parse
from tests.test_rental_timing import BASE

class AutomaticCourseTests(unittest.TestCase):
    def test_long_window_uses_multiple_places_without_delaying_departure(self):
        r = plan(PlanRequest(**BASE, mode='tour'))
        self.assertGreaterEqual(len(r.stop_ids), 3)
        self.assertEqual(r.departure_time, BASE['now'])
        self.assertEqual(r.wait_before_departure_min, 0)
        self.assertTrue(any(t.place.category != 'cafe' for t in r.timeline if t.type == 'stop'))
        single = plan(PlanRequest(**BASE, mode='tour', sequence=['yerim-13']))
        self.assertGreater(parse(r.airport_eta), parse(single.airport_eta) + 60)

    def test_deadlines_hours_and_stays_across_time_budgets(self):
        repo = load()
        for now in ('11:01', '14:00', '16:00', '17:20'):
            for mode in ('tour', 'work', 'rest'):
                with self.subTest(now=now, mode=mode):
                    r = plan(PlanRequest(**{**BASE, 'now': now}, mode=mode))
                    if r.stop_ids:
                        self.assertGreaterEqual(r.margin_min, r.buffer_min + 15)
                        self.assertEqual(len(r.stop_ids), len(set(r.stop_ids)))
                        for c in r.checkpoints:
                            self.assertGreaterEqual(c.margin_min, r.buffer_min + 15)
                    for t in r.timeline:
                        if t.type == 'stop':
                            p = repo.places[t.place.id]
                            self.assertGreaterEqual(parse(t.time), parse(p.hours(True)[0]))
                            self.assertLessEqual(parse(t.end_time), parse(p.hours(True)[1]))
                            self.assertGreaterEqual(parse(t.end_time)-parse(t.time), p.stay_min)
                            self.assertLessEqual(parse(t.end_time)-parse(t.time), p.stay_max)

    def test_earlier_return_and_longer_shuttle_reduce_available_course(self):
        full = plan(PlanRequest(**BASE, mode='tour'))
        limited = plan(PlanRequest(**{**BASE, 'rental_return_time': '14:00'}, mode='tour'))
        self.assertLess(parse(limited.checkpoints[0].eta), parse('14:00'))
        self.assertLess(len(limited.stop_ids), len(full.stop_ids))
        long_transfer = plan(PlanRequest(**{**BASE, 'rental_process_min': 100, 'rental_shuttle_min': 120}, mode='tour'))
        self.assertGreaterEqual(long_transfer.margin_min, long_transfer.buffer_min + 15)
        self.assertLess(len(long_transfer.stop_ids), len(full.stop_ids))

    def test_short_window_goes_direct_and_work_keeps_one_work_cafe(self):
        short = plan(PlanRequest(**{**BASE, 'now': '17:40'}, mode='tour'))
        self.assertEqual(short.stop_ids, [])
        work = plan(PlanRequest(**BASE, mode='work'))
        cafes = [t for t in work.timeline if t.type == 'stop' and t.place.category == 'cafe']
        self.assertEqual(len(cafes), 1)
        self.assertEqual(load().places[cafes[0].place.id].work_grade, '상')
