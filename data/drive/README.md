# 구글 드라이브 연동 (2026-10-11 기준)

> 2026-10-14 갱신: 예림·준하 입력이 추가되어 아래 목록은 초기 버전의 기록입니다. 현재 재생성은 `backend/scripts/integrate_team_data.py`를 사용하고, 최신 출처·계산·제외 항목은 앱 루트 `DATA_INTEGRATION.md`를 확인합니다.

지연 계정 드라이브에서 제주 라스트콜과 관련된 파일을 전부 찾아 이 폴더에 내려받았다.
`backend/app/data/analysis/*.csv` 와 `places.json` 의 값은 여기 있는 원본에서 만들었다.

## 드라이브에 있던 파일

| 드라이브 파일 | 수정일 | 이 폴더의 사본 | 앱에 어떻게 쓰였나 |
|---|---|---|---|
| `lastcall_analysis.py` | 2026-10-07 | `lastcall_analysis.py` | 팀 분석 파이프라인(기준월 진단 → 4분면 → 공항 도착 시뮬). 이 스크립트가 내놓는 `out/quadrant_12m.csv` 를 백엔드가 `analysis/region_index.csv` 로 읽는다 |
| `돌담랩_권역 후보 비교표_초안` (시트) | 2026-09-28 | `권역후보비교표_초안.csv` | 카카오맵으로 확인한 공항 이동시간 → `analysis/travel_observed.csv`, 리뷰 수 → `analysis/place_metrics.csv` 의 popularity, 덜 알려진 후보 장소 → `places.json` 에 추가 |
| `제주워케이션_유휴공간_수집시트` (시트) | 2026-09-20 | (사본 없음) | 이전 주제(워케이션 유휴공간) 수집 양식. 43개 행정동 × 기간 템플릿만 있고 값이 비어 있어 연동하지 않음 |

드라이브 링크
- lastcall_analysis.py: https://drive.google.com/file/d/1yzN_Mt9-7bbWUZ-M4LJ9C74qyCwlsYLa/view
- 권역 후보 비교표: https://docs.google.com/spreadsheets/d/1YoRksh-pYVYdOkxBZ5X7rHURD0v0gh7HL6vVPmenrMo/edit
- 워케이션 수집시트: https://docs.google.com/spreadsheets/d/1DRJMo0M6m620eodY_SCxAPAOdlXneod5MIkAQFKHJ-w/edit

## 아직 드라이브에 없는 것 (앱이 기다리는 데이터)

1. **읍면동별 방문객 수 · 카드 소비액 · 차량 도착 (integrated_v1.csv)** — 비교표의 "[데이터 확인 - JH]" 칸. 제주관광빅데이터플랫폼에서 받아 `lastcall_analysis.py quad integrated_v1.csv` 를 돌리면 `out/quadrant_12m.csv` 가 나온다. 그 파일을 `backend/app/data/analysis/region_index.csv` 로 복사하면 권역 지수가 추천에 반영된다.
2. **식당·카페 실제 목록** — 비교표에는 읍별 카페 수(조천 559, 구좌 342)만 있고 개별 가게는 없다. `places.json` 의 식당·카페는 전부 `verified: false` 예시이고, 화면에 "예시 장소 · 확인 필요"로 표시된다. 실제 가게가 정해지면 같은 형식으로 바꿔 넣으면 된다.
3. **시간대별 혼잡도** — `analysis/congestion_hourly.csv`. 지금은 카테고리별 패턴 × 인지도로 만든 예시값.

## 다시 내려받는 법

이 세션은 드라이브 커넥터로 읽었다. 로컬에서 다시 받으려면 드라이브에서 파일을 내려받아 이 폴더에 같은 이름으로 넣고, `backend/scripts/sync_drive.py` 를 실행하면 `analysis/*.csv` 가 다시 만들어진다.
