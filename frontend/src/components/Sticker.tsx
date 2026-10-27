import type { CSSProperties, ReactNode } from "react";

/**
 * 제주 도형 스티커
 * - arch    오름: 둥근 언덕
 * - wave    바다: 말려 올라가는 파도 + 물결 두 줄
 * - scallop 귤: 꽃잎 테두리
 * - teacup  카페: 손잡이 없는 우리 전통 찻잔 (넓은 입구 · 둥근 몸 · 낮은 굽 · 김)
 * - basalt  돌담: 숭숭 구멍 난 현무암 돌
 */
export type Shape = "arch" | "wave" | "scallop" | "teacup" | "basalt";
export type Tone = "tangerine" | "sea" | "canola" | "oreum" | "camellia" | "basalt" | "stone" | "white";

type Layer = { kind: "body" | "rounded" | "shade" | "hole" | "steam"; d: string };

const circle = (cx: number, cy: number, r: number) => `M${cx - r},${cy} a${r},${r} 0 1,0 ${2 * r},0 a${r},${r} 0 1,0 ${-2 * r},0 Z`;
const ellipse = (cx: number, cy: number, rx: number, ry: number) =>
  `M${cx - rx},${cy} a${rx},${ry} 0 1,0 ${2 * rx},0 a${rx},${ry} 0 1,0 ${-2 * rx},0 Z`;

function scallopPath(points = 12, r = 44, depth = 5) {
  let d = "";
  for (let i = 0; i <= 180; i++) {
    const t = (i / 180) * Math.PI * 2;
    const rr = r + depth * Math.cos(points * t);
    d += `${i ? "L" : "M"}${(50 + rr * Math.cos(t)).toFixed(2)},${(50 + rr * Math.sin(t)).toFixed(2)}`;
  }
  return `${d}Z`;
}

const SHAPES: Record<Shape, Layer[]> = {
  arch: [{ kind: "body", d: "M4,94 C4,40 26,8 50,8 C74,8 96,40 96,94 Z" }],
  wave: [
    {
      kind: "body",
      d: "M4,92 L4,56 C4,40 14,30 28,30 C36,30 41,35 41,42 C41,47 37,50 33,49 C38,40 30,36 26,40 C20,46 22,58 32,60 C48,63 52,34 66,22 C76,14 92,16 96,28 C88,22 78,26 76,36 C74,46 84,52 96,48 L96,92 C96,95 94,96 92,96 L8,96 C6,96 4,95 4,92 Z",
    },
    { kind: "shade", d: "M4,74 C14,66 24,66 34,72 C44,78 56,78 66,72 C76,66 88,66 96,72 L96,80 C88,74 76,74 66,80 C56,86 44,86 34,80 C24,74 14,74 4,82 Z" },
    { kind: "shade", d: "M4,88 C14,82 24,82 34,87 C44,92 56,92 66,87 C76,82 88,82 96,87 L96,92 C96,95 94,96 92,96 L8,96 C6,96 4,95 4,92 Z" },
  ],
  scallop: [{ kind: "body", d: scallopPath() }],
  teacup: [
    {
      kind: "body",
      d: "M6,36 C6,30 26,27 50,27 C74,27 94,30 94,36 C94,62 80,80 66,84 L68,92 C68,94 66,95 64,95 L36,95 C34,95 32,94 32,92 L34,84 C20,80 6,62 6,36 Z",
    },
    { kind: "shade", d: ellipse(50, 35, 40, 6.5) },
    { kind: "hole", d: ellipse(50, 36, 33, 4.2) },
    { kind: "shade", d: "M28,46 C30,60 38,70 48,74 C40,74 30,64 28,46 Z" },
    { kind: "steam", d: "M40,22 C36,17 44,13 40,7" },
    { kind: "steam", d: "M56,22 C52,17 60,13 56,7" },
  ],
  basalt: [
    { kind: "rounded", d: "M20,16 L48,8 L76,12 L92,30 L94,60 L84,84 L58,94 L28,92 L10,78 L6,46 Z" },
    ...[
      [30, 32, 5],
      [62, 26, 3.5],
      [74, 48, 6],
      [44, 52, 3.2],
      [24, 64, 3.8],
      [56, 74, 4.6],
      [78, 72, 2.8],
      [40, 80, 2.4],
      [50, 36, 2.2],
    ].map(([x, y, r]) => ({ kind: "hole" as const, d: circle(x, y, r) })),
  ],
};

export function Sticker({
  shape,
  tone,
  size = 64,
  rotate = 0,
  children,
  className = "",
  style,
}: {
  shape: Shape;
  tone: Tone;
  size?: number;
  rotate?: number;
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <span
      aria-hidden="true"
      className={`sticker sticker--${shape} tone-${tone} ${className}`}
      style={{ width: size, height: size, ["--rot" as string]: `${rotate}deg`, ...style }}
    >
      <svg viewBox="0 0 100 100">
        {SHAPES[shape].map((l, i) => (
          <path className={`l-${l.kind}`} d={l.d} key={i} />
        ))}
      </svg>
      {children && <span className="sticker__text">{children}</span>}
    </span>
  );
}

/** 장소 카테고리 → 카드 색 */
export const CATEGORY_TONE: Record<string, Tone> = {
  beach: "sea",
  oreum: "oreum",
  forest: "oreum",
  walk: "oreum",
  heritage: "stone",
  restaurant: "tangerine",
  museum: "stone",
  cafe: "canola",
};
