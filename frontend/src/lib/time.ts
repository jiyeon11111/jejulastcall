export const toMin = (hhmm: string) => {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
};

export const toHHMM = (min: number) => {
  const v = Math.max(0, Math.min(24 * 60 - 1, Math.round(min)));
  return `${String(Math.floor(v / 60)).padStart(2, "0")}:${String(v % 60).padStart(2, "0")}`;
};

export const durationText = (min: number) => {
  const v = Math.max(0, Math.round(min));
  const h = Math.floor(v / 60);
  const m = v % 60;
  if (h && m) return `${h}시간 ${m}분`;
  if (h) return `${h}시간`;
  return `${m}분`;
};

/** 시계 시각과 헷갈리지 않게 '2시간 29분 남음', '10분 46초 남음' 형태로 */
export const countdownText = (min: number) => {
  if (min <= 0) return "지금";
  const total = Math.floor(min * 60);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h) return `${h}시간 ${m}분 남음`;
  return `${m}분 ${String(s).padStart(2, "0")}초 남음`;
};

/** 실제 시각 또는 데모 시각. 데모는 고정 시각에서 실제 시간 흐름만큼 흘러간다. */
export interface Clock {
  demo: string | null; // "11:00" 이면 데모, null 이면 실제 시각
  anchoredAt: number; // Date.now() 기준점
}

export const clockNow = (clock: Clock): number => {
  if (!clock.demo) {
    const d = new Date();
    return d.getHours() * 60 + d.getMinutes() + d.getSeconds() / 60;
  }
  return toMin(clock.demo) + (Date.now() - clock.anchoredAt) / 60000;
};
