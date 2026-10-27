import { useState } from "react";
import { Sticker } from "./Sticker";
import { Logo, PrimaryButton } from "./ui";

/**
 * 베타 시작 화면: 닉네임 + 개인정보 수집·이용 동의.
 * 실명·연락처는 받지 않는다. 닉네임과 이용 기록만 익명 ID로 묶어 저장한다.
 */
export function Onboarding({ onDone, busy }: { onDone: (nickname: string) => void; busy: boolean }) {
  const [nickname, setNickname] = useState("");
  const [agree, setAgree] = useState(false);
  const [open, setOpen] = useState(false);
  const name = nickname.trim();
  const ready = name.length > 0 && agree && !busy;

  return (
    <main className="onboard">
      <div className="onboard__hero">
        <Sticker className="onboard__sticker" rotate={-10} shape="scallop" size={88} tone="tangerine">
          베타
        </Sticker>
        <Logo animate size={64} />
        <h1 className="title2">
          <span>떠나기 전 남은 시간,</span>
          <strong>제주 라스트콜 베타</strong>
        </h1>
        <p className="onboard__lead">
          비행기 시간에 맞춰 갈 수 있는 곳만 골라 드려요. 써 보신 기록과 의견은 서비스를 다듬는 데 쓰여요.
        </p>
      </div>

      <label className="onboard__field">
        <span>닉네임</span>
        <input
          autoComplete="nickname"
          maxLength={20}
          onChange={(e) => setNickname(e.target.value)}
          placeholder="예: 귤좋아"
          type="text"
          value={nickname}
        />
        <small>실명이 아니어도 돼요. 20자 이내로 정해 주세요.</small>
      </label>

      <div className="consent">
        <label className="consent__row">
          <input checked={agree} onChange={(e) => setAgree(e.target.checked)} type="checkbox" />
          <span>
            <b>[필수]</b> 개인정보 수집·이용에 동의해요
          </span>
        </label>
        <button aria-expanded={open} className="consent__more" onClick={() => setOpen(!open)} type="button">
          {open ? "내용 접기" : "내용 보기"}
        </button>
        {open && (
          <dl className="consent__body">
            <div>
              <dt>수집 항목</dt>
              <dd>닉네임, 앱 이용 기록(입력한 비행기 시간·출발 지역·모드, 추천된 코스, 장소 바꾸기·상세 보기, 평가와 의견), 접속 시각</dd>
            </div>
            <div>
              <dt>수집하지 않는 것</dt>
              <dd>이름, 연락처, 이메일, 정확한 위치 좌표</dd>
            </div>
            <div>
              <dt>이용 목적</dt>
              <dd>2026 제주 관광 데이터 활용사례 공모전 출품 서비스의 사용성 검증과 개선, 통계 작성</dd>
            </div>
            <div>
              <dt>보유 기간</dt>
              <dd>공모전 종료 후 2026년 12월 31일까지 보관한 뒤 파기</dd>
            </div>
            <div>
              <dt>동의 거부</dt>
              <dd>동의하지 않을 수 있으며, 이 경우 베타 앱을 이용할 수 없어요.</dd>
            </div>
            <div>
              <dt>운영</dt>
              <dd>돌담랩 팀 (2026 제주 관광 데이터 활용사례 공모전 참가팀)</dd>
            </div>
          </dl>
        )}
      </div>

      <div className="sticky-cta">
        <PrimaryButton disabled={!ready} onClick={() => onDone(name)}>
          {busy ? "시작하는 중…" : "시작하기"}
        </PrimaryButton>
      </div>
    </main>
  );
}
