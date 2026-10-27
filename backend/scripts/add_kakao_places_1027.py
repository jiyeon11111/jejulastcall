"""시트 30곳(10/11) + 예림 카페 조사표 '적합' 카페를 카카오맵 좌표·영업시간으로 앱에 추가 (2026-10-27)"""
import csv, json, sys
from pathlib import Path
APP = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]; BE = APP / "backend"
sys.path.insert(0, str(BE))
from app.travel import provider
from app import config
rows = json.load(open(sys.argv[2] if len(sys.argv) > 2 else APP / "data/drive/kakao_places_1027.json", encoding="utf-8"))
cafes = {r['카페명']: r for r in csv.DictReader(open(APP/'data/drive/cafes_yerim.csv', encoding='utf-8-sig'))}
alias = {'헬로남생이':'헬로남생이','섬산책':'섬산책','카페 리커버':'카페리커버','딜레탕트 함덕':'딜레당트 함덕'}
def rv(v): return None if v=='미확인' else int(float(v.replace('만',''))*(10000 if '만' in v else 1))
vals = sorted(x for x in (rv(r['리뷰수(네이버)']) for r in cafes.values()) if x is not None)
def pct(n):
    below=sum(x<n for x in vals); eq=sum(x==n for x in vals); return (below+(eq-1)/2)/(len(vals)-1)
airport = (33.5070, 126.4929)
places = json.load(open(BE/'app/data/places.json'))
provider.airport = (places['airport']['lat'], places['airport']['lng'])
stay = {'restaurant':(40,70),'cafe':(60,120),'oreum':(60,90),'forest':(60,90),'heritage':(30,60)}
out = []
for name, region, cat, cid, lat, lng, addr, op, cl, closed, dayh, last, src, lessknown, cuisine, note in rows:
    survey = cafes.get(alias.get(name, name)) if cat == 'cafe' else None
    reviews = rv(survey['리뷰수(네이버)']) if survey else None
    popularity = pct(reviews) if reviews is not None else (round(1-lessknown,3) if lessknown is not None else None)
    to_air = provider.minutes((lat,lng), provider.airport, 14*60, 'car')
    suit = 0.35*max(0,1-to_air/60) + (0.4*(1-popularity) if popularity is not None else 0) + (0.25*(1-len(closed)/7) if cat=='cafe' else 0)
    if survey and survey['최종분류(적합성)'] != '적합':
        raise SystemExit(f'{name}: 예림 분류 {survey["최종분류(적합성)"]} — 추가 대상 아님')
    p = dict(id=f'kakao-{cid}', name=name, region=region, region_code='5011025900' if region=='조천' else '5011025600',
             zone='core' if region=='조천' else 'expansion', category=cat, lat=lat, lng=lng, open=op, close=cl,
             stay_min=stay[cat][0], stay_max=stay[cat][1], popularity=popularity, conversion=None, quiet=None,
             suitability=round(suit,4), verified=True, source='kakao-map-2026-10-27', enabled=True,
             work_grade=survey['업무 적합도(상/중/하)'] if survey else None, review_count=reviews,
             review_source='네이버' if reviews is not None else None, closed_weekdays=closed, day_hours=dayh,
             hours_status='카카오맵 영업정보(10/27 조회) · 방문 전 확인' if cat!='oreum' else '주간 방문 가정',
             stay_source='프로토타입 계획 체류시간 가정(실측 평균 아님)',
             source_url=f'https://place.map.kakao.com/{cid}', operating_source_url=f'https://place.map.kakao.com/{cid}',
             checked_on='2026-10-27', address=addr,
             review_notes='; '.join(x for x in [('예림 카페 조사표 업무 적합도 '+survey['업무 적합도(상/중/하)']) if survey else ('장소후보 시트(10/11) 후보' if src=='sheet30' else ''), note or ''] if x))
    if last: p['last_entry'] = last
    if cuisine: p['cuisine'] = cuisine
    out.append(p)
supp_path = BE/'app/data/supplemental_places.json'
supp = [p for p in json.load(open(supp_path, encoding='utf-8')) if not p['id'].startswith('kakao-')]
existing = {p['name'] for p in supp} | {p['name'] for p in places['places']}
dup = [p['name'] for p in out if p['name'] in existing]
assert not dup, dup
supp = supp + out
supp_path.write_text(json.dumps(supp, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
# 기존 보류 2곳: 카카오맵으로 확인돼 활성화
for p in places['places']:
    if p['name'] == '점점':
        p.update(open='11:00', close='20:00', closed_weekdays=[], enabled=True, hours_status='카카오맵 영업정보(10/27 조회)',
                 review_notes='예림 조사표 영업시간 11:00~10:00 오기 → 카카오맵 11:00~20:00 연중무휴로 확인', operating_source_url='https://place.map.kakao.com/145331867')
    if p['name'] == '자드부팡':
        p.update(lat=33.51233394, lng=126.71050329, address='제주 제주시 조천읍 북흘로 385-216', open='10:00', close='17:00',
                 day_hours={'5':['10:30','17:00'],'6':['10:30','17:00']}, weekday_hours={}, closed_weekdays=[3], enabled=True,
                 hours_status='카카오맵 영업정보(10/27 조회)', operating_source_url='https://place.map.kakao.com/2144187164',
                 review_notes='장소표 주소(385-49)와 조사표 주소(385-216) 불일치 → 카카오맵 385-216 좌표로 정정')
(BE/'app/data/places.json').write_text(json.dumps(places, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
# 이슈 목록 갱신
iss = BE/'app/data/analysis/integration_issues.csv'
ir = [r for r in csv.DictReader(open(iss, encoding='utf-8-sig')) if r['name'] not in ('점점','자드부팡')]
with open(iss,'w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f, fieldnames=['place_id','name','issue']); w.writeheader(); w.writerows(ir)
print('added', len(out), {c: sum(p['category']==c for p in out) for c in stay}, 'expansion', sum(p['zone']=='expansion' for p in out))
