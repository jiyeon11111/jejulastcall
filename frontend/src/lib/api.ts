import type { Area, Check, Mode, Plan, PlaceDetail, TripForm, RentalHub } from "../types";

const BASE: string = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
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
};

export const kakaoDirections = (name: string, lat: number, lng: number) =>
  `https://map.kakao.com/link/to/${encodeURIComponent(name)},${lat},${lng}`;
