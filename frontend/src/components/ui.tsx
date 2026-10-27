import { useEffect, useId, type ReactNode } from "react";
import type { Badge } from "../types";
import { Icon, type IconName } from "./Icon";

/**
 * 팀 확정 시안: 노을 시계 로고
 * animate: 시계 바늘이 천천히 돌고, 해가 수평선 아래로 내려갔다 올라오는 모션 (히어로용)
 */
export function Logo({ size = 24, animate = false, className = "" }: { size?: number; animate?: boolean; className?: string }) {
  const clipId = useId();
  return (
    <svg aria-label="제주 라스트콜" className={`logo ${animate ? "logo--animate" : ""} ${className}`} height={size} role="img" viewBox="0 0 120 92" width={size * 1.3}>
      <defs>
        <clipPath id={clipId}>
          <rect height="51" width="120" x="0" y="0" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${clipId})`}>
        <path className="logo-sun" d="M26 50a34 34 0 0 1 68 0Z" fill="#F07B2F" />
      </g>
      <path d="M17 51h86" fill="none" stroke="#33383B" strokeLinecap="round" strokeWidth="6" />
      <path d="M60 16v7" fill="none" stroke="#fff" strokeLinecap="round" strokeWidth="4" />
      <path className="logo-hand" d="m43 30 17 21 13-17" fill="none" stroke="#33383B" strokeLinecap="round" strokeLinejoin="round" strokeWidth="6" />
      <circle cx="60" cy="51" fill="#33383B" r="6" />
      <path d="M28 67c8-7 16-7 24 0s16 7 24 0 16-7 24 0" fill="none" stroke="#1A9C9A" strokeLinecap="round" strokeWidth="6" />
      <path d="M35 82c7-5 14-5 21 0s14 5 21 0 14-5 21 0" fill="none" stroke="#1A9C9A" strokeLinecap="round" strokeWidth="6" />
    </svg>
  );
}

export function Badges({ items, limit }: { items: Badge[]; limit?: number }) {
  const shown = limit ? items.slice(0, limit) : items;
  return (
    <div className="badges">
      {shown.map((b) => (
        <span className={`badge badge--${b.tone}`} key={b.text}>
          {b.text}
        </span>
      ))}
    </div>
  );
}

export function PrimaryButton({
  children,
  onClick,
  disabled,
  icon = "arrow",
  tone = "orange",
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  icon?: IconName | null;
  tone?: "orange" | "dark" | "teal";
}) {
  return (
    <button className={`cta cta--${tone}`} disabled={disabled} onClick={onClick} type="button">
      <span>{children}</span>
      {icon && (
        <span className="arrow-box">
          <Icon name={icon} size={18} />
        </span>
      )}
    </button>
  );
}

export function BottomSheet({
  open,
  onClose,
  children,
  title,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  title?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <div className={`sheet-layer ${open ? "is-open" : ""}`} aria-hidden={!open}>
      <button aria-label="닫기" className="sheet-backdrop" onClick={onClose} tabIndex={-1} type="button" />
      <section aria-modal="true" className="sheet" role="dialog" aria-label={title}>
        <div className="sheet__handle" />
        {title && (
          <header className="sheet__header">
            <h2>{title}</h2>
            <button aria-label="닫기" className="icon-btn" onClick={onClose} type="button">
              <Icon name="close" size={18} />
            </button>
          </header>
        )}
        <div className="sheet__body">{open && children}</div>
      </section>
    </div>
  );
}

export function Toast({ message }: { message: string | null }) {
  return (
    <div aria-live="polite" className={`toast ${message ? "is-on" : ""}`}>
      {message}
    </div>
  );
}
