import unittest
from app.engine import plan, simulate, build_context, _valid_sequence
from app.models import PlanRequest
from app.repository import load
from app.timeutil import parse
from tests.test_rental_timing import BASE, HUBS

class CourseQualityTests(unittest.TestCase):
    def test_reported_long_day_combines_meal_culture_rest_and_one_coast(self):
        hub = next(h for h in HUBS if 'GSC스마트' in h['name'])
        req = PlanRequest(**{**BASE, 'flight_time':'19:30', 'airport_arrival_time':'18:50',
                          'rental_return_time':'18:00', 'now':'11:03', 'rental_hub_id':hub['id'], 'day_of_week':4})
        r = plan(req)
        cats = [load().places[i].category for i in r.stop_ids]
        self.assertIn('restaurant', cats)
        self.assertIn('museum', cats)
        self.assertIn('cafe', cats)
        self.assertLessEqual(sum(c in {'beach','walk'} for c in cats), 1)
        self.assertGreaterEqual(parse(r.airport_eta), parse('17:30'))
        self.assertLessEqual(r.unfilled_min, 60)
        self.assertGreaterEqual(r.margin_min, r.buffer_min+15)
        meal = next(t for t in r.timeline if t.place and t.place.category == 'restaurant')
        self.assertTrue(11*60 <= parse(meal.time) <= 14*60)

    def test_meal_preferences_and_unmet_request_are_explicit(self):
        repo = load()
        skip = plan(PlanRequest(**BASE, meal_preference='skip'))
        self.assertFalse(any(repo.places[i].category == 'restaurant' for i in skip.stop_ids))
        include = plan(PlanRequest(**BASE, meal_preference='include'))
        self.assertTrue(any(repo.places[i].category == 'restaurant' for i in include.stop_ids))
        unavailable = plan(PlanRequest(**BASE, meal_preference='include', exclude=[p.id for p in repo.places.values() if p.category=='restaurant']))
        self.assertTrue(any('식사 포함 요청' in n for n in unavailable.planning_notes))

    def test_similar_coastal_experiences_cannot_be_combined(self):
        repo=load()
        self.assertFalse(_valid_sequence((repo.places['hamdeok-beach'],repo.places['yerim-23']), 'tour'))

    def test_new_sources_closure_and_last_admission(self):
        repo=load()
        p=repo.places['visitjeju-haenyeo-gimbap']
        sunday=build_context(PlanRequest(**{**BASE,'day_of_week':6}))
        self.assertIsNone(simulate(sunday,[p]))
        ctx=build_context(PlanRequest(**BASE))
        museum=repo.places['visitjeju-dolhareubang']
        self.assertIsNone(simulate(ctx,[museum],stays=[10],start=16*60+31,start_pos=(museum.lat,museum.lng)))
        self.assertTrue(all(p.source_url.startswith('https://') for p in repo.places.values() if p.source.startswith('visitjeju')))

    def test_long_unfilled_window_is_not_hidden(self):
        r=plan(PlanRequest(**BASE,sequence=['yerim-13']))
        self.assertGreater(r.unfilled_min,60)
        self.assertTrue(any('구성하지 못했어요' in n for n in r.planning_notes))
