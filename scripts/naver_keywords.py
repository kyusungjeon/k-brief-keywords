"""네이버 검색광고 API 키워드도구(/keywordstool)로 씨앗 키워드별 연관 키워드와 월간 검색수를 모은다.

필요한 환경 변수(GitHub Secrets):
  NAVER_AD_CUSTOMER_ID     검색광고 > 도구 > API 사용 관리의 CUSTOMER_ID
  NAVER_AD_ACCESS_LICENSE  같은 화면의 액세스라이선스
  NAVER_AD_SECRET_KEY      같은 화면의 비밀키

출력:
  data/naver/latest.csv               이번 실행 전체(씨앗별 연관 키워드)
  data/naver/top.csv                  키워드 기준 중복 제거·검색수 순 상위 500 + 지난 실행 대비 변화
  data/naver/history/YYYY-MM-DD.csv   실행일별 보관(top 기준)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sys
import time

import requests

from common import DATA, ROOT, read_csv, today_kst, update_status, write_csv

BASE_URL = "https://api.searchad.naver.com"
URI = "/keywordstool"
TOP_N = 500
SLEEP_SEC = 1.0  # 호출 간격(과도한 호출 방지)

LATEST_FIELDS = [
    "seed", "keyword", "pc", "mobile", "total", "lt10", "comp_idx",
    "pc_clicks", "mobile_clicks", "ad_depth",
]
TOP_FIELDS = [
    "rank", "keyword", "total", "pc", "mobile", "lt10", "comp_idx", "seeds",
    "prev_total", "change_pct", "is_new",
]


def signature(timestamp: str, method: str, uri: str, secret: str) -> str:
    message = f"{timestamp}.{method}.{uri}"
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def to_count(value) -> tuple[int, bool]:
    """검색수 값 정규화. '< 10' 은 (5, True)로 근사(순위 계산용)하고 lt10 플래그를 세운다."""
    if isinstance(value, (int, float)):
        return int(value), False
    s = str(value).strip().replace(",", "")
    if s.startswith("<"):
        return 5, True
    try:
        return int(float(s)), False
    except ValueError:
        return 0, False


def to_float(value) -> float:
    try:
        return round(float(str(value).replace(",", "")), 1)
    except ValueError:
        return 0.0


def load_seeds() -> list[str]:
    seeds = []
    for line in (ROOT / "seeds.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        seed = line.replace(" ", "")
        if seed and seed not in seeds:
            seeds.append(seed)
    return seeds


def fetch(seed: str, customer_id: str, license_key: str, secret: str, session: requests.Session) -> list[dict]:
    for attempt in range(4):
        ts = str(int(time.time() * 1000))
        headers = {
            "X-Timestamp": ts,
            "X-API-KEY": license_key,
            "X-Customer": str(customer_id),
            "X-Signature": signature(ts, "GET", URI, secret),
        }
        resp = session.get(
            BASE_URL + URI,
            params={"hintKeywords": seed, "showDetail": "1"},
            headers=headers,
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json().get("keywordList", [])
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt * 2)
            continue
        raise RuntimeError(f"{seed}: HTTP {resp.status_code} {resp.text[:200]}")
    raise RuntimeError(f"{seed}: 재시도 후에도 실패(호출 한도 또는 서버 오류)")


def normalize(seed: str, item: dict) -> dict:
    pc, pc_lt = to_count(item.get("monthlyPcQcCnt", 0))
    mo, mo_lt = to_count(item.get("monthlyMobileQcCnt", 0))
    return {
        "seed": seed,
        "keyword": str(item.get("relKeyword", "")).strip(),
        "pc": pc,
        "mobile": mo,
        "total": pc + mo,
        "lt10": "Y" if (pc_lt or mo_lt) else "",
        "comp_idx": item.get("compIdx", ""),
        "pc_clicks": to_float(item.get("monthlyAvePcClkCnt", 0)),
        "mobile_clicks": to_float(item.get("monthlyAveMobileClkCnt", 0)),
        "ad_depth": item.get("plAvgDepth", ""),
    }


def build_top(rows: list[dict], prev_top: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for r in rows:
        k = r["keyword"]
        if not k:
            continue
        if k not in merged:
            merged[k] = {**r, "seeds": [r["seed"]]}
        else:
            if r["seed"] not in merged[k]["seeds"]:
                merged[k]["seeds"].append(r["seed"])
            if int(r["total"]) > int(merged[k]["total"]):
                keep_seeds = merged[k]["seeds"]
                merged[k] = {**r, "seeds": keep_seeds}
    prev = {p["keyword"]: int(p["total"]) for p in prev_top if p.get("keyword")}
    ordered = sorted(merged.values(), key=lambda x: int(x["total"]), reverse=True)[:TOP_N]
    out = []
    for i, r in enumerate(ordered, 1):
        prev_total = prev.get(r["keyword"])
        if prev_total:
            change = round((int(r["total"]) - prev_total) / prev_total * 100, 1)
        else:
            change = ""
        out.append({
            "rank": i,
            "keyword": r["keyword"],
            "total": r["total"],
            "pc": r["pc"],
            "mobile": r["mobile"],
            "lt10": r["lt10"],
            "comp_idx": r["comp_idx"],
            "seeds": ";".join(r["seeds"]),
            "prev_total": prev_total if prev_total is not None else "",
            "change_pct": change,
            "is_new": "" if (prev_total is not None or not prev) else "Y",
        })
    return out


def main() -> int:
    customer_id = os.environ.get("NAVER_AD_CUSTOMER_ID", "").strip()
    license_key = os.environ.get("NAVER_AD_ACCESS_LICENSE", "").strip()
    secret = os.environ.get("NAVER_AD_SECRET_KEY", "").strip()
    if not (customer_id and license_key and secret):
        update_status("naver", False, "Secrets 미설정(NAVER_AD_CUSTOMER_ID / NAVER_AD_ACCESS_LICENSE / NAVER_AD_SECRET_KEY)")
        print("네이버 검색광고 API 키가 없어 건너뜁니다.")
        return 0

    seeds = load_seeds()
    session = requests.Session()
    rows: list[dict] = []
    failed: list[str] = []
    for seed in seeds:
        try:
            items = fetch(seed, customer_id, license_key, secret, session)
            per_seed: dict[str, dict] = {}
            for it in items:
                r = normalize(seed, it)
                if r["keyword"] and (r["keyword"] not in per_seed or r["total"] > per_seed[r["keyword"]]["total"]):
                    per_seed[r["keyword"]] = r
            rows.extend(per_seed.values())
            print(f"[ok] {seed}: {len(per_seed)}개")
        except Exception as e:  # 한 씨앗 실패가 전체를 멈추지 않게
            failed.append(seed)
            print(f"[fail] {e}", file=sys.stderr)
        time.sleep(SLEEP_SEC)

    if not rows:
        update_status("naver", False, f"수집 0건(실패 씨앗 {len(failed)}개)", failed_seeds=failed)
        return 1

    out_dir = DATA / "naver"
    prev_top = read_csv(out_dir / "top.csv")
    top = build_top(rows, prev_top)
    write_csv(out_dir / "latest.csv", rows, LATEST_FIELDS)
    write_csv(out_dir / "top.csv", top, TOP_FIELDS)
    write_csv(out_dir / "history" / f"{today_kst().isoformat()}.csv", top, TOP_FIELDS)
    update_status(
        "naver", True, "ok",
        seeds=len(seeds), seeds_failed=failed, rows=len(rows), top_keywords=len(top),
    )
    print(f"완료: 씨앗 {len(seeds)}개(실패 {len(failed)}), 연관 키워드 {len(rows)}행, 상위 {len(top)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
