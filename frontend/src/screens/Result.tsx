import { useEffect, useState, type CSSProperties } from "react";
import { CATEGORY_ICON, Icon, TRANSPORT_ICON, TRANSPORT_LABEL } from "../components/Icon";
import { CATEGORY_TONE } from "../components/Sticker";
import { Badges, BottomSheet, Logo, PrimaryButton } from "../components/ui";
import { api, kakaoDirections } from "../lib/api";
import { durationText, toHHMM as toHHMMSafe, toMin } from "../lib/time";
import type { Alternative, Mode, Plan, PlaceBrief, PlaceDetail, TimelineItem, TripForm } from "../types";
import { MODES } from "./Ask";

type Sheet =
  | { kind: "detail"; place: PlaceBrief; arrive?: string; leave?: string; inCourse: boolean }
  | { kind: "swap"; index: number; item: TimelineItem }
  | null;

export function Result({
  plan,
  form,
  loading,
  onBack,
  onMode,
  onReplan,
  onStart,
  nowHour,
}: {
  plan: Plan;
  form: TripForm;
  loading: boolean;
  onBack: () => void;
  onMode: (m: Mode) => void;
  onReplan: (extra: { sequence?: string[]; exclude?: string[]; departure_strategy?: "now" | "later"; meal_preference?: "auto" | "include" | "skip" }) => void;
  onStart: () => void;
  nowHour: number;
}) {
  const [showAllPlaces, setShowAllPlaces] = useState(false);
  const [sheet, setSheet] = useState<Sheet>(null);
  const stops = plan.timeline.filter((i) => i.type === "stop");
  const close = () => setSheet(null);

  const replaceAt = (index: number, id: string) => {
    const seq = [...plan.stop_ids];
    seq[index] = id;
    close();
    onReplan({ sequence: seq });
  };
  const removeStop = (id: string) => {
    const seq = plan.stop_ids.filter((x) => x !== id);
    close();
    onReplan(seq.length ? { sequence: seq } : { exclude: [id] });
  };

  return (
    <main className={`result result--${plan.mode}`}>
      <header className="appbar">
        <button aria-label="조건 수정" className="icon-btn" onClick={onBack} type="button">
          <Icon name="back" size={20} />
        </button>
        <button className="cond-pill" onClick={onBack} type="button">
          {form.flightTime} 출발 · {form.originLabel}
          <Icon name="edit" size={13} />
        </button>
        <span className="appbar__spacer" />
      </header>

      <StatusHero form={form} plan={plan} />
      <section className="departure-options" aria-label="식사와 코스 구성">
        <strong>식사도 함께 계획할까요?</strong>
        <div className="meal-options">
          {([{id: "auto", label: "식사시간에 맞춰"}, {id: "include", label: "식사 넣기"}, {id: "skip", label: "이미 먹었어요"}] as const).map(option => (
            <button type="button" className="pill-chip" key={option.id} aria-pressed={plan.meal_preference === option.id} disabled={loading} onClick={() => onReplan({meal_preference: option.id, departure_strategy: "now"})}>{option.label}</button>
          ))}
        </div>
        <p>비슷한 해안 산책은 한 번만, 식사는 가능한 시간대에 배치해요.</p>
        {(plan.planning_notes ?? []).map(note => <p className="planning-notice" key={note}>{note}</p>)}
      </section>
      <section className="departure-options" aria-label="출발 방식">
        <p>공항에는 {form.airportArrivalTime}까지 도착하도록 계획해요.{form.rental && ` 렌터카 ${form.rentalReturnTime} 반납 마감도 함께 지켜야 하므로 공항에 더 일찍 도착할 수 있어요.`}</p>
        <div className="pill-row">
          <button className="pill-chip" aria-pressed={plan.departure_strategy === "now"} disabled={loading} onClick={() => onReplan({ sequence: plan.stop_ids, departure_strategy: "now" })}>지금 출발</button>
          <button className="pill-chip" aria-pressed={plan.departure_strategy === "later"} disabled={loading || !stops.length} onClick={() => onReplan({ sequence: plan.stop_ids, departure_strategy: "later" })}>출발 전 여유시간 활용</button>
        </div>
        {plan.wait_before_departure_min > 0 && <p>{plan.departure_time}에 현재 위치에서 출발하는 계획이에요. 출발 전 {durationText(plan.wait_before_departure_min)}은 별도 여유시간이며 카페 체류시간에 포함되지 않아요.</p>}
      </section>

      <nav className="mode-tabs" aria-label="추천 모드">
        <span
          className={`mode-tabs__pill mode-tabs__pill--${plan.mode}`}
          style={{ transform: `translateX(${MODES.findIndex((m) => m.id === plan.mode) * 100}%)` }}
        />
        {MODES.map((m) => (
          <button
            aria-pressed={plan.mode === m.id}
            className={`mode-tab mode-tab--${m.id} ${plan.mode === m.id ? "is-on" : ""}`}
            key={m.id}
            onClick={() => plan.mode !== m.id && onMode(m.id)}
            type="button"
          >
            <Icon name={m.icon} size={16} />
            {m.label}
          </button>
        ))}
      </nav>

      <section className={`course ${loading ? "is-loading" : ""}`} aria-busy={loading}>
        <div className="section-head">
          <h2>{stops.length ? `라스트콜 코스 ${stops.length}곳` : "추천 코스"}</h2>
          <span>카드를 누르면 자세히 볼 수 있어요</span>
        </div>

        <ol className="tl" key={`${plan.mode}-${plan.stop_ids.join("-")}`}>
          {plan.timeline.map((item, i) => (
            <TimelineRow
              index={i}
              item={item}
              key={i}
              onOpen={() =>
                item.place &&
                setSheet({ kind: "detail", place: item.place, arrive: item.time ?? undefined, leave: item.end_time ?? undefined, inCourse: true })
              }
              onSwap={
                item.stop_index !== null && (plan.alternatives[String(item.stop_index)]?.length ?? 0) > 0
                  ? () => setSheet({ kind: "swap", index: item.stop_index!, item })
                  : undefined
              }
            />
          ))}
        </ol>

        {plan.unfilled_min >= 60 && stops.length > 0 && (
          <p className="hint">
            <Icon name="info" size={15} />
            안전 여유 외 {durationText(plan.unfilled_min)}이 남아요. 현재 방문 후보의 영업시간·체류 상한과 선택한 모드 안에서 구성한 결과예요.
          </p>
        )}
      </section>

      {plan.reachable.length > 0 && (
        <section className="reachable">
          <div className="section-head">
            <h2>지금 바로 갈 수 있는 곳</h2>
            <span>한 곳만 들렀다 가고 싶을 때</span>
          </div>
          <div className="reach-scroll">
            {plan.reachable.slice(0, showAllPlaces ? undefined : 4).map((r, i) => (
              <button
                className={`reach-card tone-bg-${CATEGORY_TONE[r.place.category] ?? "stone"}`}
                key={r.place.id}
                style={{ "--i": i } as CSSProperties}
                onClick={() => setSheet({ kind: "detail", place: r.place, arrive: r.arrive, inCourse: plan.stop_ids.includes(r.place.id) })}
                type="button"
              >
                <span className="icon-dot">
                  <Icon name={CATEGORY_ICON[r.place.category] ?? "location"} size={16} />
                </span>
                <strong>{r.place.name}</strong>
                <small>
                  {TRANSPORT_LABEL[form.rental ? "car" : form.transport ?? "taxi"]} {r.travel_min}분 · 최대 {durationText(r.max_stay_min)}
                </small>
                <span className="tile-link">
                  {r.leave_by}까지 출발 <Icon name="arrow" size={13} />
                </span>
              </button>
            ))}
          </div>
          {plan.reachable.length > 4 && <button type="button" className="ghost-btn reach-more" aria-expanded={showAllPlaces} onClick={() => setShowAllPlaces(!showAllPlaces)}>{showAllPlaces ? "접기" : `나머지 ${plan.reachable.length - 4}곳 더 보기`}</button>}
        </section>
      )}

      <p className="data-note">
        {plan.data_source === "sample"
          ? "혼잡·소비 지표는 예시값이에요. 팀 분석 결과로 교체 예정"
          : "2025.08~2026.07 지역 분석·팀 장소 조사·비짓제주 보완 자료 기준. 이동·체류시간은 계획값이며 현장 조건을 확인해 주세요."}{" "}
        · 이동시간은 추정치예요
      </p>

      <div className="sticky-cta">
        {stops.length > 0 ? (
          <PrimaryButton onClick={onStart} icon="navigate">
            이 코스로 출발하기
          </PrimaryButton>
        ) : (
          <a className="cta cta--orange" href={kakaoDirections("제주국제공항", 33.5066, 126.4929)} rel="noreferrer" target="_blank">
            <span>공항 길찾기</span>
            <span className="arrow-box">
              <Icon name="plane" size={18} />
            </span>
          </a>
        )}
      </div>

      <BottomSheet onClose={close} open={sheet?.kind === "detail"} title={sheet?.kind === "detail" ? sheet.place.name : undefined}>
        {sheet?.kind === "detail" && (
          <DetailSheet
            arrive={sheet.arrive}
            fallbackHour={nowHour}
            inCourse={sheet.inCourse}
            leave={sheet.leave}
            onOnly={() => {
              close();
              onReplan({ sequence: [sheet.place.id] });
            }}
            onRemove={() => removeStop(sheet.place.id)}
            place={sheet.place}
            transport={form.rental ? "car" : (form.transport ?? "taxi")}
          />
        )}
      </BottomSheet>

      <BottomSheet onClose={close} open={sheet?.kind === "swap"} title="다른 곳으로 바꾸기">
        {sheet?.kind === "swap" && (
          <SwapSheet
            alternatives={plan.alternatives[String(sheet.index)] ?? []}
            current={sheet.item}
            margin={plan.margin_min}
            onPick={(id) => replaceAt(sheet.index, id)}
            onRemove={() => removeStop(sheet.item.place!.id)}
          />
        )}
      </BottomSheet>
    </main>
  );
}

function StatusHero({ plan, form }: { plan: Plan; form: TripForm }) {
  const label = { safe: "계획상 도착 목표 충족", tight: "도착은 하지만 빠듯해요", late: "시간이 부족해요" }[plan.status];
  const late = plan.status === "late";
  return (
    <section className={`hero hero--${plan.status}`}>
      <div className="hero__top">
        <span className="mini-pill mini-pill--strong">
          <Icon name={late ? "info" : "check"} size={13} /> {label}
        </span>
        <Logo animate className="hero__logo" size={52} />
      </div>
      {late ? (
        <h1 className="title2">
          <span>지금 바로</span>
          <strong>공항으로 가야 해요</strong>
        </h1>
      ) : (
        <div className="hero__numbers">
          <span className="hero__light">이 코스로 이동하면</span>
          <strong className="hero__big">
            {plan.airport_eta}
            <small>도착 예상</small>
          </strong>
        </div>
      )}
      <p>공항 목표 {plan.checkpoints[plan.checkpoints.length - 1].time}까지 · 비행기 {form.flightTime} 출발</p>
      <p>{plan.unfilled_min >= 60 ? `시간 활용 보완 필요 · 안전 여유 외 ${durationText(plan.unfilled_min)}이 남는 코스` : `반납·공항 마감 중 더 빠른 기준까지 ${plan.margin_min}분 여유`}</p>
      <TimeBar form={form} plan={plan} />
      <div className="checkpoints">
        {plan.checkpoints.map((c) => (
          <div className={`checkpoint ${c.margin_min < plan.buffer_min ? "is-late" : ""}`} key={c.label}>
            <span>{c.label}</span>
            <strong>
              예상 {c.eta} <small>/ 목표 {c.time}까지</small>
            </strong>
            <em>{c.margin_min >= 0 ? `${c.margin_min}분 여유` : `${-c.margin_min}분 늦음`}</em>
          </div>
        ))}
      </div>
    </section>
  );
}

/** 지금 → 비행기 출발까지를 한 줄로: 어디서 얼마나 쓰고, 언제 공항에 닿는지 */
function TimeBar({ plan, form }: { plan: Plan; form: TripForm }) {
  const start = toMin(plan.now);
  const end = toMin(form.flightTime!);
  const span = Math.max(1, end - start);
  const pct = (t: number) => `${Math.max(0, Math.min(100, ((t - start) / span) * 100))}%`;
  const width = (a: number, b: number) => `${Math.max(0.6, ((b - a) / span) * 100)}%`;
  const blocks = plan.timeline.filter((i) => (i.type === "stop" || i.type === "rental") && i.time && i.end_time);
  const eta = toMin(plan.airport_eta);
  const target = toMin(plan.checkpoints[plan.checkpoints.length - 1].time);
  return (
    <div className="timebar" aria-label="시간 흐름">
      <div className="timebar__track">
        {blocks.map((b, i) => (
          <i
            className={`timebar__block timebar__block--${b.type}`}
            key={i}
            style={{ left: pct(toMin(b.time!)), width: width(toMin(b.time!), toMin(b.end_time!)) }}
          />
        ))}
        <i className="timebar__airport" style={{ left: pct(eta), width: width(eta, end) }} />
        <span className="timebar__mark" style={{ left: pct(target) }} />
      </div>
      <div className="timebar__labels">
        <span>계획 기준 {plan.now}</span>
        <span>출발 {form.flightTime}</span>
      </div>
      <div className="timebar__legend">
        <span>
          <i className="lg-stop" />
          코스
        </span>
        <span>
          <i className="lg-wait" />
          공항 대기
        </span>
        <span>
          <i className="lg-mark" />
          목표 {toHHMMSafe(target)}까지
        </span>
      </div>
    </div>
  );
}

function TimelineRow({
  item,
  index,
  onOpen,
  onSwap,
}: {
  item: TimelineItem;
  index: number;
  onOpen: () => void;
  onSwap?: () => void;
}) {
  const style = { "--i": index } as CSSProperties;
  if (item.type === "move")
    return (
      <li className="tl-move" style={style}>
        <Icon name={item.transport ? TRANSPORT_ICON[item.transport] : "bus"} size={14} />
        {item.transport ? `${TRANSPORT_LABEL[item.transport]} ${item.minutes}분` : `${item.title} ${item.minutes}분`}
      </li>
    );
  if (item.type !== "stop")
    return (
      <li className={`tl-point tl-point--${item.type}`} style={style}>
        <time>{item.time}</time>
        <span className="tl-dot">
          <Icon name={item.type === "airport" ? "plane" : item.type === "rental" ? "car" : "location"} size={14} />
        </span>
        <div>
          <strong>{item.title}</strong>
          {item.subtitle && <small>{item.subtitle}</small>}
        </div>
      </li>
    );
  return (
    <li className={`tl-stop ${item.place?.station ? "is-station" : ""}`} style={style}>
      <time>
        {item.time}
        <small>{item.end_time}</small>
      </time>
      <span className="tl-dot tl-dot--stop">{(item.stop_index ?? 0) + 1}</span>
      <div className={`stop-card tone-bg-${CATEGORY_TONE[item.place?.category ?? ""] ?? "stone"}`}>
        <button className="stop-card__main" onClick={onOpen} type="button">
          <span className="stop-card__top">
            <span className="stop-card__cat">{item.subtitle}</span>
            <span className="icon-dot">
              <Icon name={CATEGORY_ICON[item.place?.category ?? ""] ?? "location"} size={16} />
            </span>
          </span>
          <strong>{item.title}</strong>
          {item.place?.station && <span className="station-tag">라스트콜 스테이션 · 짐 보관 제휴 예정</span>}
          {item.place?.source === "placeholder" && <span className="verify-tag">예시 장소 · 실제 업체 확인 필요</span>}
          <Badges items={item.badges.filter((b) => !b.text.startsWith("예시 장소"))} limit={4} />
          {item.reason && <p className="stop-card__reason">{item.reason}</p>}
        </button>
        <div className="stop-card__actions">
          <span className="stop-card__btns">
            {onSwap && (
              <button className="chip-btn" onClick={onSwap} type="button">
                <Icon name="swap" size={13} /> 바꾸기
              </button>
            )}
            <button aria-label="자세히" className="chip-btn chip-btn--dark" onClick={onOpen} type="button">
              자세히 <Icon name="arrow" size={13} />
            </button>
          </span>
        </div>
      </div>
    </li>
  );
}

function SwapSheet({
  alternatives,
  current,
  margin,
  onPick,
  onRemove,
}: {
  alternatives: Alternative[];
  current: TimelineItem;
  margin: number;
  onPick: (id: string) => void;
  onRemove: () => void;
}) {
  return (
    <div className="swap">
      <p className="sheet-lead">
        <b>{current.title}</b> 대신 갈 수 있는 곳이에요. 바꿔도 공항 도착 시간은 지켜요.
      </p>
      {alternatives.map((a) => (
        <button className="swap-row" key={a.place.id} onClick={() => onPick(a.place.id)} type="button">
          <span className={`icon-dot icon-dot--lg tone-bg-${CATEGORY_TONE[a.place.category] ?? "stone"}`}>
            <Icon name={CATEGORY_ICON[a.place.category] ?? "location"} size={18} />
          </span>
          <span className="swap-row__text">
            <strong>{a.place.name}</strong>
            <Badges items={a.badges} limit={2} />
          </span>
          <span className={`swap-row__delta ${a.margin_delta < 0 ? "is-minus" : ""}`}>
            여유 {margin}→{a.margin_min}분
          </span>
        </button>
      ))}
      <button className="text-btn text-btn--danger" onClick={onRemove} type="button">
        <Icon name="minus" size={16} /> 이 장소는 빼고 다시 계산
      </button>
    </div>
  );
}

function DetailSheet({
  place,
  arrive,
  leave,
  inCourse,
  fallbackHour,
  transport,
  onRemove,
  onOnly,
}: {
  place: PlaceBrief;
  arrive?: string;
  leave?: string;
  inCourse: boolean;
  fallbackHour: number;
  transport: string;
  onRemove: () => void;
  onOnly: () => void;
}) {
  const [detail, setDetail] = useState<PlaceDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showEvidence, setShowEvidence] = useState(false);
  const visitFrom = arrive ? Math.floor(toMin(arrive) / 60) : fallbackHour;
  const visitTo = leave ? Math.floor((toMin(leave) - 1) / 60) : visitFrom;

  useEffect(() => {
    let alive = true;
    api
      .place(place.id, visitFrom, transport)
      .then((d) => alive && setDetail(d))
      .catch((e: Error) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [place.id, visitFrom, transport]);

  if (error) return <p className="sheet-lead">{error}</p>;
  if (!detail)
    return (
      <div className="detail">
        <span className="skeleton" style={{ width: "60%" }} />
        <span className="skeleton" style={{ height: 120 }} />
      </div>
    );

  return (
    <div className="detail">
      <p className="detail__meta">
        {detail.place.region} · {detail.place.category_label}
        {arrive && (
          <>
            {" "}
            · <b>{arrive}{leave ? ` – ${leave}` : ""}</b> 방문
          </>
        )}
      </p>
      <Badges items={detail.badges} />

      {detail.hourly.length > 0 ? <div className="hourly">
        <div className="hourly__head">
          <strong>시간대별 붐빔</strong>
          <span>한적한 시간 {detail.best_hours.map((h) => `${h}시`).join(" · ")}</span>
        </div>
        <div className="hourly__bars">
          {detail.hourly.map((h, n) => {
            const inVisit = h.hour >= visitFrom && h.hour <= visitTo;
            return (
              <div
                className={`hourly__col ${inVisit ? "is-visit" : ""} hourly__col--${h.level}`}
                key={h.hour}
                style={{ "--n": n } as CSSProperties}
              >
                <i style={{ height: `${Math.max(6, h.value * 100)}%` }} />
                <small>{h.hour}</small>
              </div>
            );
          })}
        </div>
        <div className="hourly__legend">
          <span>
            <i className="lg lg--visit" />
            방문 예정
          </span>
          <span>
            <i className="lg" />
            예상 붐빔
          </span>
        </div>
      </div> : <p className="sheet-lead">실시간·시간대별 혼잡 정보는 아직 없어요. 지역별 월간 자료는 아래 추천 근거에서 확인할 수 있어요.</p>}

      <div className="facts">
        <div>
          <span>공항까지</span>
          <strong>{detail.to_airport_min}분</strong>
        </div>
        <div>
          <span>추천 체류</span>
          <strong>{detail.stay_text}</strong>
        </div>
        {Object.entries(detail.facilities).map(([k, v]) => (
          <div key={k}>
            <span>{k}</span>
            <strong className={v === "제휴 예정" ? "muted" : ""}>{v}</strong>
          </div>
        ))}
      </div>

      <button className="evidence-toggle" onClick={() => setShowEvidence(!showEvidence)} type="button">
        <Icon name="chart" size={15} /> 왜 추천했나요? 데이터 근거 {showEvidence ? "접기" : "보기"}
      </button>
      {showEvidence && (
        <dl className="evidence">
          {Object.entries(detail.evidence).map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      )}

      <div className="detail__actions">
        <a className="cta cta--orange" href={kakaoDirections(place.name, place.lat, place.lng)} rel="noreferrer" target="_blank">
          <span>카카오맵 길찾기</span>
          <span className="arrow-box">
            <Icon name="map" size={16} />
          </span>
        </a>
        {inCourse ? (
          <button className="ghost-btn" onClick={onRemove} type="button">
            코스에서 빼기
          </button>
        ) : (
          <button className="ghost-btn" onClick={onOnly} type="button">
            여기만 들렀다 가기
          </button>
        )}
      </div>
    </div>
  );
}
