"""Google Search Console API로 K-Brief의 검색어·페이지별 노출·클릭을 모은다(최근 28일).

필요한 환경 변수(GitHub Secrets):
  GSC_SERVICE_ACCOUNT_JSON  서비스 계정 키 JSON 전체(문자열)
  GSC_SITE                  속성 주소. 도메인 속성이면 "sc-domain:k-brief.com"(기본값)

출력:
  data/gsc/queries.csv                검색어별 합계(노출 순)
  data/gsc/query_pages.csv            검색어×페이지(어느 글이 그 검색어로 노출됐는지)
  data/gsc/history/YYYY-MM-DD.csv     검색어별 합계 보관
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

from common import DATA, today_kst, update_status, write_csv

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
LAG_DAYS = 3      # Search Console 데이터는 보통 2~3일 늦게 확정된다
WINDOW_DAYS = 28
ROW_LIMIT = 25000

Q_FIELDS = ["query", "clicks", "impressions", "ctr_pct", "position"]
QP_FIELDS = ["query", "page", "clicks", "impressions", "ctr_pct", "position"]


def query(service, site: str, start: str, end: str, dimensions: list[str]) -> list[dict]:
    rows, start_row = [], 0
    while True:
        body = {
            "startDate": start,
            "endDate": end,
            "dimensions": dimensions,
            "rowLimit": ROW_LIMIT,
            "startRow": start_row,
        }
        resp = service.searchanalytics().query(siteUrl=site, body=body).execute()
        batch = resp.get("rows", [])
        rows.extend(batch)
        if len(batch) < ROW_LIMIT:
            return rows
        start_row += ROW_LIMIT


def flatten(rows: list[dict], dimensions: list[str]) -> list[dict]:
    out = []
    for r in rows:
        rec = {d: r["keys"][i] for i, d in enumerate(dimensions)}
        rec.update({
            "clicks": int(r.get("clicks", 0)),
            "impressions": int(r.get("impressions", 0)),
            "ctr_pct": round(float(r.get("ctr", 0)) * 100, 2),
            "position": round(float(r.get("position", 0)), 1),
        })
        out.append(rec)
    out.sort(key=lambda x: (x["impressions"], x["clicks"]), reverse=True)
    return out


def main() -> int:
    raw = os.environ.get("GSC_SERVICE_ACCOUNT_JSON", "").strip()
    site = os.environ.get("GSC_SITE", "sc-domain:k-brief.com").strip()
    if not raw:
        update_status("gsc", False, "Secrets 미설정(GSC_SERVICE_ACCOUNT_JSON)")
        print("Search Console 서비스 계정 키가 없어 건너뜁니다.")
        return 0

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    try:
        info = json.loads(raw)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        end = today_kst() - dt.timedelta(days=LAG_DAYS)
        start = end - dt.timedelta(days=WINDOW_DAYS - 1)
        s, e = start.isoformat(), end.isoformat()
        q_rows = flatten(query(service, site, s, e, ["query"]), ["query"])
        qp_rows = flatten(query(service, site, s, e, ["query", "page"]), ["query", "page"])
    except Exception as ex:
        msg = str(ex)
        hint = ""
        if "403" in msg or "permission" in msg.lower():
            hint = " → Search Console 설정 > 사용자 및 권한에 서비스 계정 이메일을 추가했는지 확인"
        update_status("gsc", False, f"오류: {msg[:300]}{hint}", site=site)
        print(f"Search Console 조회 실패: {msg}", file=sys.stderr)
        return 1

    out_dir = DATA / "gsc"
    write_csv(out_dir / "queries.csv", q_rows, Q_FIELDS)
    write_csv(out_dir / "query_pages.csv", qp_rows, QP_FIELDS)
    write_csv(out_dir / "history" / f"{today_kst().isoformat()}.csv", q_rows, Q_FIELDS)
    update_status(
        "gsc", True, "ok", site=site, period=f"{s}~{e}",
        queries=len(q_rows), impressions=sum(r["impressions"] for r in q_rows),
        clicks=sum(r["clicks"] for r in q_rows),
    )
    print(f"완료: {s}~{e} 검색어 {len(q_rows)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
