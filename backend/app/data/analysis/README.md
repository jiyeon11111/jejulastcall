# 분석 결과 넣는 곳

현재 파일은 `backend/scripts/integrate_team_data.py`가 예림·준하 원표에서 생성합니다. 갱신 후 서버를 다시 켭니다. 정의·출처·제외 항목은 앱 루트 `DATA_INTEGRATION.md`를 확인합니다.

`region_index.csv`에는 43개 지역의 방문 대비 소비 지수와 월별 차량 도착 쏠림(최대월/평균), 43지역 기준 정규화값, 표본·기간이 있습니다. 이 값은 지역 맥락으로 추천점수에 반영되며 점포 결제 전환율이나 실시간 혼잡이 아닙니다.

`integration_issues.csv`는 미확인 운영정보·주소 오류 등으로 추천에서 제외된 장소 목록, `integration_manifest.json`은 입력 해시·기간·가정·후보 수입니다.

## place_metrics.csv  (장소별 지표, 0~1로 정규화)
| 열 | 뜻 | 화면에서 바뀌는 말 |
|---|---|---|
| place_id | places.json 의 id | |
| popularity | 카페 조사표 네이버 리뷰 수의 상대순위 | 낮으면 "조사 카페 중 리뷰가 적은 곳" |
| conversion | 이번 자료로 산출 불가, 입력하지 않음 | 표시하지 않음 |
| quiet | 이번 자료로 산출 불가, 입력하지 않음 | 표시하지 않음 |

## congestion_hourly.csv (미확보)

현재 생성하지 않으며 예시 시간대 곡선도 표시하지 않습니다. 아래는 추후 실제 관측자료 확보 시의 입력 형식입니다. 지역 시간대 카드 소비액을 이 혼잡값으로 대신 넣지 않습니다.
| 열 | 뜻 |
|---|---|
| place_id | places.json 의 id |
| hour | 0~23 |
| is_weekday | 1 평일 / 0 주말 |
| congestion | 0~1 (0.35 미만 "덜 붐빔", 0.65 미만 "보통", 그 이상 "붐빔") |
