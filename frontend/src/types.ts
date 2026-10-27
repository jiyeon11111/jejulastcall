export type Mode = "tour" | "work" | "rest";
export type Transport = "car" | "taxi" | "bus";
export type Tone = "good" | "warn" | "neutral";
export type Status = "safe" | "tight" | "late";

export interface TripForm {
  flightTime: string | null;
  hasBaggage: boolean | null;
  rental: boolean | null;
  rentalReturnTime: string | null;
  rentalHubId: string | null;
  rentalHubLabel: string | null;
  rentalLocationConfirmed: boolean;
  rentalProcessMin: number;
  rentalShuttleMin: number;
  airportArrivalTime: string | null;
  transport: Transport | null;
  originArea: string | null;
  originLat: number | null;
  originLng: number | null;
  originLabel: string | null;
}

export interface Area {
  id: string;
  name: string;
  region: string;
  lat: number;
  lng: number;
}

export interface Badge {
  text: string;
  tone: Tone;
}

export interface RentalHub {
  id: string;
  name: string;
  address: string;
  lat: number;
  lng: number;
  return_verified: boolean;
}

export interface PlaceBrief {
  id: string;
  name: string;
  region: string;
  category: string;
  category_label: string;
  lat: number;
  lng: number;
  station: boolean;
  /** 팀이 확인한 실제 장소인지. source: kakao-map-2026-09-28 | real-name-unverified | placeholder */
  verified: boolean;
  source: string;
  kakao_reviews: number | null;
}

export interface TimelineItem {
  type: "start" | "move" | "stop" | "rental" | "airport";
  time: string | null;
  end_time: string | null;
  title: string;
  subtitle: string | null;
  minutes: number | null;
  transport: Transport | null;
  stop_index: number | null;
  place: PlaceBrief | null;
  badges: Badge[];
  reason: string | null;
  leave_by: string | null;
}

export interface Alternative {
  place: PlaceBrief;
  margin_min: number;
  margin_delta: number;
  badges: Badge[];
}

export interface Reachable {
  place: PlaceBrief;
  travel_min: number;
  arrive: string;
  max_stay_min: number;
  leave_by: string;
  badges: Badge[];
}

export interface Checkpoint {
  label: string;
  time: string;
  eta: string;
  margin_min: number;
}

export interface Plan {
  meal_preference: "auto" | "include" | "skip";
  unfilled_min: number;
  planning_notes: string[];
  now: string;
  departure_time: string;
  departure_strategy: "now" | "later";
  wait_before_departure_min: number;
  rental_hub: RentalHub | null;
  mode: Mode;
  status: Status;
  headline: string;
  subline: string;
  margin_min: number;
  buffer_min: number;
  free_min: number;
  expansion: boolean;
  airport_eta: string;
  checkpoints: Checkpoint[];
  direct_travel_min: number;
  timeline: TimelineItem[];
  stop_ids: string[];
  alternatives: Record<string, Alternative[]>;
  reachable: Reachable[];
  data_source: "sample" | "analysis";
}

export interface Check {
  now: string;
  status: Status;
  message: string;
  travel_min: number;
  airport_eta: string;
  margin_min: number;
  latest_departure: string;
  free_min: number;
  checkpoints: Checkpoint[];
}

export interface HourValue {
  hour: number;
  value: number;
  level: "low" | "mid" | "high";
}

export interface PlaceDetail {
  place: PlaceBrief;
  badges: Badge[];
  hourly: HourValue[];
  best_hours: number[];
  stay_text: string;
  to_airport_min: number;
  facilities: Record<string, string>;
  evidence: Record<string, number | string>;
}
