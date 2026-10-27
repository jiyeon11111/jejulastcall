"""2026-10-16 공개 운영 안내 조사 결과를 별도 보충 데이터에 반영."""
import json
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'app/data/supplemental_places.json'
rows = json.loads(path.read_text(encoding='utf-8'))
def add(slug, name, coord, address, hours, cid, source, cuisine, **extra):
    row = dict(region='조천', zone='core', popularity=None, conversion=None, quiet=None,
        verified=True, source='visitjeju-crosscheck-2026-10-16', enabled=True,
        hours_status='공개 안내 교차 조회 · 당일 영업 확정 아님',
        stay_source='프로토타입 계획값(실측 체류시간 아님)', suitability=None,
        id='visitjeju-'+slug, name=name, category='restaurant', lat=coord[0], lng=coord[1],
        open=hours[0], close=hours[1], stay_min=50, stay_max=70,
        address='제주시 조천읍 '+address, cuisine=cuisine,
        source_url='https://www.visitjeju.net/kr/detail/view?contentsid='+cid,
        operating_source_url=source, checked_on='2026-10-16',
        review_notes='공개 운영 안내 기준. 임시 휴무·품절·대기는 매장 확인 필요.')
    row.update(extra)
    rows[:] = [r for r in rows if r['id'] != row['id']]
    rows.append(row)

dc='https://www.diningcode.com/profile.php?rid='
tb='https://www.tabling.co.kr/place/'
add('hoechun','함덕회춘',(33.5431462,126.6625984),'신북로 489',('10:30','21:00'),'CNTS_200000000012997',dc+'nlxDSAIYKUD3','한정식·돔베고기',closed_weekdays=[0],break_times=[['15:00','17:00']],order_closed_windows=[['14:00','17:00']],last_entry='20:00',phone='0507-1428-8377',review_notes='함덕 신북로 지점 기준. 일부 관광 안내의 21:30보다 이른 21:00 종료 적용. 점심 주문 14:00 마감. 삼양의 회춘 본점과 구분.')
add('hamdeok-susan','함덕수산',(33.5437203,126.6728038),'조함해안로 570 지하',('12:00','22:00'),'CNTS_300000000016016','https://www.tamnao.com/web/sp/detailPrdt.do?prdtNum=SP00002722','회·해산물',break_times=[['16:00','17:00']],last_entry='21:00',phone='064-783-3600',review_notes='탐나오 12~22시, 비짓제주 휴식 16~17시/주문마감 21시 적용. 호수·전화 안내가 출처별 상이(B102/B103). 같은 건물 지하 매장 위치를 방문 전 확인. 정기 휴무 미확인.')
add('doldam','햇살가득돌담집',(33.541645,126.65835),'함대로 25-1',('09:00','21:00'),'CNTS_000000000021845',dc+'YfvStcCuALDS','흑돼지·쌈밥 정식',closed_weekdays=[0],last_entry='20:30',phone='064-784-2200',review_notes='주소·전화 일치 확인. 다이닝코드 09~21시와 비짓제주 월요일 휴무/20:30 주문마감 반영. 브레이크타임 미확인.')
add('swimpang','함덕쉼팡',(33.5439787,126.6740276),'평사길 4-3 2층',('11:00','22:00'),'CNTS_200000000013324',dc+'n3ulqhEBksDk','피시앤칩스·버거·피자',closed_weekdays=[2],last_entry='21:50',phone='064-784-3949',review_notes='현재 평사길 주소와 수요일 휴무 안내 기준. 과거 조함해안로 주소의 운영시간·일요일 휴무는 적용하지 않음. 브레이크타임 미확인.')
add('hoonnam','훈남횟집',(33.5420803,126.6679293),'함덕13길 7',('12:00','23:30'),'CNTS_200000000013096',tb+'677ccc0966de5f06987e525b','회·회덮밥·해물라면',break_times=[['15:00','17:00']],order_closed_windows=[['14:00','17:00']],last_entry='22:30',phone='0507-1309-0083',review_notes='테이블링 운영시간 및 비짓제주·다이닝코드 휴식/주문마감 대조. 점심 14시, 저녁 22:30 주문마감. 임시휴무 확인 필요.')
add('hanmyeonga','제주한면가',(33.51203,126.70003),'북선로 373',('10:30','15:30'),'CNTS_000000000022908',tb+'677ccb2e66de5f06987cc728','국수·한식',closed_weekdays=[2],day_hours={str(d):['10:30','17:00'] for d in [4,5,6]},last_entry='15:00',phone='064-782-3358',review_notes='주소·전화 일치 확인. 금~일 17시 종료 안내가 있으나 주문마감은 비짓제주 15시를 보수적으로 적용. 수요일 휴무.')
add('danish','다니쉬',(33.5421218,126.6637469),'함덕16길 56',('10:00','17:30'),'CNTS_200000000012603',dc+'gTVAPY4V10je','빵·커피',category='cafe',closed_weekdays=[1,2],stay_min=30,stay_max=60,phone='0507-1333-1377',review_notes='베이커리·카페로 분류. 화·수 휴무 안내. 개점 변동 및 품절 조기 종료 가능, 당일 공지 확인 필요. 작업 설비 미확인.')
add('jomnyeo','좀녀해녀촌',(33.546357,126.6597032),'함덕5길 36 1층',('07:00','20:30'),'CNTS_000000000021268',dc+'CdvHHLZCp6fK','물회·전복죽·성게국',last_entry='20:00',enabled=False,phone='064-782-6769',review_notes='자동 추천 보류: 공개 주간표에 10/16 금요일 휴무가 있으나 정기/임시 여부 불명. 비짓제주는 어촌계 행사·명절 전날 휴무 안내. 07~20:30 운영 안내는 저장하되 휴무 확인 후 활성화 필요.')
add('changheung','창흥식당',(33.540309,126.667206),'함덕16길 15',('11:00','14:00'),'CNTS_200000000007673',tb+'677ccd1366de5f0698805328','한식 소반',last_entry='13:30',phone='064-783-8508',review_notes='대표 창흥소반은 2인 이상 주문 메뉴. 혼자 방문 시 주문 가능 메뉴를 먼저 문의. 비정기 휴무는 매장 공지 확인 필요. 11~14시 운영 및 13:30 주문마감 기준.')
path.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
