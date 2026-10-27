"""Checks for provenance, regional data, closures and API integration."""
import csv
import json
import unittest
from dataclasses import replace
from fastapi.testclient import TestClient
from app import config
from app.engine import plan, place_detail, place_score, PlanError
from app.main import app
from app.models import PlanRequest
from app.repository import ANALYSIS_DIR, DATA_DIR, load
from app.travel import provider

BASE = dict(flight_time='19:30', rental=True, rental_return_time='17:30',
            rental_hub_id='rental-e61c2acf8346', rental_location_confirmed=True,
            origin_area='hamdeok', now='11:00', day_of_week=1)


class TeamIntegrationTests(unittest.TestCase):
    def test_all_43_regions_have_12_months_and_bounded_scores(self):
        with (ANALYSIS_DIR / 'region_index.csv').open(encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 43)
        for r in rows:
            self.assertEqual(int(r['months']), 12)
            self.assertEqual(r['period'], '2025.08~2026.07')
            self.assertAlmostEqual(float(r['concentration']), float(r['arrival_max']) / float(r['arrival_mean']))
            self.assertGreaterEqual(float(r['저집중도']), 0)
            self.assertLessEqual(float(r['저집중도']), 1)

    def test_spend_matches_junha_report_and_is_used_in_score(self):
        cafe = load().places['yerim-13']
        self.assertAlmostEqual(cafe.region_spend_per_visit, 14308, delta=1)
        self.assertIsNone(cafe.conversion)
        changed = replace(cafe, region_spend_index=cafe.region_spend_index + 0.1)
        for mode, weights in config.MODE_WEIGHTS.items():
            self.assertAlmostEqual(place_score(changed, mode, 12, True) - place_score(cafe, mode, 12, True), weights[0] * 0.1)

    def test_fictitious_and_unresolved_places_are_not_recommended(self):
        repo = load()
        self.assertFalse(any(p.source == 'placeholder' for p in repo.places.values()))
        # 점점(yerim-14)·자드부팡(yerim-18)은 10/27 카카오맵으로 영업시간·주소를 확인해 활성화
        for pid in ['yerim-14', 'yerim-18']:
            self.assertIn(pid, repo.places)
            self.assertTrue(repo.places[pid].operating_source_url.startswith('https://place.map.kakao.com/'))
        for pid in ['yerim-19']:
            self.assertNotIn(pid, repo.places)
            with self.assertRaises(PlanError):
                plan(PlanRequest(**BASE, sequence=[pid]))

    def test_weekly_closure_applies_to_fixed_and_automatic_courses(self):
        thursday = {**BASE, 'day_of_week': 3}
        # Anorok closes Thursday; forcing its ID must not bypass the filter.
        with self.assertRaises(PlanError):
            plan(PlanRequest(**thursday, mode='work', sequence=['yerim-13']))
        self.assertNotIn('yerim-13', plan(PlanRequest(**thursday, mode='work')).stop_ids)

    def test_no_fabricated_crowd_outlet_seats_or_conversion_claim(self):
        detail = place_detail('yerim-13', 14, True)
        self.assertEqual(detail.hourly, [])
        self.assertEqual(detail.best_hours, [])
        self.assertNotIn('콘센트 좌석', detail.facilities)
        self.assertIn('지역 방문 대비 소비(원, 개인 지출액 아님)', detail.evidence)
        self.assertFalse(any(b.text == '덜 붐빔' for b in detail.badges))

    def test_observed_travel_remains_directional(self):
        repo = load()
        p = repo.places['yerim-13']
        pos, airport = (p.lat, p.lng), (repo.airport.lat, repo.airport.lng)
        self.assertTrue(provider.is_observed(pos, airport))
        self.assertFalse(provider.is_observed(airport, pos))
        self.assertEqual(provider.minutes(pos, airport, 14 * 60, 'car'), 33)

    def test_stay_caps_and_closing_time_survive_long_free_time(self):
        repo = load()
        for mode in ('tour', 'work', 'rest'):
            result = plan(PlanRequest(**BASE, mode=mode))
            for reachable in result.reachable:
                self.assertLessEqual(reachable.max_stay_min, repo.places[reachable.place.id].stay_max)
            for item in result.timeline:
                if item.type != 'stop':
                    continue
                p = repo.places[item.place.id]
                def minutes(t):
                    h, m = map(int, t.split(':'))
                    return h * 60 + m
                self.assertLessEqual(minutes(item.end_time) - minutes(item.time), p.stay_max)
                self.assertLessEqual(minutes(item.end_time), minutes(p.close))

    def test_api_three_modes_details_swap_and_short_time(self):
        client = TestClient(app)
        for mode in ('tour', 'work', 'rest'):
            response = client.post('/api/plan', json={**BASE, 'mode': mode})
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body['stop_ids'])
            self.assertEqual(body['data_source'], 'analysis')
            detail = client.get('/api/places/' + body['stop_ids'][0])
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()['hourly'], [])
            self.assertGreaterEqual(body['margin_min'], body['buffer_min'])
        short = client.post('/api/plan', json={**BASE, 'flight_time': '12:00', 'rental_return_time': '11:20'})
        self.assertEqual(short.status_code, 200)
        self.assertEqual(short.json()['stop_ids'], [])


if __name__ == '__main__':
    unittest.main()
