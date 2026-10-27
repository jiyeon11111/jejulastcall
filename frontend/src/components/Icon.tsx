import type { ReactNode } from "react";

export type IconName =
  | "arrow"
  | "back"
  | "bag"
  | "briefcase"
  | "bus"
  | "car"
  | "chart"
  | "check"
  | "chevron"
  | "clock"
  | "close"
  | "coffee"
  | "compass"
  | "crosshair"
  | "edit"
  | "flag"
  | "info"
  | "leaf"
  | "location"
  | "map"
  | "minus"
  | "navigate"
  | "plane"
  | "plug"
  | "route"
  | "sparkle"
  | "swap"
  | "walk"
  | "wave"
  | "utensils";

const PATHS: Record<IconName, ReactNode> = {
  arrow: (
    <>
      <path d="M5 12h14" />
      <path d="m14 7 5 5-5 5" />
    </>
  ),
  back: <path d="m15 18-6-6 6-6" />,
  bag: (
    <>
      <rect x="5" y="7" width="14" height="13" rx="2" />
      <path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M9 20v1M15 20v1" />
    </>
  ),
  briefcase: (
    <>
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18" />
    </>
  ),
  bus: (
    <>
      <rect x="4" y="3" width="16" height="15" rx="3" />
      <path d="M4 11h16M8 18v3M16 18v3M8 14.5h.01M16 14.5h.01" />
    </>
  ),
  car: (
    <>
      <path d="m5 11 1.4-4.1A2 2 0 0 1 8.3 5h7.4a2 2 0 0 1 1.9 1.9L19 11" />
      <rect x="3" y="10" width="18" height="8" rx="2" />
      <path d="M6 18v2M18 18v2M7 14h.01M17 14h.01" />
    </>
  ),
  chart: <path d="M4 19V9M10 19V5M16 19v-7M22 19V3" />,
  check: <path d="m5 12 4 4L19 6" />,
  chevron: <path d="m9 18 6-6-6-6" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  close: <path d="M6 6l12 12M18 6 6 18" />,
  coffee: (
    <>
      <path d="M4 8h13v6a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V8Z" />
      <path d="M17 10h1a3 3 0 0 1 0 6h-2M8 3v2M12 3v2" />
    </>
  ),
  compass: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m15.5 8.5-2.1 4.9-4.9 2.1 2.1-4.9 4.9-2.1Z" />
    </>
  ),
  crosshair: (
    <>
      <circle cx="12" cy="12" r="7" />
      <circle cx="12" cy="12" r="2.5" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
    </>
  ),
  edit: <path d="M4 20h4L19 9l-4-4L4 16v4ZM13.5 6.5l4 4" />,
  flag: <path d="M5 21V4M5 4h11l-2 4 2 4H5" />,
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </>
  ),
  leaf: (
    <>
      <path d="M5 19c0-8 5-13 14-14 0 9-5 14-13 14H5Z" />
      <path d="M5 19 13 11" />
    </>
  ),
  location: (
    <>
      <path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" />
      <circle cx="12" cy="10" r="2.5" />
    </>
  ),
  map: (
    <>
      <path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z" />
      <path d="M9 3v15M15 6v15" />
    </>
  ),
  minus: <path d="M6 12h12" />,
  navigate: <path d="M3 11 21 3l-8 18-2-8-8-2Z" />,
  plane: <path d="M10.5 3.5c.8-.8 2.2-.8 3 0s.8 2.2 0 3L10 10l2 9-2 2-4-7-3.5 3.5L3 19l-2-1 1.5-1.5L6 13 1 9l2-2 9 2 3.5-3.5" />,
  plug: <path d="M8 12h8v3a4 4 0 0 1-8 0v-3ZM10 12V7M14 12V7M12 19v3" />,
  route: (
    <>
      <circle cx="6" cy="18" r="2" />
      <circle cx="18" cy="6" r="2" />
      <path d="M8 18h2a2 2 0 0 0 2-2V8a2 2 0 0 1 2-2h2" />
    </>
  ),
  sparkle: <path d="m12 3 1.6 5.4L19 10l-5.4 1.6L12 17l-1.6-5.4L5 10l5.4-1.6L12 3Z" />,
  swap: <path d="M7 4 3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7" />,
  walk: (
    <>
      <circle cx="13" cy="4" r="2" />
      <path d="m10 22 2-7-3-3 2-4 4 3h4M8 16l-3 6M13 15l4 7" />
    </>
  ),
  wave: <path d="M2 12c2.5-3 5-3 7.5 0s5 3 7.5 0 3.5-3 5 0M2 18c2.5-3 5-3 7.5 0s5 3 7.5 0 3.5-3 5 0M12 3v4" />,
  utensils: <path d="M7 3v8M4 3v5a3 3 0 0 0 6 0V3M7 11v10M17 21V3c-2 1-3 4-3 7h3" />,
};

export function Icon({ name, size = 20, stroke = 2 }: { name: IconName; size?: number; stroke?: number }) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height={size}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={stroke}
      viewBox="0 0 24 24"
      width={size}
    >
      {PATHS[name]}
    </svg>
  );
}

export const CATEGORY_ICON: Record<string, IconName> = {
  beach: "wave",
  oreum: "flag",
  walk: "walk",
  forest: "leaf",
  heritage: "compass",
  restaurant: "utensils",
  museum: "compass",
  cafe: "coffee",
};

export const TRANSPORT_ICON: Record<string, IconName> = { car: "car", taxi: "car", bus: "bus" };
export const TRANSPORT_LABEL: Record<string, string> = { car: "차로", taxi: "택시로", bus: "버스로" };
