# -*- coding: utf-8 -*-
"""Analyze docs/calendars/*-YYYY.h for anomalous entry counts.

Severity:
  broken   — <10 entries (extraction failure)
  critical — <50 entries and not a recognized sparse pattern
  alert    — IQR low outlier (< Q1 - 1.5*IQR), needs review
  high     — IQR high outlier
  ok       — within normal range (or sparse-by-design Indifferenziato)

Sparse-by-design (ACSEL isole di prossimità): only bin 2, 20–60 entries,
at least 10 distinct months → treated as ok (not critical).
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAL_DIR = ROOT / "docs" / "calendars"
ENTRY_RE = re.compile(
    r"\{\s*(\d{4})\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}"
)


def analyze_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    year_m = re.search(r"-(\d{4})\.h$", path.name)
    year = int(year_m.group(1)) if year_m else None
    matches = list(ENTRY_RE.finditer(text))
    entries = []
    months: set[int] = set()
    bins: set[int] = set()
    for m in matches:
        y, mo, d, b = (int(m.group(i)) for i in range(1, 5))
        if year is not None and y != year:
            continue
        entries.append((y, mo, d, b))
        months.add(mo)
        bins.add(b)
    return {
        "file": path.name,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "year": year,
        "lines": len(lines),
        "entries": len(entries),
        "months": len(months),
        "month_set": sorted(months),
        "bins": sorted(bins),
    }


def is_sparse_indiff(row: dict) -> bool:
    """Solo Indifferenziato (bin 2), copertura annuale, ~settimanale/quindicinale."""
    return (
        row["bins"] == [2]
        and 20 <= row["entries"] <= 60
        and row["months"] >= 10
    )


def classify(rows: list[dict]) -> list[dict]:
    ents = [r["entries"] for r in rows]
    if len(ents) < 4:
        for r in rows:
            r["severity"] = "broken" if r["entries"] < 10 else "ok"
            r["reason"] = "sample too small for IQR" if r["severity"] == "ok" else "quasi vuoto (<10 entry)"
        return rows

    def pct(vals: list[int], p: float) -> float:
        s = sorted(vals)
        i = int(round((p / 100) * (len(s) - 1)))
        return float(s[i])

    q1, q3 = pct(ents, 25), pct(ents, 75)
    iqr = q3 - q1
    low = q1 - 1.5 * iqr
    high = q3 + 1.5 * iqr

    for r in rows:
        e = r["entries"]
        if e < 10:
            r["severity"] = "broken"
            r["reason"] = "quasi vuoto (<10 entry)"
        elif is_sparse_indiff(r):
            r["severity"] = "ok"
            r["reason"] = "sparse Indifferenziato (design)"
        elif e < 50:
            r["severity"] = "critical"
            r["reason"] = "fortemente incompleto (<50 entry)"
        elif e < low:
            r["severity"] = "alert"
            r["reason"] = f"outlier IQR basso (<{int(low)} entry)"
        elif e > high:
            r["severity"] = "high"
            r["reason"] = f"outlier IQR alto (>{int(high)} entry)"
        else:
            r["severity"] = "ok"
            r["reason"] = ""
        r["iqr_low"] = low
        r["iqr_high"] = high
        r["median"] = statistics.median(ents)
    return rows


def analyze(year: int | None = None, paths: list[Path] | None = None) -> dict:
    if paths:
        files = sorted(paths)
    elif year:
        files = sorted(CAL_DIR.glob(f"*-{year}.h"))
    else:
        files = sorted(CAL_DIR.glob("*-20*.h"))

    rows = [analyze_file(f) for f in files]
    if year:
        rows = [r for r in rows if r["year"] == year]
    rows = classify(rows)

    ents = [r["entries"] for r in rows]
    sev = Counter(r["severity"] for r in rows)
    alerts = [r for r in rows if r["severity"] not in ("ok",)]
    alerts.sort(
        key=lambda r: (
            {"broken": 0, "critical": 1, "alert": 2, "high": 3}.get(r["severity"], 9),
            r["entries"],
            r["file"],
        )
    )

    buckets = [
        {"label": "0–9", "count": sum(1 for e in ents if e < 10)},
        {"label": "10–49", "count": sum(1 for e in ents if 10 <= e < 50)},
        {"label": "50–99", "count": sum(1 for e in ents if 50 <= e < 100)},
        {"label": "100–149", "count": sum(1 for e in ents if 100 <= e < 150)},
        {"label": "150–199", "count": sum(1 for e in ents if 150 <= e < 200)},
        {"label": "200–299", "count": sum(1 for e in ents if 200 <= e < 300)},
        {"label": "300+", "count": sum(1 for e in ents if e >= 300)},
    ]

    return {
        "year": year,
        "total": len(rows),
        "median_entries": statistics.median(ents) if ents else 0,
        "mean_entries": round(statistics.mean(ents), 1) if ents else 0,
        "min_entries": min(ents) if ents else 0,
        "max_entries": max(ents) if ents else 0,
        "iqr_low": rows[0]["iqr_low"] if rows else None,
        "iqr_high": rows[0]["iqr_high"] if rows else None,
        "severity_counts": dict(sev),
        "alert_total": len(alerts),
        "buckets": buckets,
        "alerts": [
            {
                "file": r["file"],
                "path": r["path"],
                "entries": r["entries"],
                "lines": r["lines"],
                "months": r["months"],
                "bins": r["bins"],
                "severity": r["severity"],
                "reason": r["reason"],
            }
            for r in alerts
        ],
        "files": rows,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--year", type=int, default=2026)
    p.add_argument("--json", action="store_true", help="Print full JSON")
    p.add_argument(
        "--fail-on",
        choices=["none", "broken", "critical", "alert"],
        default="critical",
        help="Exit 1 if any finding at this severity or worse",
    )
    p.add_argument("files", nargs="*", help="Optional specific .h paths")
    args = p.parse_args()

    paths = [Path(f) for f in args.files] if args.files else None
    report = analyze(year=args.year if not paths else None, paths=paths)

    if args.json:
        slim = {k: v for k, v in report.items() if k != "files"}
        print(json.dumps(slim, indent=2))
    else:
        print(
            f"year={report['year']} files={report['total']} "
            f"median={report['median_entries']} "
            f"alerts={report['alert_total']} "
            f"sev={report['severity_counts']}"
        )
        for a in report["alerts"]:
            print(
                f"  {a['severity']:8s} {a['entries']:4d}e {a['lines']:4d}L "
                f"{a['months']:2d}m bins={a['bins']}  {a['file']}  ({a['reason']})"
            )

    order = ["broken", "critical", "alert", "high"]
    fail_rank = {"none": 99, "broken": 0, "critical": 1, "alert": 2}[args.fail_on]
    worst = min(
        (order.index(a["severity"]) for a in report["alerts"] if a["severity"] in order),
        default=99,
    )
    return 1 if worst <= fail_rank else 0


if __name__ == "__main__":
    raise SystemExit(main())
