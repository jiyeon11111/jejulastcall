"""구글 드라이브 원본(data/drive/) → 백엔드 분석 CSV(app/data/analysis/) 변환.

실행:  python backend/scripts/sync_drive.py
입력:  data/drive/권역후보비교표_초안.csv   (드라이브 시트 '돌담랩_권역 후보 비교표_초안' 사본)
       data/drive/quadrant_12m.csv        (있으면: lastcall_analysis.py quad 의 out/quadrant_12m.csv)
출력:  app/data/analysis/travel_observed.csv   공항 ↔ 지점 실측 이동시간 (카카오맵)
       app/data/analysis/place_metrics.csv     카카오맵 리뷰 수 → popularity (팀 스크립트와 같은 백분위 방식)
       app/data/analysis/region_index.csv      권역 지수 (quadrant_12m.csv 가 있을 때만)
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRIVE = ROOT / "data" / "drive"
ANALYSIS = ROOT / "backend" / "app" / "data" / "analysis"
PLACES = ROOT / "backend" / "app" / "data" / "places.json"

SHEET = DRIVE / "권역후보비교표_초안.csv"
MEASURED_AT = "2026-09-28"
SOURCE = "kakao-map-2026-09-28 (돌담랩_권역 후보 비교표_초안)"

# 비교표의 지점 이름 → places.json / areas 의 id
POINT_ID = {
    "조천읍": "area:jocheon",      # 공항 → 조천읍사무소
    "구좌읍": "area:sehwa",        # 구좌읍사무소는 세화리에 있다
    "함덕해수욕장": "place:hamdeok-beach",
    "월정리해수욕장": "place:woljeong-beach",
}
NAME_TO_PLACE = {
    "함덕해수욕장": "hamdeok-beach", "서우봉": "seoubong", "에코랜드": "ecoland",
    "월정리해수욕장": "woljeong-beach", "비자림": "bijarim", "김녕해수욕장": "gimnyeong-beach",
    "선흘 동백동산": "dongbaek", "교래자연휴양림": "gyorae-forest",
    "세화해변": "sehwa-beach", "평대리해수욕장": "pyeongdae-beach", "종달리해안도로": "jongdal-coast",
    "다랑쉬오름": "darangshi",
}


def read_sheet() -> list[dict]:
    with SHEET.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def travel_rows(rows: list[dict]) -> list[dict]:
    out = []
    cols = ["서부-애월읍", "서부-한림읍", "동부-조천읍", "동부-구좌읍"]
    for r in rows:
        if r["구분"] != "이동":
            continue
        for col in cols:
            cell = r[col]
            m = re.search(r"(?:(.+?):\s*)?(\d+)분\s*\((\d+(?:\.\d+)?)km\)", cell)
            if not m:
                continue
            name = (m.group(1) or col.split("-")[1]).strip()
            out.append({
                "origin_id": "airport", "dest_id": POINT_ID.get(name, ""), "dest_name": name,
                "car_min": int(m.group(2)), "km": float(m.group(3)),
                "measured_at": MEASURED_AT, "source": SOURCE, "note": r["확인방법/메모"],
            })
    return out


def review_counts(rows: list[dict]) -> dict[str, int]:
    """'이름(리뷰 N)' 또는 '이름(N)' 패턴에서 리뷰 수를 모은다 (메모 칸의 제외 장소도 포함)."""
    counts: dict[str, int] = {}
    pat = re.compile(r"([가-힣A-Za-z0-9 ]+?)\((?:리뷰 )?(\d+)\)")
    for r in rows:
        if r["구분"] not in ("관광지",):
            continue
        for cell in list(r.values()):
            for name, n in pat.findall(cell or ""):
                name = name.strip()
                if name.startswith("에코랜드"):
                    name = "에코랜드"
                counts[name] = int(n)
    return counts


def popularity_from_reviews(counts: dict[str, int]) -> dict[str, float]:
    """팀 스크립트(lastcall_analysis.fit_score)와 같은 백분위 순위. 0~1, 높을수록 알려진 곳."""
    names = sorted(counts, key=lambda k: counts[k])
    n = len(names)
    out = {}
    for name in names:
        rank = sum(1 for k in names if counts[k] < counts[name]) + 1  # 동률은 낮은 순위
        out[name] = round(rank / n, 3)
    return out


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def main() -> int:
    if not SHEET.exists():
        print(f"[중단] {SHEET} 없음 — 드라이브 시트를 CSV로 받아 넣어 주세요")
        return 1
    rows = read_sheet()

    travel = travel_rows(rows)
    write_csv(ANALYSIS / "travel_observed.csv", travel,
              ["origin_id", "dest_id", "dest_name", "car_min", "km", "measured_at", "source", "note"])
    print(f"travel_observed.csv : {len(travel)}건 (앱 지점과 연결된 것 {sum(1 for t in travel if t['dest_id'])}건)")

    counts = review_counts(rows)
    pop = popularity_from_reviews(counts)
    place_ids = {p["id"] for p in json.loads(PLACES.read_text(encoding="utf-8"))["places"]}
    metrics = []
    for name, pid in NAME_TO_PLACE.items():
        if name in pop and pid in place_ids:
            metrics.append({"place_id": pid, "popularity": pop[name], "kakao_reviews": counts[name],
                            "source": SOURCE})
    write_csv(ANALYSIS / "place_metrics.csv", metrics, ["place_id", "popularity", "kakao_reviews", "source"])
    print(f"place_metrics.csv   : {len(metrics)}곳 (리뷰 수 백분위 → popularity)")
    for m in sorted(metrics, key=lambda x: x["popularity"]):
        print(f"   {m['place_id']:18s} 리뷰 {m['kakao_reviews']:4d} → {m['popularity']:.2f}")

    quad = DRIVE / "quadrant_12m.csv"
    if quad.exists():
        shutil.copy(quad, ANALYSIS / "region_index.csv")
        print("region_index.csv    : quadrant_12m.csv 복사")
    else:
        print("region_index.csv    : 건너뜀 (data/drive/quadrant_12m.csv 없음 — 플랫폼 데이터 확보 후 lastcall_analysis.py quad 실행)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
