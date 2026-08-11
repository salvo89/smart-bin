# -*- coding: utf-8 -*-
"""Convert SCS Ivrea annual calendar PDFs (color grid) to Escilo .h files."""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.covar14_pdf_to_h import write_year_file  # noqa: E402
from tools.download_safe import download_if_needed  # noqa: E402

MONTH_NUM = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}

COLOR_BINS: dict[tuple[float, float, float], int] = {
    (0.8, 0.6, 0.0): 1,  # organico
    (1.0, 1.0, 0.0): 0,  # carta
    (0.88, 0.18, 0.14): 0,  # carta (alt)
    (1.0, 0.6, 0.4): 3,  # plastica / multimateriale
    (0.18, 0.18, 0.18): 2,  # indifferenziato
    (0.27, 0.28, 0.27): 2,
    (0.63, 0.62, 0.62): 2,
    (0.42, 0.41, 0.41): 2,
    # Verde / sfalci (calendari dedicati SCS)
    (0.22, 0.65, 0.47): 4,
    (0.0, 0.8, 0.4): 4,
    (0.75, 0.91, 0.85): 4,
}


def nearest_bin(rgb: tuple[float, ...]) -> int | None:
    rounded = tuple(round(c, 2) for c in rgb[:3])
    best = None
    best_dist = 1e9
    for color, bin_id in COLOR_BINS.items():
        dist = sum((a - b) ** 2 for a, b in zip(rounded, color))
        if dist < best_dist:
            best_dist = dist
            best = bin_id
    return best if best_dist < 0.12 else None


def month_rows(page: fitz.Page) -> list[tuple[int, float, float]]:
    rows: list[tuple[str, float, float]] = []
    for x0, y0, _x1, _y1, text, *_ in page.get_text("words"):
        name = text.strip().lower()
        if name in MONTH_NUM:
            rows.append((name, y0, x0))
    rows.sort(key=lambda item: item[1])
    out: list[tuple[int, float, float]] = []
    for i, (name, y, x) in enumerate(rows):
        y1 = rows[i + 1][1] - 5 if i + 1 < len(rows) else page.rect.height - 10
        out.append((MONTH_NUM[name], y, y1))
    return out


def day_columns(page: fitz.Page, month_y0: float, month_y1: float) -> list[tuple[int, float]]:
    cols: list[tuple[int, float]] = []
    for x0, y0, _x1, _y1, text, *_ in page.get_text("words"):
        if not (month_y0 - 20 <= y0 <= month_y0 + 15):
            continue
        if re.fullmatch(r"\d{1,2}", text):
            day = int(text)
            if 1 <= day <= 31:
                cols.append((day, x0))
    if not cols:
        return []
    # Deduplicate by day keeping leftmost x.
    by_day: dict[int, float] = {}
    for day, x in sorted(cols, key=lambda item: item[1]):
        by_day.setdefault(day, x)
    return sorted(by_day.items(), key=lambda item: item[1])


def extract_entries(page: fitz.Page, year: int) -> list[tuple[int, int, int, int]]:
    months = month_rows(page)
    if not months:
        return []

    day_cols_cache: dict[int, list[tuple[int, float]]] = {}
    for month, y0, y1 in months:
        day_cols_cache[month] = day_columns(page, y0, y1)

    entries: set[tuple[int, int, int, int]] = set()
    for draw in page.get_drawings():
        fill = draw.get("fill")
        rect = draw.get("rect")
        if not fill or not rect or rect.width < 4 or rect.height < 4:
            continue
        cx = (rect.x0 + rect.x1) / 2
        cy = (rect.y0 + rect.y1) / 2
        if cy < 130 or cx < 250:
            continue
        bin_id = nearest_bin(fill)
        if bin_id is None:
            continue

        month = None
        for m, y0, y1 in months:
            if y0 <= cy < y1:
                month = m
                break
        if month is None:
            continue

        cols = day_cols_cache.get(month) or []
        if not cols:
            continue
        day, dx = min(cols, key=lambda item: abs(cx - item[1]))
        if abs(cx - dx) > 20:
            continue
        entries.add((year, month, day, bin_id))

    return sorted(entries)


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
    slug: str,
    comune: str,
    zone_label: str,
    outdir: Path,
    work_pdf: Path,
) -> dict:
    pdf_path = download_if_needed(source, work_pdf)
    doc = fitz.open(pdf_path)
    if pdf_path.read_bytes()[:4] != b"%PDF":
        raise RuntimeError(f"Not a PDF: {pdf_path}")

    year = detect_year(doc)
    entries: list[tuple[int, int, int, int]] = []
    for page in doc:
        entries.extend(extract_entries(page, year))
    entries = sorted(set(entries))
    if not entries:
        raise RuntimeError(f"No entries extracted for {slug}")

    outdir.mkdir(parents=True, exist_ok=True)
    write_year_file(
        out_path=outdir / f"{slug}-{year}.h",
        comune_name=comune,
        zone_label=zone_label,
        provider="SCS",
        addresses=[],
        year=year,
        entries=entries,
    )
    return {
        "slug": slug,
        "zone_label": zone_label,
        "years": [year],
        "entries": {str(year): len(entries)},
        "addresses": [],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("--slug", required=True)
    p.add_argument("--comune", required=True)
    p.add_argument("--zone", required=True)
    p.add_argument("--outdir", default="docs/calendars")
    p.add_argument("--work-pdf", default="tmp_calendars/scs/_one.pdf")
    args = p.parse_args()
    info = convert_pdf(
        args.source,
        slug=args.slug,
        comune=args.comune,
        zone_label=args.zone,
        outdir=Path(args.outdir),
        work_pdf=Path(args.work_pdf),
    )
    print(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
