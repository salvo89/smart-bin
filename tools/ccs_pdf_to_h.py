# -*- coding: utf-8 -*-
"""Convert Consorzio Chierese (CCS) calendar PDFs to Smart Bin .h data files."""
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

WEEKDAYS = {
    "LUNEDÌ",
    "LUNEDI",
    "MARTEDÌ",
    "MARTEDI",
    "MERCOLEDÌ",
    "MERCOLEDI",
    "GIOVEDÌ",
    "GIOVEDI",
    "VENERDÌ",
    "VENERDI",
    "SABATO",
    "DOMENICA",
}

BIN_ALIASES = [
    (re.compile(r"\bcarta\b", re.I), 0),
    (re.compile(r"\bca\b", re.I), 0),
    (re.compile(r"\borganico\b", re.I), 1),
    (re.compile(r"\borg\b", re.I), 1),
    (re.compile(r"\bnon\s*rec\b", re.I), 2),
    (re.compile(r"\bindifferenz", re.I), 2),
    (re.compile(r"\bplastica\b", re.I), 3),
    (re.compile(r"\bpla\b", re.I), 3),
    (re.compile(r"\bsfalci\b", re.I), 4),
    (re.compile(r"\bsfa\b", re.I), 4),
    (re.compile(r"\bverde\b", re.I), 4),
    (re.compile(r"\bvetro\b", re.I), 5),
    (re.compile(r"\bve\b", re.I), 5),
]


def normalize(s: str) -> str:
    return " ".join(s.replace("\ufffd", "'").split())


def extract_addresses(doc: fitz.Document) -> list[str]:
    page = doc[0]
    lines = [normalize(x) for x in page.get_text("text").splitlines()]
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        up = line.upper()
        if not line:
            continue
        if up.startswith(ADDRESS_PREFIXES) or any(
            up.startswith(p.strip()) for p in ADDRESS_PREFIXES
        ):
            if line not in seen:
                seen.add(line)
                out.append(line)
    return out


def _bins_from_label(text: str) -> list[int]:
    bins: list[int] = []
    for rx, idx in BIN_ALIASES:
        if rx.search(text):
            bins.append(idx)
    return sorted(set(bins))


def extract_entries(doc: fitz.Document) -> list[tuple[int, int, int, int]]:
    """Parse CCS tall calendar page (months in a multi-row grid)."""
    entries: list[tuple[int, int, int, int]] = []
    page = doc[1] if doc.page_count > 1 else doc[0]
    words = page.get_text("words")
    page_w = page.rect.width
    page_h = page.rect.height

    years_at: list[tuple[float, float, int]] = []
    month_headers: list[tuple[float, float, int]] = []
    for x0, y0, _x1, _y1, text, *_ in words:
        t = text.strip()
        up = t.upper()
        if re.fullmatch(r"20\d{2}", t) and y0 < 1200:
            years_at.append((x0, y0, int(t)))
        if up in MONTHS and y0 < 1200:
            month_headers.append((x0, y0, MONTHS[up]))

    # Pair each month header with nearest year on same row.
    resolved: list[tuple[float, float, int, int]] = []
    for mx, my, month in month_headers:
        year = None
        best = 1e9
        for yx, yy, yv in years_at:
            if abs(yy - my) > 20:
                continue
            dist = abs(yx - mx)
            if dist < best:
                best = dist
                year = yv
        if year is None:
            continue
        resolved.append((mx, my, month, year))

    if not resolved:
        return []

    # Group headers into rows by y.
    resolved.sort(key=lambda item: (round(item[1] / 20.0), item[0]))
    rows: list[list[tuple[float, float, int, int]]] = []
    for item in resolved:
        if not rows or abs(item[1] - rows[-1][0][1]) > 40:
            rows.append([item])
        else:
            rows[-1].append(item)

    row_ys = [min(it[1] for it in row) for row in rows]
    columns: list[tuple[float, float, float, float, int, int]] = []
    for row_idx, row in enumerate(rows):
        row = sorted(row, key=lambda item: item[0])
        y_top = row_ys[row_idx] + 10
        y_bot = (row_ys[row_idx + 1] - 10) if row_idx + 1 < len(rows) else min(page_h - 80, y_top + 340)
        for i, (mx, _my, month, year) in enumerate(row):
            x_left = mx - 15
            x_right = row[i + 1][0] - 5 if i + 1 < len(row) else page_w - 10
            columns.append((x_left, x_right, y_top, y_bot, month, year))

    for x0, x1, y0, y1, month, year in columns:
        day_rows: dict[int, float] = {}
        label_rows: list[tuple[float, str]] = []
        for wx0, wy0, _wx1, _wy1, text, *_ in words:
            if not (x0 <= wx0 < x1 and y0 <= wy0 <= y1):
                continue
            t = normalize(text)
            if not t:
                continue
            up = t.upper()
            if re.fullmatch(r"\d{1,2}", t):
                day = int(t)
                if 1 <= day <= 31 and (wx0 - x0) < 45:
                    day_rows[day] = wy0
                continue
            if up in WEEKDAYS or up in MONTHS or re.fullmatch(r"20\d{2}", t):
                continue
            if _bins_from_label(t) or t.lower() in {
                "non",
                "rec",
                "-",
                "carta",
                "organico",
                "org",
                "pla",
                "ve",
                "ca",
                "sfa",
            }:
                label_rows.append((wy0, t))

        label_rows.sort()
        clusters: list[tuple[float, str]] = []
        if label_rows:
            cur_y, cur_parts = label_rows[0][0], [label_rows[0][1]]
            for y, tok in label_rows[1:]:
                if abs(y - cur_y) <= 3:
                    cur_parts.append(tok)
                else:
                    clusters.append((cur_y, " ".join(cur_parts)))
                    cur_y, cur_parts = y, [tok]
            clusters.append((cur_y, " ".join(cur_parts)))

        for day, dy in day_rows.items():
            phrase = None
            best = 8.0
            for ly, text in clusters:
                dist = abs(ly - dy)
                if dist < best:
                    best = dist
                    phrase = text
            if not phrase:
                continue
            for b in _bins_from_label(phrase):
                entries.append((year, month, day, b))

    return sorted(set(entries))


def convert_pdf(
    source: str,
    *,
    slug: str,
    comune: str,
    zone_label: str,
    outdir: Path,
    work_pdf: Path,
    provider: str = "CCS",
) -> dict:
    pdf_path = download_if_needed(source, work_pdf)
    doc = fitz.open(pdf_path)
    if pdf_path.read_bytes()[:4] != b"%PDF":
        raise RuntimeError(f"Not a PDF: {pdf_path} ({pdf_path.read_bytes()[:40]!r})")

    addresses = extract_addresses(doc)
    entries = extract_entries(doc)
    if not entries:
        raise RuntimeError(f"No entries extracted for {slug}")

    grouped: dict[int, list[tuple[int, int, int, int]]] = defaultdict(list)
    for item in entries:
        grouped[item[0]].append(item)

    outdir.mkdir(parents=True, exist_ok=True)
    for year, year_entries in sorted(grouped.items()):
        # Keep only Oct 2025+ useful range; still write 2025 if present
        write_year_file(
            out_path=outdir / f"{slug}-{year}.h",
            comune_name=comune,
            zone_label=zone_label,
            provider=provider,
            addresses=addresses,
            year=year,
            entries=sorted(set(year_entries)),
        )

    return {
        "years": sorted(grouped),
        "entries": {str(y): len(grouped[y]) for y in grouped},
        "addresses": addresses,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("--slug", required=True)
    p.add_argument("--comune", required=True)
    p.add_argument("--zone", required=True)
    p.add_argument("--outdir", default="docs/calendars")
    p.add_argument("--work-pdf", default="tmp_calendars/ccs/_one.pdf")
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
