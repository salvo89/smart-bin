# -*- coding: utf-8 -*-
"""Validate every comune/via like the app's "Mostra calendario" flow.

Fails if any via in docs/calendars/index.json points to a calendar base that
has no parseable *-YYYY.h for the app's active years (last 2 in years[]).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
INDEX_PATH = DOCS / "calendars" / "index.json"
ENTRY_RE = re.compile(r"\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(-?\d+)\s*\}")


def normalize_calendar_base(path: str) -> str:
    if not path:
        return path
    s = str(path)
    s = re.sub(r"-\d{4}\.h$", "", s, flags=re.I)
    s = re.sub(r"\.h$", "", s, flags=re.I)
    return s


def active_years(idx: dict) -> list[int]:
    years = sorted({int(y) for y in idx.get("years", []) if int(y) > 2000})
    return years[-2:] if years else []


def parse_entries(text: str) -> list[tuple[int, int, int, int]]:
    return [
        (int(m[0]), int(m[1]), int(m[2]), int(m[3]))
        for m in ENTRY_RE.findall(text)
    ]


def load_calendar(base: str, years: list[int]) -> tuple[int, int, str | None]:
    """Returns (loaded_years, entry_count, error)."""
    base = normalize_calendar_base(base)
    merged: list[tuple[int, int, int, int]] = []
    loaded = 0
    parse_err: str | None = None
    for year in years:
        path = DOCS / f"{base}-{year}.h"
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        entries = parse_entries(text)
        if not entries:
            parse_err = f"Nessuna entry calendario in {path.name}"
            continue
        merged.extend(entries)
        loaded += 1
    if not loaded:
        return 0, 0, parse_err or f"Nessun calendario anno per {base}"
    return loaded, len(merged), None


def validate(idx: dict) -> dict:
    years = active_years(idx)
    comuni = idx.get("comuni") or []
    failures: list[dict] = []
    ok_by_cal: dict[str, tuple[int, int]] = {}
    fail_by_cal: dict[str, str] = {}
    via_ok = 0
    via_fail = 0
    empty_vie_comuni: list[str] = []

    for comune in comuni:
        cid = comune.get("id") or ""
        cname = comune.get("name") or cid
        vie = comune.get("vie") or []
        if not vie:
            empty_vie_comuni.append(f"{cname} ({cid})")
            continue
        for via in vie:
            vname = via.get("name") or ""
            cal = normalize_calendar_base(via.get("calendar") or "")
            if not cal:
                via_fail += 1
                failures.append(
                    {
                        "comune": cname,
                        "comuneId": cid,
                        "via": vname,
                        "calendar": cal,
                        "error": "calendar path vuoto",
                    }
                )
                continue
            if cal in ok_by_cal:
                via_ok += 1
                continue
            if cal in fail_by_cal:
                via_fail += 1
                failures.append(
                    {
                        "comune": cname,
                        "comuneId": cid,
                        "via": vname,
                        "calendar": cal,
                        "error": fail_by_cal[cal],
                    }
                )
                continue
            loaded, n, err = load_calendar(cal, years)
            if err:
                fail_by_cal[cal] = err
                via_fail += 1
                failures.append(
                    {
                        "comune": cname,
                        "comuneId": cid,
                        "via": vname,
                        "calendar": cal,
                        "error": err,
                    }
                )
            else:
                ok_by_cal[cal] = (loaded, n)
                via_ok += 1

    by_cal: dict[str, list[dict]] = defaultdict(list)
    for f in failures:
        by_cal[f["calendar"]].append(f)

    return {
        "activeYears": years,
        "comuni": len(comuni),
        "vieOk": via_ok,
        "vieFail": via_fail,
        "calendarsOk": len(ok_by_cal),
        "calendarsFail": len(fail_by_cal),
        "emptyVieComuni": empty_vie_comuni,
        "failedCalendars": [
            {
                "calendar": cal,
                "error": items[0]["error"],
                "vieCount": len(items),
                "comuni": sorted({i["comune"] for i in items}),
                "sampleVies": [
                    f"{i['comune']} / {i['via']}" for i in items[:5]
                ],
            }
            for cal, items in sorted(
                by_cal.items(), key=lambda kv: (-len(kv[1]), kv[0])
            )
        ],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true", help="Print JSON report")
    p.add_argument(
        "--index",
        type=Path,
        default=INDEX_PATH,
        help="Path to calendars/index.json",
    )
    args = p.parse_args(argv)

    idx = json.loads(args.index.read_text(encoding="utf-8"))
    if not isinstance(idx.get("comuni"), list):
        print("index.json non valido: manca comuni[]", file=sys.stderr)
        return 2

    report = validate(idx)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"activeYears={report['activeYears']}")
        print(
            f"comuni={report['comuni']} "
            f"vieOk={report['vieOk']} vieFail={report['vieFail']}"
        )
        print(
            f"calendarsOk={report['calendarsOk']} "
            f"calendarsFail={report['calendarsFail']}"
        )
        if report["emptyVieComuni"]:
            print("Comuni senza vie:")
            for x in report["emptyVieComuni"]:
                print(f"  - {x}")
        for item in report["failedCalendars"]:
            print(f"\nFAIL {item['calendar']}")
            print(f"  error: {item['error']}")
            print(
                f"  vie={item['vieCount']} "
                f"comuni={', '.join(item['comuni'])}"
            )
            for s in item["sampleVies"]:
                print(f"    · {s}")

    if report["vieFail"] or report["emptyVieComuni"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
