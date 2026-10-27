import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Icon, type IconName } from "../components/Icon";
import { Sticker, type Shape, type Tone } from "../components/Sticker";
import { PrimaryButton } from "../components/ui";
import { api } from "../lib/api";
import { durationText, toHHMM, toMin } from "../lib/time";
import type { Area, Check, Mode, TripForm, RentalHub } from "../types";

type Step = "flight" | "baggage" | "arrival" | "rental" | "hub" | "return" | "transport" | "origin" | "mode";

const stagger = (i: number) => ({ "--i": i }) as CSSProperties;

/** 제목은 얇은 줄 + 굵은 줄 두 겹 */
const QUESTIONS: Record<Step, { light: string; bold: string; icon: IconName }> = {
  flight: { light: "비행기는", bold: "몇 시 출발이에요?", icon: "plane" },
  baggage: { light: "부칠 짐이", bold: "있나요?", icon: "bag" },
  arrival: { light: "공항에는", bold: "언제까지 도착할까요?", icon: "clock" },
  hub: { light: "렌터카는", bold: "어디에 반납하나요?", icon: "car" },
  rental: { light: "렌터카,", bold: "반납해야 하나요?", icon: "car" },
  return: { light: "렌터카는", bold: "몇 시까지 반납해요?", icon: "clock" },
  transport: { light: "공항까지는", bold: "뭘 타고 가요?", icon: "bus" },
  origin: { light: "지금", bold: "어디쯤이에요?", icon: "location" },
  mode: { light: "남은 시간,", bold: "어떻게 보낼까요?", icon: "sparkle" },
};

export const MODES: {
  id: Mode;
  icon: IconName;
  label: string;
  title: string;
  desc: string;
  shape: Shape;
  sticker: Tone;
}[] = [
  { id: "tour", icon: "compass", label: "관광", title: "한 곳이라도 더", desc: "시간 안에 둘러볼 산책길과 카페", shape: "scallop", sticker: "tangerine" },
  { id: "work", icon: "briefcase", label: "일", title: "제주에서 일 마무리", desc: "검색 조사에서 작업 적합도가 높은 카페", shape: "teacup", sticker: "sea" },
  { id: "rest", icon: "coffee", label: "휴식", title: "마지막은 여유롭게", desc: "이동시간을 고려한 산책길과 카페", shape: "arch", sticker: "canola" },
];

const EAST_BOUNDS = { minLat: 33.4, maxLat: 33.6, minLng: 126.45, maxLng: 126.95 };

function flow(form: TripForm): Step[] {
  const steps: Step[] = ["flight", "baggage", "arrival", "rental"];
  if (form.rental === true) steps.push("hub", "return");
  if (form.rental === false) steps.push("transport");
  steps.push("origin", "mode");
  return steps;
}

function answered(step: Step, form: TripForm): boolean {
  switch (step) {
    case "flight":
      return !!form.flightTime;
    case "baggage":
      return form.hasBaggage !== null;
    case "arrival":
      return !!form.airportArrivalTime;
    case "hub":
      return !!form.rentalHubId && form.rentalLocationConfirmed;
    case "rental":
      return form.rental !== null;
    case "return":
      return !!form.rentalReturnTime;
    case "transport":
      return !!form.transport;
    case "origin":
      return !!form.originArea || form.originLat !== null;
    case "mode":
      return false;
  }
}

function chipText(step: Step, form: TripForm): string {
  switch (step) {
    case "flight":
      return `${form.flightTime} 출발`;
    case "baggage":
      return form.hasBaggage ? "부칠 짐 있음" : "기내 짐만";
    case "arrival":
      return `공항 ${form.airportArrivalTime}까지`;
    case "hub":
      return form.rentalHubLabel ?? "반납 지점";
    case "rental":
      return form.rental ? "렌터카 있음" : "렌터카 없음";
    case "return":
      return `${form.rentalReturnTime} 반납`;
    case "transport":
      return form.transport === "bus" ? "버스" : "택시";
    case "origin":
      return form.originLabel ?? "";
    default:
      return "";
  }
}

export function Ask({
  form,
  setForm,
  areas,
  now,
  apiNow,
  onSubmit,
  onToast,
}: {
  form: TripForm;
  setForm: (f: TripForm) => void;
  areas: Area[];
  now: number;
  apiNow: string | null;
  onSubmit: (mode: Mode) => void;
  onToast: (m: string) => void;
}) {
  const [editing, setEditing] = useState<Step | null>(null);
  const [locating, setLocating] = useState(false);
  const [preview, setPreview] = useState<Check | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const steps = flow(form);
  const current: Step = editing ?? steps.find((s) => !answered(s, form)) ?? "mode";
  const currentIndex = steps.indexOf(current);
  const done = steps.filter((s) => s !== current && answered(s, form));

  const update = (patch: Partial<TripForm>) => {
    setForm({ ...form, ...patch });
    setEditing(null);
  };

  const ready = steps.filter((s) => s !== "mode").every((s) => answered(s, form));
  useEffect(() => {
    if (!ready) {
      setPreview(null);
      return;
    }
    let alive = true;
    setPreviewError(null);
    api
      .check(form, apiNow)
      .then((c) => alive && setPreview(c))
      .catch((e: Error) => alive && setPreviewError(e.message));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, form, apiNow]);

  const locate = () => {
    if (!navigator.geolocation) return onToast("이 기기에서는 위치를 확인할 수 없어요");
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        const { latitude: lat, longitude: lng } = pos.coords;
        const inside = lat > EAST_BOUNDS.minLat && lat < EAST_BOUNDS.maxLat && lng > EAST_BOUNDS.minLng && lng < EAST_BOUNDS.maxLng;
        if (!inside) return onToast("지금은 제주 동부(조천·구좌)만 지원해요. 가까운 지역을 골라 주세요");
        update({ originArea: null, originLat: lat, originLng: lng, originLabel: "현재 위치" });
      },
      () => {
        setLocating(false);
        onToast("위치 권한이 없어서 지역을 직접 골라 주세요");
      },
      { timeout: 8000 },
    );
  };

  const flightMin = form.flightTime ? toMin(form.flightTime) : null;

  return (
    <main className="ask">
      <div className="steps" aria-label={`${currentIndex + 1} / ${steps.length} 단계`}>
        {steps.map((s, i) => (
          <i className={i < currentIndex ? "is-done" : i === currentIndex ? "is-now" : ""} key={s} />
        ))}
      </div>

      {done.length > 0 && (
        <div className="answer-chips" aria-label="입력한 정보, 눌러서 수정">
          {done.map((s) => (
            <button className="answer-chip" key={s} onClick={() => setEditing(s)} type="button">
              <Icon name={QUESTIONS[s].icon} size={14} />
              {chipText(s, form)}
            </button>
          ))}
        </div>
      )}

      <section className="question" key={current}>
        <h1 className="title2">
          <span>{QUESTIONS[current].light}</span>
          <strong>{QUESTIONS[current].bold}</strong>
        </h1>

        {current === "flight" && (
          <TimeWheel
            fromMin={now + 90}
            toMin={22 * 60 + 50}
            initial={form.flightTime}
            confirmLabel={(v) => `${v} 출발이에요`}
            hint={(v) => `지금부터 ${durationText(toMin(v) - now)} 뒤`}
            onConfirm={(v) => {
              const keepReturn = form.rentalReturnTime && toMin(form.rentalReturnTime) < toMin(v);
              update({ flightTime: v, airportArrivalTime: null, rentalReturnTime: keepReturn ? form.rentalReturnTime : null });
            }}
          />
        )}

        {current === "baggage" && (
          <div className="tile-pair">
            <ChoiceTile
              desc="출발 1시간 전 공항 도착으로 계산"
              i={0}
              icon="bag"
              onClick={() => update({ hasBaggage: true, airportArrivalTime: null })}
              selected={form.hasBaggage === true}
              title="있어요"
              tone="tangerine"
            />
            <ChoiceTile
              desc="모바일 체크인, 40분 전 도착으로 계산"
              i={1}
              icon="check"
              onClick={() => update({ hasBaggage: false, airportArrivalTime: null })}
              selected={form.hasBaggage === false}
              title="기내 짐만"
              tone="sea"
            />
          </div>
        )}

        {current === "arrival" && flightMin !== null && (
          <>
            <p>이 시각까지 공항에 도착하는 코스를 계산해요. 코스 예상 도착과는 다른 기준이에요.</p>
            <TimeWheel fromMin={now + 20} toMin={flightMin - 30}
              initial={form.airportArrivalTime ?? toHHMM(flightMin - (form.hasBaggage ? 60 : 40))}
              confirmLabel={(v) => `공항 ${v}까지 도착할게요`}
              hint={(v) => `출발 ${durationText(flightMin - toMin(v))} 전 · 항공사 안내도 확인해 주세요`}
              onConfirm={(v) => update({ airportArrivalTime: v })} />
          </>
        )}

        {current === "hub" && <RentalPicker form={form} onConfirm={update} />}

        {current === "rental" && (
          <div className="tile-pair">
            <ChoiceTile
              desc="반납 지점과 검차·셔틀 시간을 입력해요"
              i={0}
              icon="car"
              onClick={() => update({ rental: true, transport: null })}
              selected={form.rental === true}
              title="반납해요"
              tone="canola"
            />
            <ChoiceTile
              desc="택시나 버스로 공항까지"
              i={1}
              icon="bus"
              onClick={() => update({ rental: false, rentalReturnTime: null })}
              selected={form.rental === false}
              title="렌터카 없어요"
              tone="oreum"
            />
          </div>
        )}

        {current === "return" && flightMin !== null && (
          <TimeWheel
            fromMin={now + 20}
            toMin={flightMin - 40}
            initial={form.rentalReturnTime}
            confirmLabel={(v) => `${v}까지 반납해요`}
            hint={(v) => `비행기 출발 ${durationText(flightMin - toMin(v))} 전`}
            onConfirm={(v) => update({ rentalReturnTime: v })}
          />
        )}

        {current === "transport" && (
          <div className="tile-pair">
            <ChoiceTile
              desc="호출 대기 5분 포함"
              i={0}
              icon="car"
              onClick={() => update({ transport: "taxi" })}
              selected={form.transport === "taxi"}
              title="택시"
              tone="canola"
            />
            <ChoiceTile
              desc="배차 대기 12분, 이동이 더 걸려요"
              i={1}
              icon="bus"
              onClick={() => update({ transport: "bus" })}
              selected={form.transport === "bus"}
              title="버스"
              tone="sea"
            />
          </div>
        )}

        {current === "origin" && (
          <>
            <button className="pill-btn pill-btn--white locate" disabled={locating} onClick={locate} type="button">
              <Icon name="crosshair" size={18} />
              {locating ? "위치 확인 중..." : "현재 위치로 찾기"}
            </button>
            {["조천", "구좌", "제주시"].map((region) => (
              <div className="area-group" key={region}>
                <span className="area-group__label">
                  {region}
                  {region === "조천" && <em>추천 중심 권역</em>}
                  {region === "구좌" && <em>시간 여유 있을 때</em>}
                </span>
                <div className="pill-row">
                  {areas
                    .filter((a) => a.region === region)
                    .map((a, i) => (
                      <button
                        className={`pill-chip ${form.originArea === a.id ? "is-on" : ""}`}
                        key={a.id}
                        onClick={() => update({ originArea: a.id, originLat: null, originLng: null, originLabel: a.name })}
                        style={stagger(i)}
                        type="button"
                      >
                        {a.name}
                      </button>
                    ))}
                </div>
              </div>
            ))}
          </>
        )}

        {current === "mode" && (
          <>
            <TimePreview check={preview} error={previewError} />
            <div className="mode-stack">
              {MODES.map((m, i) => (
                <button
                  className={`mode-card mode-card--${m.id}`}
                  disabled={!preview || preview.status === "late"}
                  key={m.id}
                  onClick={() => onSubmit(m.id)}
                  style={stagger(i + 1)}
                  type="button"
                >
                  <Sticker className="mode-card__sticker" rotate={[-10, -4, 8][i]} shape={m.shape} size={78} tone={m.sticker} />
                  <span className="mode-card__label">{m.label}</span>
                  <strong>{m.title}</strong>
                  <small>{m.desc}</small>
                  <span className="arrow-box">
                    <Icon name="arrow" size={18} />
                  </span>
                </button>
              ))}
            </div>
            {preview?.status === "late" && (
              <div className="sticky-cta">
                <PrimaryButton onClick={() => onSubmit("rest")} icon="plane">
                  공항 가는 길 바로 보기
                </PrimaryButton>
              </div>
            )}
          </>
        )}
      </section>
    </main>
  );
}

function RentalPicker({ form, onConfirm }: { form: TripForm; onConfirm: (patch: Partial<TripForm>) => void }) {
  const [hubs, setHubs] = useState<RentalHub[]>([]);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [id, setId] = useState(form.rentalHubId ?? "");
  const [confirmed, setConfirmed] = useState(form.rentalLocationConfirmed);
  const [process, setProcess] = useState(form.rentalProcessMin);
  const [shuttle, setShuttle] = useState(form.rentalShuttleMin);
  useEffect(() => { api.rentalHubs().then(setHubs).catch((e: Error) => setError(e.message)); }, []);
  const selected = hubs.find((h) => h.id === id);
  const matched = hubs.filter((h) => `${h.name} ${h.address}`.includes(query.trim())).slice(0, 30);
  const shown = selected && !matched.includes(selected) ? [selected, ...matched] : matched;
  const valid = !!selected && confirmed && Number.isInteger(process) && process >= 0 && process <= 120 && Number.isInteger(shuttle) && shuttle >= 0 && shuttle <= 180;
  return <div className="rental-picker">
    <p>업체명과 주소를 검색해 주세요. 목록은 렌터카 POI이며 실제 반납 지점은 계약서에서 확인해야 해요.</p>
    {error && <p role="alert">{error}</p>}
    <label>업체·주소 검색<input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="예: 빌리카, 도두" /></label>
    <label>반납 지점<select value={id} onChange={(e) => { setId(e.target.value); setConfirmed(false); }}>
      <option value="">지점을 선택해 주세요</option>
      {shown.map((h) => <option key={h.id} value={h.id}>{h.name} · {h.address}</option>)}
    </select></label>
    {selected && <p>{selected.address}</p>}
    <label className="rental-confirm"><input type="checkbox" checked={confirmed} disabled={!selected} onChange={(e) => setConfirmed(e.target.checked)} />계약서에 적힌 반납 주소와 같아요</label>
    <p>아래 기본값은 가정이에요. 업체 안내에 맞게 수정해 주세요.</p>
    <label>반납 처리 시간(분)<input type="number" min={0} max={120} value={Number.isFinite(process) ? process : ""} onChange={(e) => setProcess(e.target.value === "" ? NaN : Number(e.target.value))} /></label>
    <label>셔틀 대기·이동 시간(분)<input type="number" min={0} max={180} value={Number.isFinite(shuttle) ? shuttle : ""} onChange={(e) => setShuttle(e.target.value === "" ? NaN : Number(e.target.value))} /></label>
    <div className="sticky-cta"><PrimaryButton disabled={!valid} onClick={() => selected && onConfirm({ rentalHubId: selected.id, rentalHubLabel: selected.name, rentalLocationConfirmed: true, rentalProcessMin: process, rentalShuttleMin: shuttle })}>이 반납지로 계산</PrimaryButton></div>
  </div>;
}

/** 레퍼런스의 숫자 휠: 시(가로 스크롤, 고른 숫자는 큰 동그라미) + 분 알약 */
function TimeWheel({
  fromMin,
  toMin: until,
  initial,
  hint,
  confirmLabel,
  onConfirm,
}: {
  fromMin: number;
  toMin: number;
  initial: string | null;
  hint: (v: string) => string;
  confirmLabel: (v: string) => string;
  onConfirm: (v: string) => void;
}) {
  const hours = useMemo(() => {
    const out: number[] = [];
    for (let h = Math.floor(fromMin / 60); h <= Math.floor(until / 60); h++) if (h < 24) out.push(h);
    return out;
  }, [fromMin, until]);
  const [hour, setHour] = useState<number | null>(initial ? Math.floor(toMin(initial) / 60) : null);
  const [minute, setMinute] = useState<number>(initial ? toMin(initial) % 60 : 0);
  const wheel = useRef<HTMLDivElement>(null);

  const valid = (h: number, m: number) => h * 60 + m >= fromMin && h * 60 + m <= until;
  const value = hour !== null && valid(hour, minute) ? toHHMM(hour * 60 + minute) : null;

  useEffect(() => {
    const box = wheel.current;
    if (!box) return;
    // 아직 안 골랐으면 가운데쯤(보통 저녁 비행기 시간대)을 보여준다
    const target = hour ?? hours[Math.floor(hours.length / 2)];
    const el = box.querySelector<HTMLElement>(`[data-h="${target}"]`);
    if (el) box.scrollTo({ left: el.offsetLeft - box.clientWidth / 2 + el.offsetWidth / 2, behavior: hour === null ? "auto" : "smooth" });
  }, [hour, hours]);

  const pickHour = (h: number) => {
    setHour(h);
    if (!valid(h, minute)) {
      const first = [0, 10, 20, 30, 40, 50].find((m) => valid(h, m));
      if (first !== undefined) setMinute(first);
    }
  };

  return (
    <div className="wheel">
      <div className="wheel__hours" ref={wheel} role="listbox" aria-label="시">
        {hours.map((h, i) => (
          <button
            aria-selected={hour === h}
            className={`wheel__h ${hour === h ? "is-on" : ""} ${hour !== null && Math.abs(h - hour) === 1 ? "is-near" : ""}`}
            data-h={h}
            key={h}
            onClick={() => pickHour(h)}
            role="option"
            style={stagger(i)}
            type="button"
          >
            {h}
          </button>
        ))}
      </div>
      <span className="wheel__unit">시</span>
      <div className="pill-row wheel__mins" role="radiogroup" aria-label="분">
        {[0, 10, 20, 30, 40, 50].map((m) => (
          <button
            aria-checked={minute === m}
            className={`pill-chip ${minute === m ? "is-on" : ""}`}
            disabled={hour !== null && !valid(hour, m)}
            key={m}
            onClick={() => setMinute(m)}
            role="radio"
            type="button"
          >
            {String(m).padStart(2, "0")}분
          </button>
        ))}
      </div>
      <p className="wheel__hint">{value ? hint(value) : "시간을 골라 주세요"}</p>
      <div className="sticky-cta">
        <PrimaryButton disabled={!value} onClick={() => value && onConfirm(value)}>
          {value ? confirmLabel(value) : "다음"}
        </PrimaryButton>
      </div>
    </div>
  );
}

function ChoiceTile({
  icon,
  title,
  desc,
  selected,
  onClick,
  tone,
  i,
}: {
  icon: IconName;
  title: string;
  desc: string;
  selected: boolean;
  onClick: () => void;
  tone: Tone;
  i: number;
}) {
  return (
    <button className={`choice-tile tone-bg-${tone} ${selected ? "is-on" : ""}`} onClick={onClick} style={stagger(i)} type="button">
      <span className="icon-dot">
        <Icon name={icon} size={18} />
      </span>
      <strong>{title}</strong>
      <small>{desc}</small>
      <span className="tile-link">
        선택 <Icon name="arrow" size={14} />
      </span>
    </button>
  );
}

function TimePreview({ check, error }: { check: Check | null; error: string | null }) {
  if (error) return <div className="block block--camellia">{error}</div>;
  if (!check)
    return (
      <div className="block block--canola block--loading">
        <span className="skeleton" style={{ width: 120 }} />
        <span className="skeleton" style={{ width: 200, height: 40 }} />
      </div>
    );
  if (check.status === "late")
    return (
      <div className="block block--camellia">
        <span className="block__label">남은 시간이 거의 없어요</span>
        <strong className="block__big block__big--sm">지금 바로 공항으로</strong>
        <p>
          지금 출발하면 {check.airport_eta} 공항 도착 · 차로 {check.travel_min}분
        </p>
      </div>
    );
  const h = Math.floor(check.free_min / 60);
  const m = check.free_min % 60;
  return (
    <div className="block block--canola">
      <span className="block__label">지금부터 쓸 수 있는 시간</span>
      <strong className="block__big">
        {h > 0 && (
          <>
            {h}
            <small>시간</small>
          </>
        )}
        {m > 0 && (
          <>
            {" "}
            {m}
            <small>분</small>
          </>
        )}
      </strong>
      <p>
        늦어도 <b>{check.latest_departure}</b>엔 공항 쪽으로 출발
      </p>
      <div className="pill-row">
        {check.checkpoints.map((c) => (
          <span className="mini-pill" key={c.label}>
            {c.label} {c.time}
          </span>
        ))}
      </div>
    </div>
  );
}
