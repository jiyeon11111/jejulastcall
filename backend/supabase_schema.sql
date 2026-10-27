-- 제주 라스트콜 베타 사용 기록 (Supabase → SQL Editor → New query → 전체 붙여넣고 Run)
-- 앱 서버(Render)가 service_role 키로만 쓴다. RLS를 켜고 정책을 만들지 않아서
-- 화면용 공개 키(anon)로는 읽기·쓰기가 모두 막힌다.

create table if not exists public.users (
  id uuid primary key,                     -- 화면에서 만든 익명 ID
  nickname text not null,
  consent_version text,
  consented_at timestamptz,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz
);

create table if not exists public.events (
  id bigint generated always as identity primary key,
  user_id uuid not null,
  session_id text,                         -- 한 번 방문(탭) 단위
  type text not null,                      -- plan, plan_error, app_open, live_start, live_done, place_detail, directions_click, swap_open
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.feedback (
  id bigint generated always as identity primary key,
  user_id uuid not null,
  session_id text,
  rating smallint not null check (rating between 1 and 5),
  comment text,
  would_use boolean,
  mode text,
  stop_ids jsonb,
  stop_names jsonb,
  unfilled_min int,
  origin_area text,
  flight_time text,
  created_at timestamptz not null default now()
);

create index if not exists events_user_idx on public.events (user_id);
create index if not exists events_type_time_idx on public.events (type, created_at);
create index if not exists feedback_time_idx on public.feedback (created_at);

alter table public.users enable row level security;
alter table public.events enable row level security;
alter table public.feedback enable row level security;

-- ── 서식 1 '정량적 성과'용 요약 (Table Editor에서 바로 열어 볼 수 있음) ──

create or replace view public.beta_summary with (security_invoker = true) as
select
  (select count(*) from public.users)                                                    as 사용자수,
  (select count(distinct user_id) from public.events where type = 'plan')                as 코스받은_사용자수,
  (select count(*) from public.events where type = 'plan' and payload->>'kind' = 'auto') as 코스추천_횟수,
  (select count(*) from public.events where type = 'plan' and payload->>'kind' <> 'auto') as 장소바꾸기_빼기_횟수,
  (select count(distinct user_id) from public.events where type = 'live_start')          as 출발하기_누른_사용자수,
  (select count(distinct user_id) from public.events where type = 'live_done')           as 끝까지_따라간_사용자수,
  (select count(*) from public.feedback)                                                 as 피드백수,
  (select round(avg(rating)::numeric, 2) from public.feedback)                           as 평균별점,
  (select round(100.0 * avg(case when would_use then 1 else 0 end), 1)
     from public.feedback where would_use is not null)                                    as 쓸의향_퍼센트,
  (select count(*) from (select user_id from public.events where type = 'app_open'
     group by user_id having count(distinct date(created_at at time zone 'Asia/Seoul')) >= 2) t) as 다른날_재방문_사용자수;

create or replace view public.beta_by_mode with (security_invoker = true) as
select
  payload->>'mode'                                   as 모드,
  count(*)                                           as 코스추천_횟수,
  count(distinct user_id)                            as 사용자수,
  round(avg((payload->>'stops')::int), 2)            as 평균_방문지수,
  round(avg((payload->>'unfilled_min')::int), 1)     as 평균_남는시간_분,
  round(avg((payload->>'ms')::int))                  as 평균_응답_ms
from public.events
where type = 'plan' and payload->>'kind' = 'auto'
group by 1
order by 2 desc;

create or replace view public.beta_places with (security_invoker = true) as
select
  name                                               as 장소,
  count(*)                                           as 코스에_들어간_횟수
from public.events, jsonb_array_elements_text(payload->'stop_names') as name
where type = 'plan'
group by 1
order by 2 desc;
