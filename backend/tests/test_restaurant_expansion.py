import unittest
from app.engine import build_context, simulate, candidates, _shortlist, plan, place_detail
from app.models import PlanRequest
from app.repository import load
from app.timeutil import parse
from tests.test_rental_timing import BASE

class RestaurantExpansionTests(unittest.TestCase):
    def test_twelve_real_meal_candidates_are_loaded_and_searchable(self):
        ctx=build_context(PlanRequest(**BASE))
        restaurants=[p for p in ctx.repo.places.values() if p.category=='restaurant']
        # 10/16 비짓제주 12곳 + 10/27 카카오맵 7곳(장소후보 시트 30곳 중 식당)
        self.assertEqual(len(restaurants),19)
        self.assertTrue(all(p.cuisine and p.source_url for p in restaurants))
        pool=candidates(ctx,600,set())
        meals={p.id for p in pool if p.category=='restaurant'}
        # 식당 전부를 넣으면 탐색이 12~18초로 느려져 점수 상위 3 + 가까운 2곳으로 제한
        self.assertGreaterEqual(len(meals & {p.id for p in _shortlist(ctx,pool)}), min(4,len(meals)))

    def test_weekly_closures_are_enforced(self):
        for pid,day in [('visitjeju-hwangjegung',4),('visitjeju-geuttaegeujip',2)]:
            ctx=build_context(PlanRequest(**{**BASE,'day_of_week':day}))
            self.assertIsNone(simulate(ctx,[ctx.repo.places[pid]]))
            self.assertNotIn(pid,[p.id for p in candidates(ctx,600,set())])

    def test_break_overlap_and_wednesday_early_close(self):
        p=load().places['visitjeju-nangtteul']
        for day,start in [(1,'15:30'),(1,'16:00'),(2,'15:01'),(2,'17:00')]:
            ctx=build_context(PlanRequest(**{**BASE,'day_of_week':day}))
            self.assertIsNone(simulate(ctx,[p],start=parse(start),start_pos=(p.lat,p.lng)))
        ctx=build_context(PlanRequest(**BASE))
        lunch=simulate(ctx,[p],start=parse('13:00'),start_pos=(p.lat,p.lng))
        dinner=simulate(ctx,[p],start=parse('17:00'),start_pos=(p.lat,p.lng))
        self.assertIsNotNone(lunch)
        self.assertIsNotNone(dinner)

    def test_new_candidates_can_be_planned_and_details_explain_unknowns(self):
        for pid in ['visitjeju-hwangjegung','visitjeju-geuttaegeujip','visitjeju-nangtteul']:
            r=plan(PlanRequest(**BASE,sequence=[pid]))
            self.assertEqual(r.stop_ids,[pid])
            self.assertGreaterEqual(r.margin_min,r.buffer_min)
            d=place_detail(pid,12,True)
            self.assertIn('음식 종류',d.facilities)
            self.assertIn('미확인',d.facilities['가격·대기시간'])

    def test_lunch_order_deadline_and_dinner_reopening(self):
        from unittest.mock import patch
        ctx=build_context(PlanRequest(**BASE))
        with patch('app.engine.provider.minutes', return_value=0):
            for pid in ['visitjeju-hoechun','visitjeju-hoonnam']:
                p=ctx.repo.places[pid]
                for start,valid in [('14:00',True),('14:01',False),('14:30',False),('15:10',False),('17:00',True)]:
                    with self.subTest(place=pid,start=start):
                        result=simulate(ctx,[p],stays=[50],start=parse(start),start_pos=(p.lat,p.lng))
                        self.assertEqual(result is not None,valid)

    def test_new_data_provenance_and_unresolved_closure(self):
        import json
        from app.repository import DATA_DIR
        rows=json.loads((DATA_DIR/'supplemental_places.json').read_text(encoding='utf-8'))
        new=[p for p in rows if p['source']=='visitjeju-crosscheck-2026-10-16']
        self.assertEqual(len(new),9)
        self.assertEqual(sum(p['enabled'] for p in new),8)
        self.assertNotIn('visitjeju-jomnyeo',load().places)
        self.assertEqual(load().places['visitjeju-danish'].category,'cafe')
        for p in new:
            self.assertTrue(p['operating_source_url'] and p['checked_on'] and p['phone'])
        detail=place_detail('visitjeju-hoechun',12,True)
        self.assertIn('14:00',detail.facilities['회차별 주문 마감'])
        self.assertIn('운영정보 출처',detail.evidence)

    def test_additional_weekly_closures(self):
        for pid,day in [('hoechun',0),('doldam',0),('swimpang',2),('hanmyeonga',2),('danish',1),('danish',2)]:
            ctx=build_context(PlanRequest(**{**BASE,'day_of_week':day}))
            self.assertIsNone(simulate(ctx,[ctx.repo.places['visitjeju-'+pid]]))
