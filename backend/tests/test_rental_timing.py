import json
import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.engine import check, plan, build_context, finish
from app.models import PlanRequest, CheckRequest
from app.repository import DATA_DIR, load
from app.timeutil import parse

HUBS = json.loads((DATA_DIR / 'rental_hubs.json').read_text(encoding='utf-8'))
BASE = dict(flight_time='19:20', has_baggage=False, airport_arrival_time='18:40',
            rental=True, rental_hub_id=HUBS[0]['id'], rental_location_confirmed=True,
            rental_return_time='18:30', rental_process_min=15, rental_shuttle_min=10,
            origin_area='hamdeok', now='11:01', day_of_week=1)


class RentalTimingTests(unittest.TestCase):
    def test_explicit_target_is_identical_before_after_and_after_swap(self):
        before = check(CheckRequest(**BASE))
        now = plan(PlanRequest(**BASE, mode='work'))
        later = plan(PlanRequest(**BASE, mode='work', departure_strategy='later', sequence=now.stop_ids))
        for r in (before, now, later):
            self.assertEqual(r.checkpoints[-1].time, '18:40')
        self.assertGreater(parse(later.airport_eta), parse(now.airport_eta))
        self.assertGreater(later.wait_before_departure_min, 0)
        self.assertGreaterEqual(later.margin_min, later.buffer_min + 15)
        self.assertEqual(later.timeline[0].time, later.departure_time)
        for item in later.timeline:
            if item.type == 'stop':
                p = load().places[item.place.id]
                self.assertLessEqual(parse(item.end_time) - parse(item.time), p.stay_max)
                self.assertLessEqual(parse(item.end_time), parse(p.close))
        for index, alternatives in later.alternatives.items():
            for alternative in alternatives:
                sequence = later.stop_ids.copy()
                sequence[index] = alternative.place.id
                swapped = plan(PlanRequest(**BASE, mode='work', departure_strategy='later', sequence=sequence))
                self.assertEqual(swapped.checkpoints[-1].time, '18:40')
                self.assertGreaterEqual(swapped.margin_min, swapped.buffer_min)

    def test_selected_hub_changes_finish_route(self):
        first = build_context(CheckRequest(**BASE))
        second_hub = max(HUBS, key=lambda h: abs(h['lng'] - first.hub[1]))
        second = build_context(CheckRequest(**{**BASE, 'rental_hub_id': second_hub['id']}))
        self.assertEqual(second.hub, (second_hub['lat'], second_hub['lng']))
        self.assertNotEqual(finish(first, first.origin, first.now).travel,
                            finish(second, second.origin, second.now).travel)

    def test_process_and_shuttle_input_affect_eta(self):
        a = check(CheckRequest(**BASE))
        b = check(CheckRequest(**{**BASE, 'rental_process_min': 20, 'rental_shuttle_min': 25}))
        self.assertEqual(parse(b.airport_eta) - parse(a.airport_eta), 20)

    def test_unconfirmed_missing_and_invalid_hubs_do_not_fall_back(self):
        client = TestClient(app)
        for patch in ({'rental_hub_id': None}, {'rental_location_confirmed': False}, {'rental_hub_id': 'missing'}):
            self.assertEqual(client.post('/api/check', json={**BASE, **patch}).status_code, 422)
        hubs = client.get('/api/rental-hubs').json()
        self.assertEqual(len(hubs), 288)
        self.assertTrue(all(not h['return_verified'] for h in hubs))


if __name__ == '__main__':
    unittest.main()
