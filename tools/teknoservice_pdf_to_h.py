# -*- coding: utf-8 -*-
"""Convert TeknoService/CCA Canavese weekly-grid PDFs to Escilo .h files."""
from __future__ import annotations

import argparse
import calendar as cal_mod
import re
import sys
from collections import defaultdict
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.covar14_pdf_to_h import write_year_file  # noqa: E402
from tools.download_safe import download_if_needed  # noqa: E402

BIN_LABELS: list[tuple[str, int]] = [
    ("ORGANICO", 1),
    ("INDIFFERENZIATO", 2),
    ("CARTA", 0),
    ("PLASTICA", 3),
    ("VETRO", 5),
]


def parse_weekly_schedule(page: fitz.Page) -> dict[int, list[int]]:
    words = page.get_text("words")

    header_tokens: list[tuple[str, float, float]] = []
    for x0, y0, _x1, _y1, text, *_ in words:
        if text in {"L", "M", "G", "V", "S"} and 250 < x0 < 750:
            header_tokens.append((text, x0, y0))

    if not header_tokens:
        return {}

    header_y = min(y for _ch, _x, y in header_tokens)
    row = sorted(
        [(ch, x) for ch, x, y in header_tokens if abs(y - header_y) < 20],
        key=lambda t: t[1],
    )

    unique_cols: list[tuple[int, float]] = []
    m_idx = 0
    for ch, x in row:
        if ch == "L":
            unique_cols.append((0, x))
        elif ch == "M":
            unique_cols.append((m_idx, x))
            m_idx += 1
        elif ch == "G":
            unique_cols.append((3, x))
        elif ch == "V":
            unique_cols.append((4, x))
        elif ch == "S":
            unique_cols.append((5, x))

    bin_rows: list[tuple[int, float]] = []
    for label, bin_id in BIN_LABELS:
        for x0, y0, _x1, _y1, text, *_ in words:
            if label in text.upper() and x0 < 220:
                bin_rows.append((bin_id, y0 + 18))
                break

    if not unique_cols or not bin_rows:
        return {}

    min_y = min(y for _b, y in bin_rows) - 35
    max_y = max(y for _b, y in bin_rows) + 35
    schedule: dict[int, set[int]] = defaultdict(set)

    for draw in page.get_drawings():
        fill = draw.get("fill")
        rect = draw.get("rect")
        if not fill or not rect:
            continue
        if not (38 <= rect.width <= 65 and 38 <= rect.height <= 65):
            continue
        cx = (rect.x0 + rect.x1) / 2
        cy = (rect.y0 + rect.y1) / 2
        if cy < min_y or cy > max_y or cx < 250:
            continue

        wd_idx = min(range(len(unique_cols)), key=lambda i: abs(cx - unique_cols[i][1]))
        if abs(cx - unique_cols[wd_idx][1]) > 48:
            continue
        wd = unique_cols[wd_idx][0]

        row = min(bin_rows, key=lambda item: abs(cy - item[1]))
        if abs(cy - row[1]) > 40:
            continue
        schedule[wd].add(row[0])

    return {wd: sorted(bins) for wd, bins in schedule.items()}


def expand_year(schedule: dict[int, list[int]], year: int) -> list[tuple[int, int, int, int]]:
    entries: list[tuple[int, int, int, int]] = []
    for month in range(1, 13):
        for day in range(1, cal_mod.monthrange(year, month)[1] + 1):
            wd = cal_mod.weekday(year, month, day)
            for bin_id in schedule.get(wd, []):
                entries.append((year, month, day, bin_id))
    return entries


def detect_year(doc: fitz.Document) -> int:
    for page in doc:
        for _x0, _y0, _x1, _y1, text, *_ in page.get_text("words"):
            m = re.search(r"20\d{2}", text)
            if m:
                return int(m.group())
    return 2026


def convert_pdf(
    source: str,
    *,
    slug_base: str,
    comune: str,
    outdir: Path,
    work_pdf: Path,
    years: list[int] | None = None,
) -> dict:
    pdf_path = download_if_needed(source, work_pdf)
    doc = fitz.open(pdf_path)
    if pdf_path.read_bytes()[:4] != b"%PDF":
        raise RuntimeError(f"Not a PDF: {pdf_path}")

    schedule: dict[int, list[int]] = {}
    for page in doc:
        schedule = parse_weekly_schedule(page)
        if schedule:
            break

    if not schedule:
        raise RuntimeError(f"No weekly grid found for {slug_base}")

    slug = f"{slug_base}-zunica"
    year_list = years or [detect_year(doc)]
    outdir.mkdir(parents=True, exist_ok=True)

    entry_counts: dict[str, int] = {}
    for year in year_list:
        entries = expand_year(schedule, year)
        write_year_file(
            out_path=outdir / f"{slug}-{year}.h",
            comune_name=comune,
            zone_label="Zona unica",
            provider="TeknoService",
            addresses=[],
            year=year,
            entries=entries,
        )
        entry_counts[str(year)] = len(entries)

    return {
        "slug": slug,
        "zone_label": "Zona unica",
        "years": year_list,
        "entries": entry_counts,
        "addresses": [],
        "schedule": schedule,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("--slug-base", required=True)
    p.add_argument("--comune", required=True)
    p.add_argument("--outdir", default="docs/calendars")
    p.add_argument("--work-pdf", default="tmp_calendars/teknoservice/_one.pdf")
    args = p.parse_args()
    info = convert_pdf(
        args.source,
        slug_base=args.slug_base,
        comune=args.comune,
        outdir=Path(args.outdir),
        work_pdf=Path(args.work_pdf),
    )
    print(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
