import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "./components/Icon";
import { Splash } from "./components/Splash";
import { Sticker } from "./components/Sticker";
import { Onboarding } from "./components/Onboarding";
import { Logo, Toast } from "./components/ui";
import { api, track } from "./lib/api";
import { loadUser, newUser, saveUser, type BetaUser } from "./lib/session";
import { clockNow, toHHMM, type Clock } from "./lib/time";
import { Ask } from "./screens/Ask";
import { Live } from "./screens/Live";
import { Result } from "./screens/Result";
import type { Area, Mode, Plan, TripForm } from "./types";

type Screen = "ask" | "calculating" | "result" | "live";

const EMPTY: TripForm = {
  flightTime: null,
  hasBaggage: null,
  rental: null,
  rentalReturnTime: null,
  rentalHubId: null,
  rentalHubLabel: null,
  rentalLocationConfirmed: false,
  rentalProcessMin: 15,
  rentalShuttleMin: 10,
  airportArrivalTime: null,
  transport: null,
  originArea: null,
  originLat: null,
  originLng: null,
  originLabel: null,
};

const DEMO_TIMES = ["09:00", "11:00", "13:00", "15:00"];

// 베타 기본은 실제 현재 시각. 발표 시연은 주소 뒤에 ?demo (또는 ?now=13:00) 를 붙인다.
const DEMO_ENABLED = (() => {
  const q = new URLSearchParams(window.location.search);
  return q.has("demo") || q.has("now");
})();

function initialClock(): Clock {
  const q = new URLSearchParams(window.location.search);
  if (!DEMO_ENABLED) return { demo: null, anchoredAt: Date.now() };
  return { demo: q.get("now") ?? "11:00", anchoredAt: Date.now() };
}

function register(user: BetaUser) {
  return api
    .register(user.id, user.nickname, user.consentVersion)
    .then(() => saveUser({ ...user, registered: true }))
    .catch(() => undefined); // 서버가 깨어나는 중이면 다음 접속 때 다시 시도
}

export default function App() {
  const [screen, setScreen] = useState<Screen>("ask");
  const [splash, setSplash] = useState(true);
  const finishSplash = useCallback(() => setSplash(false), []);
  const [form, setForm] = useState<TripForm>(EMPTY);
  const [areas, setAreas] = useState<Area[]>([]);
  const [clock, setClock] = useState<Clock>(initialClock);
  const [now, setNow] = useState(() => clockNow(clock));
  const [plan, setPlan] = useState<Plan | null>(null);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [clockMenu, setClockMenu] = useState(false);
  const [user, setUser] = useState<BetaUser | null>(() => loadUser());
  const [joining, setJoining] = useState(false);
  const toastTimer = useRef<number | undefined>(undefined);

  // 이미 닉네임을 정한 사람: 접속 기록 (등록이 안 됐었다면 다시 등록)
  useEffect(() => {
    const u = loadUser();
    if (!u) return;
    (u.registered ? Promise.resolve() : register(u)).then(() => track("app_open", { demo: DEMO_ENABLED }));
  }, []);

  const join = async (nickname: string) => {
    const u = newUser(nickname);
    saveUser(u);
    setJoining(true);
    await Promise.race([register(u), new Promise((r) => setTimeout(r, 4000))]);
    setJoining(false);
    setUser(u);
    track("app_open", { demo: DEMO_ENABLED, first: true });
  };

  useEffect(() => {
    setNow(clockNow(clock));
    const id = window.setInterval(() => setNow(clockNow(clock)), 1000);
    return () => window.clearInterval(id);
  }, [clock]);

  useEffect(() => {
    // 무료 서버가 잠들어 있으면 첫 응답이 늦거나 실패할 수 있어 몇 번 다시 시도한다
    let tries = 0;
    const load = () =>
      api.areas().then(setAreas).catch(() => {
        tries += 1;
        if (tries === 1) showToast("서버를 깨우는 중이에요. 잠시만 기다려 주세요");
        if (tries < 6) window.setTimeout(load, 5000);
        else showToast("서버에 연결할 수 없어요. 잠시 후 새로고침해 주세요");
      });
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const showToast = useCallback((message: string) => {
    setToast(message);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 2600);
  }, []);

  // 데모 시각은 분 단위로 고정해서 API에 보낸다 (실제 시각 모드면 서버가 현재 시각 사용)
  const apiNow = clock.demo ? toHHMM(Math.floor(now)) : null;

  const runPlan = async (mode: Mode, extra?: { sequence?: string[]; exclude?: string[]; departure_strategy?: "now" | "later"; meal_preference?: "auto" | "include" | "skip" }, first = false) => {
    setLoading(true);
    if (first) setScreen("calculating");
    const started = Date.now();
    try {
      const result = await api.plan(form, apiNow, mode, { meal_preference: first ? "auto" : plan?.meal_preference ?? "auto", departure_strategy: first ? "now" : plan?.departure_strategy ?? "now", ...extra });
      if (first) await new Promise((r) => setTimeout(r, Math.max(0, 1100 - (Date.now() - started))));
      setPlan(result);
      setScreen("result");
      window.scrollTo({ top: 0 });
    } catch (e) {
      showToast((e as Error).message);
      if (first) setScreen("ask");
    } finally {
      setLoading(false);
    }
  };

  const setDemo = (demo: string | null) => {
    setClock({ demo, anchoredAt: Date.now() });
    setClockMenu(false);
    if (screen !== "ask") setScreen("ask");
  };

  return (
    <div className="shell">
      <div className="phone">
        {splash && <Splash onDone={finishSplash} />}
        {!user && !splash && <Onboarding busy={joining} onDone={join} />}
        {user && (screen === "ask" || screen === "calculating") && (
          <header className="topbar">
            <span className="brand">
              <Logo size={22} />
              제주 라스트콜
            </span>
            <div className="clock-wrap">
              <button className="clock-pill" onClick={() => DEMO_ENABLED && setClockMenu(!clockMenu)} type="button">
                {clock.demo ? "데모" : "지금"} {toHHMM(now)}
                {DEMO_ENABLED && <Icon name="chevron" size={12} />}
              </button>
              {DEMO_ENABLED && clockMenu && (
                <div className="clock-menu" role="menu">
                  <button onClick={() => setDemo(null)} type="button">
                    실제 시각
                  </button>
                  {DEMO_TIMES.map((t) => (
                    <button key={t} onClick={() => setDemo(t)} type="button">
                      데모 {t}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </header>
        )}

        {user && screen === "ask" && (
          <Ask
            apiNow={apiNow}
            areas={areas}
            form={form}
            now={now}
            onSubmit={(mode) => runPlan(mode, undefined, true)}
            onToast={showToast}
            setForm={setForm}
          />
        )}

        {screen === "calculating" && <Calculating form={form} />}

        {screen === "result" && plan && (
          <Result
            form={form}
            loading={loading}
            nowHour={Math.floor(now / 60)}
            onBack={() => setScreen("ask")}
            onMode={(m) => runPlan(m)}
            onReplan={(extra) => runPlan(plan.mode, extra)}
            onStart={() => {
              track("live_start", { mode: plan.mode, stops: plan.stop_ids.length, stop_ids: plan.stop_ids });
              setScreen("live");
              window.scrollTo({ top: 0 });
            }}
            plan={plan}
          />
        )}

        {screen === "live" && plan && (
          <Live
            form={form}
            isDemo={!!clock.demo}
            now={now}
            onExit={() => setScreen("result")}
            onJump={(t) => setClock({ demo: t, anchoredAt: Date.now() })}
            plan={plan}
          />
        )}

        <Toast message={toast} />
      </div>
    </div>
  );
}

function Calculating({ form }: { form: TripForm }) {
  const lines = [
    `비행기 ${form.flightTime} 출발 기준으로 공항 마감 확인`,
    form.rental ? `렌터카 ${form.rentalReturnTime} 반납 시간 반영` : "공항까지 이동 수단 반영",
    `${form.originLabel}에서 갈 수 있는 곳 이동시간 계산`,
    "시간 조건과 장소 조사 결과 확인 중",
  ];
  return (
    <main className="calculating" aria-live="polite">
      <div className="calc-stickers" aria-hidden="true">
        <Sticker className="cs cs--1" rotate={-14} shape="arch" size={92} tone="oreum">
          오름
        </Sticker>
        <Sticker className="cs cs--2" rotate={6} shape="wave" size={92} tone="sea">
          바다
        </Sticker>
        <Sticker className="cs cs--3" rotate={-6} shape="scallop" size={96} tone="tangerine">
          귤밭
        </Sticker>
        <Sticker className="cs cs--4" rotate={-4} shape="teacup" size={92} tone="canola">
          카페
        </Sticker>
        <Sticker className="cs cs--5" rotate={10} shape="basalt" size={78} tone="basalt">
          돌담
        </Sticker>
        <span className="cs-car">
          <Icon name="car" size={20} />
        </span>
      </div>
      <h1 className="title2 title2--center">
        <span>갈 수 있는 곳만</span>
        <strong>계산하고 있어요</strong>
      </h1>
      <ul>
        {lines.map((l, i) => (
          <li key={l} style={{ animationDelay: `${i * 0.22}s` }}>
            <Icon name="check" size={14} /> {l}
          </li>
        ))}
      </ul>
    </main>
  );
}
