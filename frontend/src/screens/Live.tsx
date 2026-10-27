import React, { useEffect, useMemo, useState } from "react";
import { CATEGORY_ICON, Icon } from "../components/Icon";
import { Sticker } from "../components/Sticker";
import { PrimaryButton } from "../components/ui";
import { api, track, kakaoDirections } from "../lib/api";
import { countdownText, durationText, toHHMM, toMin } from "../lib/time";
import type { Check, Plan, TimelineItem, TripForm } from "../types";

type Stage = { kind: "move"; stop: TimelineItem } | { kind: "stay"; stop: TimelineItem } | { kind: "final" } | { kind: "shuttle" } | { kind: "done" };

const AIRPORT = { name: "제주국제공항", lat: 33.5066, lng: 126.4929 };

export function Live({
  plan,
  form,
  now,
  isDemo,
  onJump,
  onExit,
}: {
  plan: Plan;
  form: TripForm;
  now: number;
  isDemo: boolean;
  onJump: (hhmm: string) => void;
  onExit: () => void;
}) {
  const stops = plan.timeline.filter((i) => i.type === "stop");
  const stages = useMemo<Stage[]>(
    () => [...stops.flatMap((s) => [{ kind: "move", stop: s } as Stage, { kind: "stay", stop: s } as Stage]), { kind: "final" }, ...(form.rental ? [{ kind: "shuttle" } as Stage] : []), { kind: "done" }],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [plan],
  );
  const [index, setIndex] = useState(0);
  const [check, setCheck] = useState<Check | null>(null);
  const stage = stages[index];
  const stopIndex = stage.kind === "move" || stage.kind === "stay" ? stops.indexOf(stage.stop) : stops.length;
  const finalCheckpoint = plan.checkpoints[0];
  const airportEta = plan.timeline.find((i) => i.type === "airport")?.time ?? plan.airport_eta;

  // 베타 기록: 코스를 끝까지 따라갔는지
  useEffect(() => {
    if (stage.kind === "done") track("live_done", { mode: plan.mode, stops: stops.length, stop_ids: plan.stop_ids });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage.kind]);

  // 지금 여기서 공항으로 바로 가면? (단계가 바뀔 때마다 다시 계산)
  const nowHHMM = toHHMM(now);
  useEffect(() => {
    if (stage.kind === "done") return;
    if (stage.kind === "shuttle") { setCheck(null); return; }
    let alive = true;
    setCheck(null);
    const placeId = stage.kind === "stay" ? stage.stop.place?.id : stage.kind === "final" ? stops[stops.length - 1]?.place?.id : stops[stopIndex - 1]?.place?.id;
    api
      .check(form, nowHHMM, placeId)
      .then((c) => alive && setCheck(c))
      .catch(() => alive && setCheck(null));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, nowHHMM]);

  const advance = () => {
    const next = stages[index + 1];
    if (isDemo) {
      if (stage.kind === "move") onJump(stage.stop.time!);
      if (stage.kind === "stay") onJump(stage.stop.end_time!);
      if (stage.kind === "final") onJump(form.rental ? plan.timeline.find((i) => i.type === "rental")!.end_time! : airportEta);
      if (stage.kind === "shuttle") onJump(airportEta);
    }
    if (next) setIndex(index + 1);
  };

  if (now < toMin(plan.departure_time)) return (
    <main className="live"><h1>{plan.departure_time}에 출발하는 계획이에요</h1><p>출발 전 여유시간은 {durationText(toMin(plan.departure_time) - now)}이에요. 현재 위치에서 시간을 보내고 계획 시각에 출발해 주세요.</p>
      {isDemo && <PrimaryButton onClick={() => onJump(plan.departure_time)}>데모 출발 시각으로 이동</PrimaryButton>}
      <button className="ghost-btn" onClick={onExit}>계획으로 돌아가기</button>
    </main>
  );

  if (stage.kind === "done")
    return (
      <main className="live live--done">
        <div className="done-mark">
          <Sticker className="done-sticker" rotate={-8} shape="scallop" size={124} tone="tangerine">
            <Icon name="plane" size={36} />
          </Sticker>
          {Array.from({ length: 10 }, (_, i) => (
            <i className="confetti" key={i} style={{ "--i": i } as React.CSSProperties} />
          ))}
        </div>
        <h1 className="title2 title2--center">
          <span>제주에서의 마지막 시간,</span>
          <strong>잘 보내셨나요?</strong>
        </h1>
        <p>
          {stops.length}곳을 들르고 {airportEta}에 공항에 도착했어요.
          <br />
          좋은 비행 되세요.
        </p>
        <div className="done-list">
          {stops.map((s) => (
            <span key={s.title}>
              <Icon name={CATEGORY_ICON[s.place?.category ?? ""] ?? "location"} size={14} /> {s.title}
            </span>
          ))}
        </div>
        <div className="sticky-cta">
          <PrimaryButton onClick={onExit} icon="back" tone="dark">
            처음으로
          </PrimaryButton>
        </div>
      </main>
    );

  let title = "";
  let target = 0;
  let targetLabel = "";
  let destination = AIRPORT;
  let cta = "";
  if (stage.kind === "move") {
    title = stage.stop.title;
    target = toMin(stage.stop.time!);
    targetLabel = "도착 예정";
    destination = { name: stage.stop.title, lat: stage.stop.place!.lat, lng: stage.stop.place!.lng };
    cta = "도착했어요";
  } else if (stage.kind === "stay") {
    title = stage.stop.title;
    target = toMin(stage.stop.leave_by!);
    targetLabel = "여기서 늦어도";
    const next = stops[stopIndex + 1];
    destination = next ? { name: next.title, lat: next.place!.lat, lng: next.place!.lng } : form.rental && plan.rental_hub ? plan.rental_hub : AIRPORT;
    cta = next ? "다음 장소로 출발" : form.rental ? "렌터카 반납하러 출발" : "공항으로 출발";
  } else if (stage.kind === "shuttle") {
    title = "셔틀로 제주공항 이동";
    target = toMin(airportEta);
    targetLabel = "공항 도착 예정";
    destination = AIRPORT;
    cta = "공항에 도착했어요";
  } else {
    title = form.rental ? "렌터카 반납 → 공항" : "제주공항";
    target = form.rental ? toMin(plan.timeline.find((i) => i.type === "rental")!.time!) : toMin(finalCheckpoint.time);
    targetLabel = form.rental ? "반납 지점 계획 도착" : "공항 도착 목표";
    destination = form.rental && plan.rental_hub ? plan.rental_hub : AIRPORT;
    cta = form.rental ? "렌터카 반납을 마쳤어요" : "공항에 도착했어요";
  }
  const remaining = target - now;
  const urgent = stage.kind === "stay" && remaining < 15;
  const over = remaining < 0;

  return (
    <main className="live">
      <header className="appbar">
        <button aria-label="코스로 돌아가기" className="icon-btn" onClick={onExit} type="button">
          <Icon name="close" size={18} />
        </button>
        <span className="appbar__title">진행 중</span>
        <span className="clock-pill">{nowHHMM}</span>
      </header>

      <ol className="live-steps">
        {stops.map((s, i) => (
          <li className={i < stopIndex ? "is-done" : i === stopIndex ? "is-now" : ""} key={s.title}>
            <span>{i < stopIndex ? <Icon name="check" size={12} /> : i + 1}</span>
            <small>{s.title}</small>
          </li>
        ))}
        <li className={stage.kind === "final" ? "is-now" : ""}>
          <span>
            <Icon name="plane" size={12} />
          </span>
          <small>공항</small>
        </li>
      </ol>

      <section className={`live-card live-card--${stage.kind} ${urgent ? "is-urgent" : ""} ${over ? "is-over" : ""}`}>
        <Sticker
          className="live-card__sticker"
          rotate={stage.kind === "move" ? 6 : -6}
          shape={stage.kind === "stay" ? "teacup" : stage.kind === "move" ? "wave" : "arch"}
          size={70}
          tone={stage.kind === "stay" ? "canola" : stage.kind === "move" ? "sea" : "oreum"}
        />
        <span className="live-card__state">
          {stage.kind === "move" ? "이동 중" : stage.kind === "stay" ? "머무는 중" : "마지막 이동"}
        </span>
        <h1>{title}</h1>
        <div className="countdown">
          <span>
            {targetLabel} <b>{toHHMM(target)}</b>
            {stage.kind === "stay" ? " 출발" : ""}
          </span>
          <strong className={urgent || over ? "is-beating" : ""} key={stage.kind + index}>
            {over ? "시간이 지났어요" : countdownText(remaining)}
          </strong>
          {stage.kind === "stay" && (
            <small>
              계획은 {stage.stop.end_time} 출발이에요. {over ? "지금 바로 출발하세요." : "체류를 늘리려면 매장 이용 조건도 확인해 주세요."}
            </small>
          )}
        </div>
      </section>

      {check && (
        <section className={`quick-check quick-check--${check.status}`}>
          <Icon name="plane" size={16} />
          <p>
            <small>지금 바로 {form.rental ? "반납하고 " : ""}공항 가면</small>
            <b>
              {check.airport_eta} 도착 ·{" "}
              {check.margin_min >= 0 ? `${durationText(check.margin_min)} 여유` : `${durationText(-check.margin_min)} 늦음`}
            </b>
          </p>
        </section>
      )}

      <section className="next-dest">
        <span>{stage.kind === "move" ? "가는 곳" : "다음 목적지"}</span>
        <strong>{destination.name}</strong>
        <a className="chip-btn chip-btn--dark" href={kakaoDirections(destination.name, destination.lat, destination.lng)} rel="noreferrer" target="_blank">
          <Icon name="map" size={14} /> 길찾기
        </a>
      </section>

      {isDemo && <p className="demo-note">데모 모드: 버튼을 누르면 시계가 계획된 시각으로 넘어가요</p>}

      <div className="sticky-cta">
        <PrimaryButton onClick={advance} icon={stage.kind === "final" ? "check" : "arrow"} tone="orange">
          {cta}
        </PrimaryButton>
      </div>
    </main>
  );
}
