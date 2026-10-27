/** 베타 사용자 정보 — 닉네임과 익명 ID만 이 기기 브라우저에 저장한다. */

export const CONSENT_VERSION = "beta-2026-10-27";

export interface BetaUser {
  id: string;
  nickname: string;
  consentVersion: string;
  registered: boolean; // 서버에 등록 요청이 성공했는지 (실패하면 다음 접속 때 다시 시도)
}

const USER_KEY = "lastcall.user";
const SESSION_KEY = "lastcall.session";

function uuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

// 저장소를 못 쓰는 환경(사생활 보호 모드 등)에서도 이번 방문 동안은 동작하도록 메모리에 같이 둔다
let memoryUser: BetaUser | null = null;
let memorySession: string | null = null;

export function loadUser(): BetaUser | null {
  try {
    const raw = window.localStorage.getItem(USER_KEY);
    if (raw) {
      const u = JSON.parse(raw) as BetaUser;
      if (u && u.id && u.nickname && u.consentVersion === CONSENT_VERSION) return u;
    }
  } catch {
    /* 저장소 사용 불가 */
  }
  return memoryUser;
}

export function saveUser(user: BetaUser): void {
  memoryUser = user;
  try {
    window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    /* 저장소 사용 불가 */
  }
}

export function newUser(nickname: string): BetaUser {
  const existing = loadUser();
  return { id: existing?.id ?? uuid(), nickname: nickname.trim(), consentVersion: CONSENT_VERSION, registered: false };
}

export function clearUser(): void {
  memoryUser = null;
  try {
    window.localStorage.removeItem(USER_KEY);
  } catch {
    /* 저장소 사용 불가 */
  }
}

/** 탭(방문) 단위 ID — 한 번 방문에서 몇 번 계산했는지 묶어 보는 용도 */
export function sessionId(): string {
  if (memorySession) return memorySession;
  try {
    const s = window.sessionStorage.getItem(SESSION_KEY);
    if (s) return (memorySession = s);
    memorySession = uuid();
    window.sessionStorage.setItem(SESSION_KEY, memorySession);
  } catch {
    memorySession = memorySession ?? uuid();
  }
  return memorySession;
}
