import type { Area, Check, Mode, Plan, PlaceDetail, TripForm, RentalHub } from "../types";

import { loadUser, sessionId } from "./session";

const BASE: string = import.meta.env.VITE_API_BASE ?? "";

/** 베타 사용 기록용: 시작 화면에서 정한 익명 ID와 방문 ID를 모든 요청에 붙인다 */
function trackingHeaders(): Record<string, string> {
  const user = loadUser();
  return user ? { "X-User-Id": user.id, "X-Session-Id": sessionId() } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...trackingHeaders() },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (body as { detail?: unknown }).detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? String((detail[0] as { msg?: string })?.msg ?? "입력값을 확인해 주세요").replace(/^Value error, /, "")
          : "잠시 후 다시 시도해 주세요";
    throw new Error(message);
  }
  return body as T;
}

export function tripPayload(form: TripForm, now: string | null) {
  return {
    flight_time: form.flightTime,
    has_baggage: form.hasBaggage ?? true,
    rental: !!form.rental,
    rental_return_time: form.rental ? form.rentalReturnTime : null,
    rental_hub_id: form.rental ? form.rentalHubId : null,
    rental_location_confirmed: form.rentalLocationConfirmed,
    rental_process_min: form.rentalProcessMin,
    rental_shuttle_min: form.rentalShuttleMin,
    airport_arrival_time: form.airportArrivalTime,
    transport: form.rental ? null : form.transport,
    origin_area: form.originArea,
    origin_lat: form.originArea ? null : form.originLat,
    origin_lng: form.originArea ? null : form.originLng,
    now,
  };
}

export const api = {
  areas: () => request<Area[]>("/api/areas"),
  rentalHubs: () => request<RentalHub[]>("/api/rental-hubs"),
  plan: (form: TripForm, now: string | null, mode: Mode, extra?: { sequence?: string[]; exclude?: string[]; departure_strategy?: "now" | "later"; meal_preference?: "auto" | "include" | "skip" }) =>
    request<Plan>("/api/plan", {
      method: "POST",
      body: JSON.stringify({ ...tripPayload(form, now), mode, ...extra }),
    }),
  check: (form: TripForm, now: string | null, placeId?: string) =>
    request<Check>("/api/check", {
      method: "POST",
      body: JSON.stringify({ ...tripPayload(form, now), place_id: placeId ?? null }),
    }),
  place: (id: string, hour: number, transport: string) =>
    request<PlaceDetail>(`/api/places/${id}?hour=${hour}&transport=${transport}`),
  register: (userId: string, nickname: string, consentVersion: string) =>
    request<{ ok: boolean; tracking: boolean }>("/api/users", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, nickname, consent: true, consent_version: consentVersion }),
    }),
  feedback: (body: FeedbackBody) =>
    request<{ ok: boolean }>("/api/feedback", { method: "POST", body: JSON.stringify(body) }),
};

export interface FeedbackBody {
  rating: number;
  comment: string;
  would_use: boolean | null;
  mode: string;
  stop_ids: string[];
  stop_names: string[];
  unfilled_min: number;
  origin_area: string | null;
  flight_time: string | null;
}

export type TrackEvent = "app_open" | "live_start" | "live_done" | "place_detail" | "directions_click" | "swap_open";

/** 사용 기록 한 줄. 기다리지 않고, 실패해도 화면에는 아무 영향이 없다. */
export function track(type: TrackEvent, payload: Record<string, unknown> = {}): void {
  if (!loadUser()) return;
  fetch(`${BASE}/api/events`, {
    method: "POST",
    keepalive: true,
    headers: { "Content-Type": "application/json", ...trackingHeaders() },
    body: JSON.stringify({ type, payload }),
  }).catch(() => undefined);
}

export const kakaoDirections = (name: string, lat: number, lng: number) =>
  `https://map.kakao.com/link/to/${encodeURIComponent(name)},${lat},${lng}`;
