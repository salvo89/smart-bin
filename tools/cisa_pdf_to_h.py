# -*- coding: utf-8 -*-
"""Convert CISA ecocalendar PDFs (Ciriè-style diary) to Escilo .h files."""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.covar14_pdf_to_h import ADDRESS_PREFIXES, write_year_file  # noqa: E402
from tools.download_safe import download_if_needed  # noqa: E402

MONTHS = {
    "GENNAIO": 1,
    "FEBBRAIO": 2,
    "MARZO": 3,
    "APRILE": 4,
    "MAGGIO": 5,
    "GIUGNO": 6,
    "LUGLIO": 7,
    "AGOSTO": 8,
    "SETTEMBRE": 9,
    "OTTOBRE": 10,
    "NOVEMBRE": 11,
    "DICEMBRE": 12,
}

BIN_MAP = {"C": 0, "O": 1, "I": 2, "P": 3, "S": 4, "V": 5}


def extract_addresses(doc: fitz.Document) -> list[str]:
    # Streets usually on early pages after cover.
    out: list[str] = []
    seen: set[str] = set()
    for page_index in range(min(8, doc.page_count)):
        for line in doc[page_index].get_text("text").splitlines():
            line = " ".join(line.replace("\ufffd", "'").split()).strip(" •\t")
            if not line:
                continue
            up = line.upper()
            if up.startswith(ADDRESS_PREFIXES) or any(
                up.startswith(p.strip()) for p in ADDRESS_PREFIXES
            ):
                if line not in seen and len(line) > 3:
                    seen.add(line)
                    out.append(line)
    return out


def _page_year_month(page: fitz.Page) -> tuple[int, int] | None:
    words = page.get_text("words")
    years = [(w[0], w[1], int(w[4])) for w in words if re.fullmatch(r"20\d{2}", w[4].strip())]
    months = [
        (w[0], w[1], MONTHS[w[4].strip().upper()])
        for w in words
        if w[4].strip().upper() in MONTHS
    ]
    if not years or not months:
        return None
    # Prefer year/month near top-left of calendar block.
    year = min(years, key=lambda item: (item[1], item[0]))[2]
    month = min(months, key=lambda item: (item[1], item[0]))[2]
    return year, month


def extract_entries(doc: fitz.Document) -> dict[str, list[tuple[int, int, int, int]]]:
    """
    Return schedules keyed by column id ('c1', 'c2').
    CISA Zona A/B PDFs often show two letter-columns (ex-zone patterns).
    """
    by_col: dict[str, list[tuple[int, int, int, int]]] = defaultdict(list)

    for page in doc:
        ym = _page_year_month(page)
        if ym is None:
            continue
        year, month = ym
        # Skip obvious non-calendar pages without day numbers.
        words = page.get_text("words")
        days: list[tuple[int, float, float]] = []
        letters: list[tuple[str, float, float, float]] = []
        for x0, y0, x1, y1, text, *_ in words:
            t = text.strip()
            up = t.upper()
            if re.fullmatch(r"\d{1,2}", t) and x0 < 200:
                day = int(t)
                if 1 <= day <= 31:
                    days.append((day, x0, y0))
            if up in BIN_MAP and 150 < x0 < 520:
                width = x1 - x0
                # Legend letters on far right are larger / different; keep badge-sized.
                if 2.5 <= width <= 12:
                    letters.append((up, x0, y0, width))

        if len(days) < 10:
            continue

        # Deduplicate day numbers (keep leftmost).
        by_day: dict[int, tuple[int, float, float]] = {}
        for day, dx, dy in sorted(days, key=lambda item: item[1]):
            by_day.setdefault(day, (day, dx, dy))
        days = list(by_day.values())

        # Split letter columns by x.
        xs = sorted(lett[1] for lett in letters)
        if not xs:
            continue
        if max(xs) - min(xs) > 120:
            mid = (min(xs) + max(xs)) / 2.0
            col_letters = {
                "c1": [L for L in letters if L[1] < mid],
                "c2": [L for L in letters if L[1] >= mid],
            }
        else:
            col_letters = {"c1": letters}

        for col_id, col in col_letters.items():
            for day, _dx, dy in days:
                matched = {
                    L
                    for L, lx, ly, _w in col
                    if abs(ly - dy) <= 12
                }
                for letter in matched:
                    by_col[col_id].append((year, month, day, BIN_MAP[letter]))

    return {k: sorted(set(v)) for k, v in by_col.items() if v}


def convert_pdf(
    source: str,
    *,
    comune: str,
    zone_base: str,
    slug_base: str,
    outdir: Path,
    work_pdf: Path,
) -> list[dict]:
    pdf_path = download_if_needed(source, work_pdf)
    if pdf_path.read_bytes()[:4] != b"%PDF":
        raise RuntimeError(f"Not a PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    addresses = extract_addresses(doc)
    schedules = extract_entries(doc)
    if not schedules:
        raise RuntimeError(f"No entries for {slug_base}")

    outdir.mkdir(parents=True, exist_ok=True)
    results = []
    multi = len(schedules) > 1
    for col_id, entries in sorted(schedules.items()):
        suffix = col_id if multi else ""
        zone_label = f"{zone_base} {col_id.upper()}" if multi else zone_base
        slug = f"{slug_base}-{col_id}" if multi else slug_base
        grouped: dict[int, list] = defaultdict(list)
        for item in entries:
            grouped[item[0]].append(item)
        for year, year_entries in sorted(grouped.items()):
            if year > 2027:
                continue
            write_year_file(
                out_path=outdir / f"{slug}-{year}.h",
                comune_name=comune,
                zone_label=zone_label,
                provider="CISA",
                addresses=addresses if not multi or col_id == "c1" else [],
                year=year,
                entries=sorted(set(year_entries)),
            )
        results.append(
            {
                "slug": slug,
                "zone_label": zone_label,
                "years": sorted(y for y in grouped if y <= 2027),
                "entries": {str(y): len(grouped[y]) for y in grouped if y <= 2027},
                "addresses": addresses if not multi or col_id == "c1" else [],
                "suffix": suffix,
            }
        )
    return results


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("--slug-base", required=True)
    p.add_argument("--comune", required=True)
    p.add_argument("--zone", required=True)
    p.add_argument("--outdir", default="docs/calendars")
    p.add_argument("--work-pdf", default="tmp_calendars/cisa/_one.pdf")
    args = p.parse_args()
    info = convert_pdf(
        args.source,
        comune=args.comune,
        zone_base=args.zone,
        slug_base=args.slug_base,
        outdir=Path(args.outdir),
        work_pdf=Path(args.work_pdf),
    )
    print(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
