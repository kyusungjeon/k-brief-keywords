"""수집 결과를 키워드 매니저가 바로 읽을 수 있는 data/summary.md 로 요약한다."""
from __future__ import annotations

import json
import sys
from collections import defaultdict

from common import DATA, read_csv, today_kst

TOP_OVERALL = 60
TOP_PER_SEED = 8
RISING_MIN_TOTAL = 500
RISING_MIN_PCT = 30.0


def num(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def fmt(n) -> str:
    return f"{num(n):,}"


def main() -> int:
    lines = [f"# K-Brief 키워드 데이터 요약 ({today_kst().isoformat()} KST 생성)", ""]
    status_path = DATA / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    lines.append("## 수집 상태")
    for src, label in (("naver", "네이버 검색광고 키워드도구"), ("gsc", "Google Search Console")):
        s = status.get(src)
        if not s:
            lines.append(f"- {label}: 기록 없음")
        else:
            lines.append(f"- {label}: {'정상' if s.get('ok') else '실패'} · {s.get('message')} · {s.get('run_at_kst')}")
    lines.append("")

    top = read_csv(DATA / "naver" / "top.csv")
    if top:
        lines += [
            "## 네이버 월간 검색수 상위 (최근 30일, PC+모바일)",
            "검색수는 네이버 검색광고 키워드도구 값. '<10'은 10회 미만. 경쟁 정도는 광고 경쟁(높음/중간/낮음)으로 콘텐츠 경쟁과는 다를 수 있음.",
            "",
            "| 순위 | 키워드 | 월간 검색수 | 모바일 | 광고 경쟁 | 지난주 대비 | 씨앗 |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in top[:TOP_OVERALL]:
            chg = f"{r['change_pct']}%" if r.get("change_pct") not in ("", None) else ("신규" if r.get("is_new") == "Y" else "-")
            total = "<10" if r.get("lt10") == "Y" and num(r["total"]) < 10 else fmt(r["total"])
            seeds = [x for x in str(r.get("seeds", "")).split(";") if x]
            seed_txt = "·".join(seeds[:3]) + (f" 외 {len(seeds) - 3}" if len(seeds) > 3 else "")
            lines.append(f"| {r['rank']} | {r['keyword']} | {total} | {fmt(r['mobile'])} | {r['comp_idx']} | {chg} | {seed_txt} |")
        lines.append("")

        rising = [
            r for r in top
            if r.get("change_pct") not in ("", None)
            and float(r["change_pct"]) >= RISING_MIN_PCT
            and num(r["total"]) >= RISING_MIN_TOTAL
        ]
        rising.sort(key=lambda r: float(r["change_pct"]), reverse=True)
        lines.append(f"## 급상승 (지난 실행 대비 +{RISING_MIN_PCT:.0f}% 이상, 월 {RISING_MIN_TOTAL:,}회 이상)")
        if rising:
            for r in rising[:20]:
                lines.append(f"- {r['keyword']}: {fmt(r['prev_total'])} → {fmt(r['total'])} ({r['change_pct']}%)")
        else:
            lines.append("- 없음(첫 실행이거나 해당 키워드 없음)")
        lines.append("")

        latest = read_csv(DATA / "naver" / "latest.csv")
        by_seed: dict[str, list[dict]] = defaultdict(list)
        for r in latest:
            by_seed[r["seed"]].append(r)
        lines.append(f"## 씨앗별 연관 키워드 상위 {TOP_PER_SEED}")
        for seed, rows in by_seed.items():
            rows.sort(key=lambda x: num(x["total"]), reverse=True)
            items = ", ".join(f"{x['keyword']}({fmt(x['total'])})" for x in rows[:TOP_PER_SEED])
            lines.append(f"- **{seed}**: {items}")
        lines.append("")

    gsc = read_csv(DATA / "gsc" / "queries.csv")
    s = status.get("gsc", {})
    lines.append(f"## K-Brief 구글 검색어 (Search Console, {s.get('period', '기간 정보 없음')})")
    if gsc:
        lines += ["| 검색어 | 노출 | 클릭 | 평균 순위 |", "|---|---|---|---|"]
        for r in gsc[:40]:
            lines.append(f"| {r['query']} | {fmt(r['impressions'])} | {fmt(r['clicks'])} | {r['position']} |")
    else:
        lines.append("- 데이터 없음(미설정·실패이거나 아직 노출 없음)")
    lines.append("")

    (DATA / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("data/summary.md 작성 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
