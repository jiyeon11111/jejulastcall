"""
제주 라스트콜 · 분석 스크립트 (3주차, 10/5 회의 반영본)
========================================================
10/5 회의 지적 두 건을 반영해서 고침:
  (가) 기준월 불일치   → coverage 명령 추가. 기준월 안 맞으면 계산 자체를 막음
  (나) 외부 데이터 난항 → 지표 2+1 구조. 유휴 카페 제거, 장소 적합성(직접 수집)으로 대체

명령
  python lastcall_analysis.py coverage integrated_v1.csv   # ① 기준월 진단 — 제일 먼저
  python lastcall_analysis.py quad     integrated_v1.csv   # ② 4분면 + 도착 집중도
  python lastcall_analysis.py sim      places.csv quadrant_12m.csv  # ③ 공항 준수율
  python lastcall_analysis.py demo                          # 가짜 데이터로 동작 확인

COLS의 오른쪽 값만 integrated_v1 실제 컬럼명으로 바꾸면 됨.
"""
import os
import sys
import numpy as np
import pandas as pd

# ── 0. 컬럼 매핑 (예림 기준 합의표 나오면 여기만 수정) ─────────────
COLS = {
    "ym":       "기준연월",           # 202607 또는 2026-07
    "region":   "읍면동",             # 43개 읍면동
    "visitors": "방문객수",            # SKT 추정 방문객  ← R의 분모
    "spend":    "관광객카드소비액",     # 도민 제외 관광객 카드 소비(원) ← R의 분자
    "arrivals": "관광객차량도착건수",   # TMAP 월간 차량 도착 ← 도착 집중도
}
REQUIRED = ["visitors", "spend"]      # 이 둘은 같은 달이어야 R이 성립
OPTIONAL = ["arrivals"]
FOCUS = ["조천읍", "구좌읍"]
OUT = "out"

# ── 지표 2+1 구조 (10/5 회의 결정) ─────────────────────────────
#   데이터 지표 2개: I_spend(방문 대비 소비), I_arrive(월간 차량 도착 집중도)
#   직접 수집 1개 : fit(장소 적합성) — 유휴 카페 지표를 대체
WEIGHTS = {
    "관광": {"spend": 0.35, "low_crowd": 0.25, "fit": 0.20, "travel": -0.20},
    "일":   {"spend": 0.10, "low_crowd": 0.15, "fit": 0.60, "travel": -0.15},
    "휴식": {"spend": 0.10, "low_crowd": 0.40, "fit": 0.35, "travel": -0.15},
}


# ══════════════════════════════════════════════════════════════
# 1. 기준월 진단  (10/5 지적 '가' 대응)
# ══════════════════════════════════════════════════════════════
def read_raw(path):
    df = pd.read_csv(path)
    have = {k: v for k, v in COLS.items() if v in df.columns}
    missing = [k for k in ["ym", "region"] + REQUIRED if k not in have]
    if missing:
        raise SystemExit(f"[중단] 필수 컬럼 없음: {[COLS[m] for m in missing]}\n"
                         f"       파일의 컬럼: {list(df.columns)}\n"
                         f"       → 스크립트 맨 위 COLS를 실제 컬럼명으로 고칠 것")
    df = df.rename(columns={v: k for k, v in have.items()})
    df["ym"] = pd.to_datetime(df["ym"].astype(str).str.replace("-", "").str[:6], format="%Y%m")
    return df


def coverage(path, months=12, verbose=True):
    """컬럼별 가능 기간을 뽑아 공통 구간·대표 단월을 정한다. quad는 이걸 먼저 통과해야 함."""
    df = read_raw(path)
    value_cols = [c for c in REQUIRED + OPTIONAL if c in df.columns]

    rows, spans = [], {}
    for c in value_cols:
        ok = df[df[c].notna() & (df[c] > 0)]
        if ok.empty:
            rows.append(dict(컬럼=COLS[c], 최초월="-", 최종월="-", 개월수=0, 결측월=0)); continue
        mn, mx = ok.ym.min(), ok.ym.max()
        full = pd.period_range(mn.to_period("M"), mx.to_period("M"), freq="M")
        gap = len(full) - ok.ym.dt.to_period("M").nunique()
        spans[c] = (mn, mx)
        rows.append(dict(컬럼=COLS[c], 최초월=f"{mn:%Y-%m}", 최종월=f"{mx:%Y-%m}",
                         개월수=ok.ym.dt.to_period("M").nunique(), 결측월=gap))
    cov = pd.DataFrame(rows)

    req = [c for c in REQUIRED if c in spans]
    if len(req) < len(REQUIRED):
        raise SystemExit("[중단] 필수 지표에 유효한 값이 없음 — 원본 확인 필요")
    start = max(spans[c][0] for c in req)
    end = min(spans[c][1] for c in req)          # 대표 단월 = 공통 구간의 마지막 달
    win_start = max(start, end - pd.DateOffset(months=months - 1))

    # 분자·분모가 같은 달에 함께 있는지 — R이 성립하는 행 비율
    both = df[df[REQUIRED].notna().all(axis=1) & (df[REQUIRED] > 0).all(axis=1)]
    pair_rate = len(both) / max(len(df), 1)

    if verbose:
        print("=" * 62)
        print("[기준월 진단]  10/5 회의 지적 '가' — 이 표가 기획서 3장 본문이 됨")
        print("=" * 62)
        print(cov.to_string(index=False))
        print(f"\n  공통 구간        : {start:%Y-%m} ~ {end:%Y-%m}")
        print(f"  분석 기간(권장)  : {win_start:%Y-%m} ~ {end:%Y-%m}  ({months}개월)")
        print(f"  대표 단월        : {end:%Y-%m}   ← 기획서 대표 수치는 전부 이 달 기준")
        print(f"  방문·소비 동월 행 : {pair_rate:.1%}  (100%가 아니면 R 계산에서 빠지는 지역 있음)")
        for c in OPTIONAL:
            if c in spans and spans[c][1] < end:
                print(f"  [주의] {COLS[c]}의 최종월({spans[c][1]:%Y-%m})이 대표 단월보다 빠름 "
                      f"→ 표에 '기준월 다름' 표기하고 보조 근거로만 사용")
        if pair_rate < 0.95:
            print("  [경고] 방문객·소비가 서로 다른 달에만 있는 행이 5% 넘음. "
                  "읍면동 코드나 기준월 표기가 어긋났을 가능성 — 합치기 전에 확인할 것")
        os.makedirs(OUT, exist_ok=True)
        cov.to_csv(f"{OUT}/coverage.csv", index=False, encoding="utf-8-sig")
        print(f"\n  저장: {OUT}/coverage.csv  (그대로 기획서 데이터 품질 표로 사용)")
    return df, win_start, end


def merge_sources(paths: dict, out="integrated_v1.csv"):
    """여러 원본을 (기준연월, 음면동)으로 합치면서 버려지는 행을 보고한다.
       paths 예: {"방문객": "skt.csv", "소비": "card.csv", "차량도착": "tmap.csv"}"""
    base = None
    for name, p in paths.items():
        d = pd.read_csv(p)
        d[COLS["ym"]] = d[COLS["ym"]].astype(str).str.replace("-", "").str[:6]
        print(f"  {name:8s}: {len(d):6,}행  {d[COLS['ym']].min()}~{d[COLS['ym']].max()}")
        base = d if base is None else base.merge(d, on=[COLS["ym"], COLS["region"]], how="inner")
        print(f"  {'':8s}  → 합친 뒤 {len(base):6,}행")
    base.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"  저장: {out}")
    return base


# ══════════════════════════════════════════════════════════════
# 2. 4분면 + 도착 집중도  (지표 2개)
# ══════════════════════════════════════════════════════════════
def quadrant(i_visit, i_spend, cut=0.5):
    if i_visit < cut and i_spend >= cut:
        return "숨은 알짜"
    if i_visit >= cut and i_spend >= cut:
        return "이미 인기"
    if i_visit < cut and i_spend < cut:
        return "관심 밖"
    return "방문 대비 소비 낮음"


def run_quadrant(path, months=12):
    os.makedirs(OUT, exist_ok=True)
    df, win_start, end = coverage(path, months)
    win = df[(df.ym >= win_start) & (df.ym <= end)].copy()
    win = win[win.visitors > 0]
    win["R"] = win.spend / win.visitors
    win["I_spend"] = win.groupby("ym")["R"].rank(pct=True)
    win["I_visit"] = win.groupby("ym")["visitors"].rank(pct=True)
    if "arrivals" in win.columns:
        win["I_arrive"] = win.groupby("ym")["arrivals"].rank(pct=True)

    aggmap = dict(visitors=("visitors", "sum"), spend=("spend", "sum"),
                  I_visit=("I_visit", "mean"), I_spend=("I_spend", "mean"))
    if "I_arrive" in win.columns:
        aggmap["I_arrive"] = ("I_arrive", "mean")
    agg = win.groupby("region").agg(**aggmap).reset_index()
    agg["R_12m"] = agg.spend / agg.visitors
    agg["사분면"] = [quadrant(v, s) for v, s in zip(agg.I_visit, agg.I_spend)]
    if "I_arrive" in agg.columns:
        agg["저집중도"] = 1 - agg.I_arrive      # 추천 점수에 쓰는 값

    win["q_month"] = [quadrant(v, s) for v, s in zip(win.I_visit, win.I_spend)]
    stab = (win.merge(agg[["region", "사분면"]], on="region")
               .assign(same=lambda d: d.q_month == d["사분면"])
               .groupby("region")["same"].mean().rename("사분면_유지율"))
    agg = agg.merge(stab, on="region")

    win["season"] = np.where(win.ym.dt.month.isin([7, 8]), "성수기", "비수기")
    seas = win.pivot_table(index="region", columns="season", values="I_spend", aggfunc="mean")
    if {"성수기", "비수기"} <= set(seas.columns):
        agg = agg.merge((seas["성수기"] - seas["비수기"]).rename("계절편차"), on="region")

    piv = win.pivot_table(index="region", columns="ym", values="R")
    rho = piv.corr(method="spearman").values
    month_rho = np.nanmean(rho[np.triu_indices_from(rho, k=1)])

    agg = agg.sort_values("I_spend", ascending=False)
    agg.to_csv(f"{OUT}/quadrant_12m.csv", index=False, encoding="utf-8-sig")

    print("\n" + "=" * 62)
    print(f"[4분면]  {win.ym.min():%Y-%m}~{win.ym.max():%Y-%m}, {agg.region.nunique()}개 읍면동")
    print("=" * 62)
    print(f"  월간 순위 상관(Spearman 평균) = {month_rho:.2f}"
          f"   {'→ 구조적 차이로 서술 가능' if month_rho >= 0.7 else '→ 0.7 미만, 월별 변동 크다고 서술할 것'}")
    print(agg["사분면"].value_counts().to_string())
    print("\n[조천·구좌]")
    cols = [c for c in ["region", "R_12m", "I_visit", "I_spend", "저집중도", "사분면", "사분면_유지율", "계절편차"] if c in agg.columns]
    print(agg[agg.region.isin(FOCUS)][cols].round(3).to_string(index=False))
    for _, r in agg[agg.region.isin(FOCUS)].iterrows():
        if r["사분면"] == "이미 인기":
            print(f"  [확인] {r.region}이 '{r['사분면']}'에 찍힘 → 음 단위로 '덜 알려진 지역'이라고 "
                  f"쓰면 반박당함. 권역 안 장소 단위로 서술할 것")
    plot_quadrant(agg)
    return agg


def plot_quadrant(agg):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for f in ["NanumGothic", "Noto Sans CJK KR", "AppleGothic", "Malgun Gothic"]:
        if any(f in x.name for x in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = f
            break
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(7, 6))
    base = agg[~agg.region.isin(FOCUS)]
    ax.scatter(base.I_visit, base.I_spend, s=28, color="#B8B2A7")
    foc = agg[agg.region.isin(FOCUS)]
    ax.scatter(foc.I_visit, foc.I_spend, s=70, color="#D9652B", zorder=3)
    for _, r in foc.iterrows():
        ax.annotate(r.region, (r.I_visit, r.I_spend), xytext=(6, 4), textcoords="offset points")
    ax.axhline(.5, color="#888", lw=.8, ls="--"); ax.axvline(.5, color="#888", lw=.8, ls="--")
    for x, y, t in [(.02, .97, "숨은 알짜"), (.98, .97, "이미 인기"),
                    (.02, .03, "관심 밖"), (.98, .03, "방문 대비 소비 낮음")]:
        ax.text(x, y, t, transform=ax.transAxes, ha="left" if x < .5 else "right",
                va="top" if y > .5 else "bottom", color="#666", fontsize=9)
    ax.set_xlabel("방문 규모 지수 (12개월 평균, 0~1)")
    ax.set_ylabel("방문 대비 소비 지수 (12개월 평균, 0~1)")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(f"{OUT}/quadrant_12m.png", dpi=200)
    print(f"  그래프: {OUT}/quadrant_12m.png")


# ══════════════════════════════════════════════════════════════
# 3. 장소 적합성  (유휴 카페 지표 대체 — 직접 수집)
# ══════════════════════════════════════════════════════════════
# places.csv: name, type(관광지/카페/휴식), area, to_airport_min, dwell_min,
#             [lat, lon, open_from, open_to, seats, power, wifi, quiet, scenic, review_cnt]
def _wsum(parts):
    """값이 없는 항목은 빼고 남은 가중치를 비율대로 다시 맞춤 (기획서 '데이터 없을 때' 규칙)."""
    ok = [(w, v) for w, v in parts if v is not None and not pd.isna(v)]
    if not ok:
        return 0.5, 0.0                      # 정보 없음 → 중립값, 신뢰도 0
    tot = sum(w for w, _ in ok)
    return sum(w * v for w, v in ok) / tot, tot / sum(w for w, _ in parts)


def fit_score(places, mode):
    """모드별 장소 적합성 0~1 + 속성 충족률. 리뷰 수는 '덜 알려진' 쪝에 가점."""
    p = places.copy()
    g = lambda c: p[c] if c in p.columns else pd.Series([np.nan] * len(p), index=p.index)
    hours = (g("open_to") - g("open_from")).clip(lower=0) / 12
    unknown = 1 - g("review_cnt").rank(pct=True) if "review_cnt" in p.columns else pd.Series([np.nan] * len(p), index=p.index)
    stay = 1 - ((g("dwell_min") - 60).abs() / 60).clip(upper=1)     # 30~90분이 적합
    out, conf = [], []
    for i in p.index:
        if mode == "일":
            parts = [(0.30, g("wifi")[i]), (0.30, g("power")[i]),
                     (0.20, min(g("seats")[i] / 40, 1) if not pd.isna(g("seats")[i]) else np.nan),
                     (0.20, min(hours[i], 1) if not pd.isna(hours[i]) else np.nan)]
        elif mode == "휴식":
            parts = [(0.40, g("quiet")[i]), (0.40, g("scenic")[i]), (0.20, unknown[i])]
        else:
            parts = [(0.50, stay[i]), (0.50, unknown[i])]
        s, c = _wsum(parts)
        out.append(s); conf.append(c)
    return pd.Series(out, index=p.index), pd.Series(conf, index=p.index)


# ══════════════════════════════════════════════════════════════
# 4. 추천 + 공항 도착 준수율
# ══════════════════════════════════════════════════════════════
BUFFER = 30
AIRPORT_BEFORE = 60
RENTAL_RETURN = 25          # 설문 결과로 교체


def available_minutes(now_min, flight_min, rental=True):
    return flight_min - AIRPORT_BEFORE - now_min - (RENTAL_RETURN if rental else 0) - BUFFER


def plan_course(places, avail, mode, between_min, low_crowd, spend_idx):
    """STEP A 시간 필터 → STEP B 권역 → STEP C 모드별 가중 점수(최고점 선택)."""
    w = WEIGHTS[mode]
    area_ok = places if avail >= 180 else places[places.area == "조천"]
    if area_ok.empty:
        return None
    fit, _ = fit_score(area_ok, mode)
    cands = []

    def add(t, names, idx_list):
        if t > avail:
            return
        regions = area_ok.loc[idx_list, "area"]
        score = (w["spend"] * np.mean([spend_idx.get(r, 0.5) for r in regions])
                 + w["low_crowd"] * np.mean([low_crowd.get(r, 0.5) for r in regions])
                 + w["fit"] * fit.loc[idx_list].mean()
                 + w["travel"] * (t / avail))
        cands.append((score, t, names))

    if mode == "관광":
        A = area_ok[area_ok.type == "관광지"]; B = area_ok[area_ok.type == "카페"]
        for ia, a in A.iterrows():
            for ib, b in B.iterrows():
                t = a.to_airport_min + a.dwell_min + between_min(a, b) + b.dwell_min + b.to_airport_min
                add(t, [a["name"], b["name"]], [ia, ib])
    else:
        pool = area_ok[area_ok.type == ("카페" if mode == "일" else "휴식")]
        for i, p in pool.iterrows():
            add(p.to_airport_min * 2 + p.dwell_min, [p["name"]], [i])
    if not cands:
        return None
    best = max(cands, key=lambda x: x[0])
    return best[1], best[2], best[0]


def simulate(places, region_idx=None, n=2000, noise=0.25, seed=7, quiet=False):
    rng = np.random.default_rng(seed)
    low_crowd = (region_idx or {}).get("저집중도", {})
    spend_idx = (region_idx or {}).get("I_spend", {})

    def between(a, b):
        if {"lat", "lon"} <= set(places.columns) and not pd.isna(a.lat):
            d = np.hypot(a.lat - b.lat, (a.lon - b.lon) * 0.83) * 111
            return d / 40 * 60 * 1.3
        return abs(a.to_airport_min - b.to_airport_min) + 10

    rows = []
    for _ in range(n):
        mode = rng.choice(["관광", "일", "휴식"])
        now = rng.integers(9 * 60, 14 * 60)
        flight = now + rng.integers(4 * 60, 9 * 60)
        rental = rng.random() < 0.75
        avail = available_minutes(now, flight, rental)
        plan = plan_course(places, avail, mode, between, low_crowd, spend_idx)
        if plan is None:
            rows.append(dict(mode=mode, avail=avail, recommended=False,
                             on_time=np.nan, slack_min=np.nan)); continue
        planned, _, score = plan
        actual = planned * .45 + planned * .55 * rng.lognormal(np.log(1 + noise / 2), noise / 2)
        slack = avail + BUFFER - actual
        rows.append(dict(mode=mode, avail=avail, recommended=True, score=score,
                         on_time=float(slack >= 0), slack_min=float(slack)))
    res = pd.DataFrame(rows)
    rec = res[res.recommended]
    if not quiet:
        print(f"\n[시뮬레이션] n={n}, 이동시간 노이즈 ±{int(noise * 100)}%")
        print(f"  추천 제공률        : {res.recommended.mean():.1%}")
        print(f"  공항 도착 준수율   : {rec.on_time.mean():.1%}")
        print(f"  여유 30분 미사용률 : {(rec.slack_min >= BUFFER).mean():.1%}")
        print(rec.groupby("mode")["on_time"].mean().map("{:.1%}".format).to_string())
    return res


def sensitivity(places, region_idx=None):
    print("\n[민감도] 이동시간 노이즈별 공항 도착 준수율")
    for nz in [0.1, 0.25, 0.5, 0.8]:
        r = simulate(places, region_idx, n=1000, noise=nz, seed=1, quiet=True)
        rec = r[r.recommended]
        print(f"  ±{int(nz * 100):>2}%  준수율 {rec.on_time.mean():6.1%}   제공률 {r.recommended.mean():6.1%}")
    print("  → 기획서 문장: \"이드시간이 계획보다 50% 늘어나는 상황에서도 ○○%가 공항 도착 기준을 지킴다\"")


def weight_sensitivity(places, region_idx=None, delta=0.1):
    """가중치 ±0.1에서 추천 1순위가 바뀌는 비율 — '가중치는 초안' 방어용."""
    print(f"\n[가중치 민감도] 각 요소 ±{delta} 변화 시 1순위 코스가 바뀌는 비율")
    import copy
    base = {m: plan_course(places, 300, m, lambda a, b: abs(a.to_airport_min - b.to_airport_min) + 10,
                           (region_idx or {}).get("저집중도", {}), (region_idx or {}).get("I_spend", {}))
            for m in WEIGHTS}
    orig = copy.deepcopy(WEIGHTS)
    for mode in WEIGHTS:
        changed = 0; trials = 0
        for key in ["spend", "low_crowd", "fit"]:
            for d in (+delta, -delta):
                WEIGHTS[mode][key] = orig[mode][key] + d
                new = plan_course(places, 300, mode, lambda a, b: abs(a.to_airport_min - b.to_airport_min) + 10,
                                  (region_idx or {}).get("저집중도", {}), (region_idx or {}).get("I_spend", {}))
                trials += 1
                if base[mode] and new and base[mode][1] != new[1]:
                    changed += 1
                WEIGHTS[mode][key] = orig[mode][key]
        print(f"  {mode}: {changed}/{trials} 변동  "
              f"{'(안정 — 가중치 싰자에 결과가 좌우되지 않음)' if changed <= trials * .25 else '(민감 — 설문 근거를 꽭 붙일 것)'}")


def load_region_idx(path):
    q = pd.read_csv(path)
    key = "region"
    out = {}
    for c in ["저집중도", "I_spend"]:
        if c in q.columns:
            # places의 area('조천')와 읍면동명('조천읍') 연결
            out[c] = {str(r[key]).replace("읍", "").replace("면", ""): r[c] for _, r in q.iterrows()}
    return out


# ══════════════════════════════════════════════════════════════
# 5. 동작 확인용 가지 데이터
# ══════════════════════════════════════════════════════════════
def demo():
    rng = np.random.default_rng(0)
    regions = FOCUS + [f"음면동{i:02d}" for i in range(41)]
    rows = []
    for r in regions:
        base_v = 732876 if r == "조천읍" else 708830 if r == "구좌읍" else rng.lognormal(12, .8)
        base_R = 14292 if r == "조천읍" else 11032 if r == "구좌읍" else rng.lognormal(9.3, .4)
        for ym in pd.period_range("2024-08", "2026-07", freq="M"):
            s = 1.3 if ym.month in (7, 8) else 1.0
            v = base_v / (1.3 if r in FOCUS else 1) * s * rng.lognormal(0, .1)
            row = {COLS["ym"]: ym.strftime("%Y%m"), COLS["region"]: r,
                   COLS["visitors"]: round(v),
                   COLS["spend"]: round(v * base_R * rng.lognormal(0, .12))}
            # 차량 도착은 한 달 늦게 들어오는 상황을 일부러 넣음 (기준월 경고 확인용)
            if ym < pd.Period("2026-07"):
                row[COLS["arrivals"]] = round(v * 0.35 * rng.lognormal(0, .15))
            rows.append(row)
    pd.DataFrame(rows).to_csv("demo_integrated.csv", index=False, encoding="utf-8-sig")
    agg = run_quadrant("demo_integrated.csv")

    places = pd.DataFrame([
        ("조천 관광지A", "관광지", "조천", 33, 60, 1, 1, 320),
        ("조천 관광지B", "관광지", "조천", 38, 45, 1, 1, 90),
        ("조천 카페A", "카페", "조천", 31, 50, 0, 0, 1500),
        ("조천 카페B", "카페", "조천", 36, 90, 1, 1, 210),
        ("조천 휴식A", "휴식", "조천", 35, 60, 1, 1, 150),
        ("구좌 관광지A", "관광지", "구좌", 59, 60, 1, 1, 2400),
        ("구좌 카페A", "카페", "구좌", 55, 60, 1, 1, 320),
        ("구좌 휴식A", "휴식", "구좌", 58, 70, 1, 1, 80),
    ], columns=["name", "type", "area", "to_airport_min", "dwell_min", "quiet", "scenic", "review_cnt"])
    places["open_from"] = 9; places["open_to"] = [18, 18, 20, 21, 19, 18, 19, 18]
    places["seats"] = [np.nan, np.nan, 25, 48, 30, np.nan, 40, 20]
    places["wifi"] = [np.nan, np.nan, 1, 1, 1, np.nan, 1, 0]
    places["power"] = [np.nan, np.nan, 0, 1, 1, np.nan, 1, 0]

    idx = load_region_idx(f"{OUT}/quadrant_12m.csv")
    print("\n[장소 적합성] 모드별 상위 3곳")
    for m in WEIGHTS:
        f, c = fit_score(places, m)
        top = places.assign(저합성=f.round(2), 속성충족=c.round(2)).nlargest(3, "적합성")
        print(f"  {m}: " + ", ".join(f"{r['name']}({r.적합성})" for _, r in top.iterrows()))

    simulate(places, idx)
    sensitivity(places, idx)
    weight_sensitivity(places, idx)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if cmd == "coverage":
        coverage(sys.argv[2])
    elif cmd == "quad":
        run_quadrant(sys.argv[2])
    elif cmd == "sim":
        p = pd.read_csv(sys.argv[2])
        idx = load_region_idx(sys.argv[3]) if len(sys.argv) > 3 else None
        simulate(p, idx); sensitivity(p, idx); weight_sensitivity(p, idx)
    else:
        demo()
