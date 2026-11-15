"""공통 도우미: 경로, 날짜(KST), 상태 기록, CSV 읽기·쓰기."""
from __future__ import annotations

import csv
import datetime as dt
import json
import pathlib
from typing import Iterable

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
KST = dt.timezone(dt.timedelta(hours=9))


def today_kst() -> dt.date:
    return dt.datetime.now(KST).date()


def write_csv(path: pathlib.Path, rows: Iterable[dict], fields: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
            n += 1
    return n


def read_csv(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def update_status(source: str, ok: bool, message: str, **extra) -> None:
    """data/status.json 에 소스별 마지막 실행 결과를 남긴다(키워드 매니저가 읽음)."""
    path = DATA / "status.json"
    status = {}
    if path.exists():
        try:
            status = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            status = {}
    status[source] = {
        "ok": ok,
        "message": message,
        "run_at_kst": dt.datetime.now(KST).isoformat(timespec="seconds"),
        **extra,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
