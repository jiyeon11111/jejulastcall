import { useEffect, useState } from "react";
import { Logo } from "./ui";
import backdrop from "../assets/sunset-bg.png";

/**
 * 앱 시작 화면 (스플래시): 노을 바다 그림을 배경으로 깔고, 그림이 천천히 떠다니는 모션을 준다.
 * 로고는 시계 바늘이 돌고 해가 수평선 아래로 지는 모션 그대로.
 */
export function Splash({ onDone, duration = 2600 }: { onDone: () => void; duration?: number }) {
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    const leave = window.setTimeout(() => setLeaving(true), duration);
    const done = window.setTimeout(onDone, duration + 600);
    return () => {
      window.clearTimeout(leave);
      window.clearTimeout(done);
    };
  }, [duration, onDone]);

  return (
    <div
      aria-label="제주 라스트콜 시작 화면"
      className={`splash ${leaving ? "is-leaving" : ""}`}
      role="status"
      style={{ ["--splash-bg" as string]: `url(${backdrop})` }}
    >
      <div className="splash__brand">
        <Logo animate size={96} />
        <h1>제주 라스트콜</h1>
        <p>떠나기 전 남은 시간을,<br />덜 알려진 제주에서</p>
      </div>
    </div>
  );
}
