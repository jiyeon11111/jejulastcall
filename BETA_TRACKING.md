# 베타 사용자 기록 (2026-10-27)

## 무엇이 바뀌었나

- **현재 시각이 기본**: 앱은 실제 한국 시각과 오늘 요일로 계산한다(휴무 반영). 발표 시연은 주소 뒤에 `?demo`(11시), `?now=13:00`처럼 붙이면 예전 데모 시계가 나온다.
- **시작 화면**: 닉네임 + 개인정보 수집·이용 동의(필수). 실명·연락처·이메일·위치 좌표는 받지 않는다. 기기마다 익명 ID(UUID)를 만들어 브라우저에 저장한다.
- **기록**: 화면 → Render 서버 → Supabase. Supabase 비밀 키는 Render 환경변수에만 있다.
- **피드백**: 결과 화면 아래에 별점(1~5), "실제로 쓸 것 같나요?", 한 줄 의견.

## 쌓이는 데이터

| 표 | 한 줄 = | 주요 칸 |
|---|---|---|
| `users` | 사용자 1명 | 닉네임, 동의 시각 |
| `events` | 행동 1번 | `type`과 `payload`(아래) |
| `feedback` | 평가 1번 | 별점, 쓸 의향, 의견, 그때의 코스 |

`events.type`
- `plan`: 코스 계산. payload에 모드·출발 지역·비행기 시간·렌터카·식사·출발 방식·추천 장소·남는 시간·응답 ms. `kind`가 `auto`면 처음 추천, `swap`이면 장소 바꾸기/빼기/여기만, `exclude`면 빼고 다시 계산
- `plan_error`: 계산 실패(영업시간 등)
- `app_open`: 접속
- `live_start`: "이 코스로 출발하기"
- `live_done`: 진행 화면을 끝까지 따라감
- `place_detail`: 장소 상세 열기
- `directions_click`: 카카오맵 길찾기
- `swap_open`: 바꾸기 목록 열기

요약 뷰(Table Editor 왼쪽 목록에 보임)
- `beta_summary`: 사용자 수, 추천 횟수, 바꾸기 횟수, 출발하기/끝까지, 피드백 수, 평균 별점, 쓸 의향 %, 다른 날 재방문
- `beta_by_mode`: 모드별 추천 횟수, 평균 방문지 수, 남는 시간, 응답 속도
- `beta_places`: 장소별 코스에 들어간 횟수

## 처음 한 번 설정

1. supabase.com → 새 프로젝트(Region: Northeast Asia (Seoul))
2. SQL Editor → New query → `backend/supabase_schema.sql` 전체 붙여넣고 Run
3. Project Settings → API Keys에서 **secret 키**(`sb_secret_...`, 또는 Legacy 탭의 `service_role` 키 `eyJ...`) 복사. Project URL은 Integrations → Data API의 API URL에서 끝의 `/rest/v1/`를 뺀 주소
4. Render → 서비스 → Environment → 두 개 추가 후 저장(자동 재배포)
   - `SUPABASE_URL` = Project URL (예: `https://abcd.supabase.co`)
   - `SUPABASE_SERVICE_KEY` = secret 키 (둘 중 무엇이든)
5. `https://<render 주소>/api/health` 에서 `"tracking": true` 확인

secret/service_role 키는 모든 데이터를 읽고 쓸 수 있는 키라 채팅·카톡·GitHub에 올리지 않는다. 표는 RLS를 켜 두어 공개 키로는 접근할 수 없다.

## 개인정보 안내(시작 화면 문구)

수집 항목: 닉네임, 앱 이용 기록, 접속 시각 / 목적: 공모전 출품 서비스 검증·개선, 통계 / 보유: 2026-12-31까지 보관 후 파기 / 동의 거부 시 베타 이용 불가. 보유 기간을 바꾸면 `frontend/src/components/Onboarding.tsx` 문구와 `CONSENT_VERSION`(`lib/session.ts`)을 같이 바꾼다. 버전이 바뀌면 기존 사용자도 다시 동의 화면을 본다.

## 기프티콘 추첨 (10/28 추가)

- 결과 화면에서 별점을 보내면 **응모 코드**(`LC-` + 익명 ID 앞 6자리)와 "1분 설문하고 응모하기" 버튼이 나온다.
- 버튼 주소는 Vercel 환경변수 `VITE_SURVEY_URL`. 구글 설문 '미리 채운 링크'에서 닉네임 자리에 `{nickname}`, 코드 자리에 `{code}`가 들어간 주소를 넣는다(Apps Script 실행 로그의 "앱에 넣을 주소"). 바꾸면 Vercel에서 Redeploy해야 반영된다. 비어 있으면 버튼 없이 코드만 보인다.
- 설문지 생성 스크립트: `docs/make_survey_form.gs` (script.google.com에 붙여넣고 실행)
- 당첨자 확인: Supabase Table Editor → `raffle_check` 뷰에서 설문 시트의 응모 코드를 찾는다. 별점수 1 이상이면 실제로 앱을 쓰고 별점까지 남긴 사람.
- 연락처는 경품 발송이 끝나면 설문 응답 시트에서 열째로 지운다(설문 안내문에 그렇게 고지함).
