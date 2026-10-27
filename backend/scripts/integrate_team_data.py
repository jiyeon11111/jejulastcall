"""Build app data from preserved Yerim place/cafe CSVs and Junha monthly results.

Run from any directory: python backend/scripts/integrate_team_data.py
Unknown venue hours never become confirmed hours. Outdoor visiting windows and
stay durations are explicit prototype assumptions, not observed measurements.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRIVE = ROOT / 'data' / 'drive'
DATA = ROOT / 'backend' / 'app' / 'data'
OUT = DATA / 'analysis'
PERIOD = '2025.08~2026.07'
SOURCE_PLACES = 'https://drive.google.com/file/d/1dq29c9RVRu7FYdTY9xu5Mouz8Q8ShBYW/view'
SOURCE_CAFES = 'https://drive.google.com/file/d/1zPc1gxKU4ixjKAXPnH1ofk3Q8kSb4vsl/view'


def read(name):
    with (DRIVE / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write(name, rows):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
        w.writeheader()
        w.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    monthly = read('monthly_indices_JH.csv')
    quads = {r['읍면동명']: r for r in read('quadrant_JH.csv')}
    grouped = defaultdict(list)
    for r in monthly:
        grouped[r['읍면동명']].append(r)
    assert len(grouped) == 43 and len(monthly) == 516
    regions = []
    for region, rows in grouped.items():
        assert len(rows) == 12 and len({r['기준연월'] for r in rows}) == 12
        visits = sum(float(r['총_방문객수']) for r in rows)
        spend = sum(float(r['관광객_소비금액']) for r in rows)
        arrivals = [float(r['차량_도착건수']) for r in rows]
        assert visits > 0 and sum(arrivals) > 0
        regions.append(dict(region=region, region_code=rows[0]['표준_읍면동코드'],
                            period=PERIOD, months=12, visitors=visits, tourist_spend=spend,
                            spend_per_visit=spend / visits,
                            arrival_mean=sum(arrivals) / 12, arrival_max=max(arrivals),
                            concentration=max(arrivals) / (sum(arrivals) / 12),
                            I_spend=float(quads[region]['방문대비소비지수']),
                            사분면=quads[region]['사분면'],
                            arrival_population='도민 포함 TMAP 이용차량',
                            visitor_population='내·외국인 SKT 방문량',
                            source='JH monthly_indices.csv; quadrant_12m.csv'))
    lo, hi = min(r['concentration'] for r in regions), max(r['concentration'] for r in regions)
    for r in regions:
        r['concentration_normalized'] = (r['concentration'] - lo) / (hi - lo)
        r['저집중도'] = 1 - r['concentration_normalized']
    write('region_index.csv', sorted(regions, key=lambda r: r['region_code']))

    cafes = {r['카페명']: r for r in read('cafes_yerim.csv')}
    review_values = sorted(float(r['리뷰수(네이버)'].replace('만', '')) * (10000 if '만' in r['리뷰수(네이버)'] else 1)
                           for r in cafes.values() if r['리뷰수(네이버)'] != '미확인')
    seed = json.loads((DRIVE / 'places_seed_ver1.json').read_text(encoding='utf-8'))
    names = {'함덕해수욕장': 'hamdeok-beach', '서우봉 산책로': 'seoubong'}
    outdoor = {'남생이못', '신흥해수욕장', '함덕해수욕장', '올레길 19코스', '서우봉 산책로',
               '닭머르해안길 1코스', '함덕북촌마을길', '조천해안도로'}
    places, travels, issues = [], [], []
    for row in read('places_yerim.csv'):
        if not row.get('장소명'):
            continue
        name = row['장소명']
        pid = names.get(name, 'yerim-' + row['번호'])
        cafe = cafes.get(name)
        category = 'cafe' if row['유형'] == '카페' else ('beach' if '해수욕장' in name else 'walk' if name in outdoor else 'heritage')
        reasons = []
        opening, closing, hours_status = '09:00', '18:00', '미확인'
        weekdays = {}
        closed_days = []
        grade = cafe['업무 적합도(상/중/하)'] if cafe else None
        popularity, reviews = None, None
        if cafe:
            hours = cafe['영업시간']
            ranges = re.findall(r'(\d{1,2}:\d{2})\s*[~\-]\s*(\d{1,2}:\d{2})', hours)
            if len(ranges) == 2 and '평일' in hours and '주말' in hours:
                weekdays = {'weekday': list(ranges[0]), 'weekend': list(ranges[1])}
                opening, closing = ranges[0]
            elif len(ranges) == 1:
                opening, closing = ranges[0]
            else:
                reasons.append('영업시간 미확인')
            opening = opening.zfill(5)
            closing = closing.zfill(5)
            if ranges and closing > opening:
                hours_status = '검색 조사'
            elif ranges:
                reasons.append('영업시간 역전/익일 종료 확인 필요')
            closed_days = [i for i, day in enumerate('월화수목금토일') if day in cafe['휴무일']]
            if cafe['최종분류(적합성)'] != '적합':
                reasons.append('카페 조사 분류: ' + cafe['최종분류(적합성)'])
            if name == '자드부팡':
                reasons.append('장소표와 카페 조사표 주소 불일치')
            if cafe['리뷰수(네이버)'] != '미확인':
                v = cafe['리뷰수(네이버)']
                reviews = int(float(v.replace('만', '')) * (10000 if '만' in v else 1))
                below = sum(x < reviews for x in review_values)
                equal = sum(x == reviews for x in review_values)
                popularity = (below + (equal - 1) / 2) / (len(review_values) - 1)
        elif name in outdoor:
            opening, closing, hours_status = '09:00', '18:00', '주간 방문 가정'
        else:
            reasons.append('운영시간·입장조건 미확인')
        p = dict(id=pid, name=name, region='조천', region_code='5011025900', zone='core', category=category,
                 lat=float(row['위도(lat)']), lng=float(row['경도(lon)']), open=opening, close=closing,
                 stay_min=60 if cafe else 30, stay_max=120 if cafe else 60,
                 popularity=popularity, conversion=None, quiet=None,
                 suitability=(0.35 * max(0, 1 - int(row['공항 이동시간(분)']) / 60)
                              + (0.4 * (1 - popularity) if popularity is not None else 0)
                              + (0.25 * (1 - len(closed_days) / 7) if cafe and hours_status == '검색 조사' else 0)),
                 verified=True, source='yerim-search-2026-10-11', enabled=not reasons,
                 work_grade=grade, review_count=reviews, review_source='네이버' if reviews is not None else None,
                 closed_weekdays=closed_days, weekday_hours=weekdays, hours_status=hours_status,
                 stay_source='프로토타입 계획 체류시간 가정(실측 평균 아님)',
                 source_url=SOURCE_PLACES, address=row['주소·위치(일부 기준점 임의 설정)'],
                 review_notes='; '.join(reasons))
        places.append(p)
        if reasons:
            issues.append(dict(place_id=pid, name=name, issue='; '.join(reasons)))
        travels.append(dict(origin_id='place:' + pid, dest_id='airport', dest_name='제주국제공항',
                            car_min=int(row['공항 이동시간(분)']), km='', measured_at='2026-10-11',
                            departure_at='2026-10-15T14:00:00+09:00', source=SOURCE_PLACES,
                            note='카카오맵 예상시간 조회; 미래 출발 기준, 실주행 실측 아님', directed='1'))
    assert len(places) == 25 and len({p['id'] for p in places}) == 25
    # Preserve airport/area reference points, replace all fictitious venue seeds.
    seed['places'] = places
    (DATA / 'places.json').write_text(json.dumps(seed, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    old_travel = read('travel_seed_ver1.csv') if (DRIVE / 'travel_seed_ver1.csv').exists() else []
    write('travel_observed.csv', [r for r in old_travel if r['dest_id'].startswith('area:')] + travels)
    write('place_metrics.csv', [dict(place_id=p['id'], popularity=p['popularity'] if p['popularity'] is not None else '',
                                     source=SOURCE_CAFES) for p in places])
    write('integration_issues.csv', issues)
    manifest = dict(version='team-integration-2026-10-14', period=PERIOD, region_count=43,
                    place_count=25, enabled_count=sum(p['enabled'] for p in places),
                    work_cafes=sum(p['enabled'] and p['category'] == 'cafe' and p['work_grade'] == '상' for p in places),
                    excluded=issues, assumptions=['체류시간은 계획값', '야외 09~18시는 주간 방문 가정',
                        '일부 장소 운영정보 미확인으로 제외', '렌터카 차고지·장소 간 이동은 기존 추정식',
                        '월별 최대/평균은 계절 쏠림 지표이며 실시간 혼잡 아님'],
                    sources=[dict(file=n, sha256=hashlib.sha256((DRIVE / n).read_bytes()).hexdigest())
                             for n in ['monthly_indices_JH.csv', 'quadrant_JH.csv', 'places_yerim.csv', 'cafes_yerim.csv']],
                    target_regions=[r for r in regions if r['region'] in ('조천읍', '구좌읍')])
    (OUT / 'integration_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: manifest[k] for k in ['region_count', 'place_count', 'enabled_count', 'work_cafes']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
