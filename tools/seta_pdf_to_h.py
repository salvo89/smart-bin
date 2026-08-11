"""Convert SETA ecocalendar PDFs to Escilo calendar data files."""
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

from tools.covar14_pdf_to_h import download_if_needed, write_year_file

# SETA: C Carta, O Organico, I Indiff., P Plastica, S Sfalci(=Verde), V Vetro
SETA_BIN_MAP = {
    "C": 0,
    "O": 1,
    "I": 2,
    "P": 3,
    "S": 4,
    "V": 5,
}

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


def detect_page_columns(page: fitz.Page, page_index: int) -> list[tuple[float, int, int]]:
    words = page.get_text("words")
    header_words = [w for w in words if 70 <= w[1] < 120]
    years_by_x: list[tuple[float, float, int]] = []
    for x0, y0, _x1, _y1, text, *_ in header_words:
        if re.fullmatch(r"20\d{2}", text.strip()):
            years_by_x.append((x0, y0, int(text.strip())))

    columns: list[tuple[float, int, int]] = []
    for x0, y0, _x1, _y1, text, *_ in header_words:
        name = text.strip().upper()
        if name not in MONTHS or text.strip() != name:
            continue
        month = MONTHS[name]
        year = None
        for yx, yy, yval in years_by_x:
            if abs(yy - y0) < 20 and abs(yx - x0) < 100:
                year = yval
                break
        if year is None:
            if page_index == 1 and month <= 2:
                year = 2027
            else:
                year = 2026
        columns.append((x0, month, year))

    columns.sort(key=lambda item: item[0])
    return columns

COL_WIDTH = 138
ROW_Y_MIN = 85
ROW_Y_MAX = 420
DAY_LEFT_MAX = 24
DAY_RIGHT_MIN = 130
DAY_RIGHT_MAX = 145
BIN_X_MIN = 25
BIN_X_MAX = 95
DAY_MATCH_Y = 14

WEEKDAYS = re.compile(
    r"^(luned|marted|mercoled|gioved|venerd|sabato|domenic)",
    re.I,
)


def _month_words(page: fitz.Page, col_x: int) -> list[tuple]:
    return [
        w
        for w in page.get_text("words")
        if ROW_Y_MIN <= w[1] <= ROW_Y_MAX
        and (
            col_x <= w[0] < col_x + COL_WIDTH
            or col_x + DAY_RIGHT_MIN <= w[0] < col_x + DAY_RIGHT_MAX
        )
    ]


def _day_from_word(col_x: int, x0: float, token: str) -> int | None:
    if not re.fullmatch(r"\d{1,2}", token):
        return None
    day = int(token)
    if not 1 <= day <= 31:
        return None
    rel_x = x0 - col_x
    if rel_x <= DAY_LEFT_MAX or DAY_RIGHT_MIN <= rel_x <= DAY_RIGHT_MAX:
        return day
    return None


def extract_entries(doc: fitz.Document) -> list[tuple[int, int, int, int]]:
    entries: list[tuple[int, int, int, int]] = []

    for page_index in range(min(2, doc.page_count)):
        page = doc[page_index]
        columns = detect_page_columns(page, page_index)
        if not columns:
            continue

        for col_x, month, year in columns:
            words = _month_words(page, col_x)
            days: list[tuple[int, float]] = []
            bins_by_y: dict[int, set[str]] = defaultdict(set)

            for x0, y0, _x1, _y1, text, *_ in words:
                token = text.strip().upper()
                if not token:
                    continue
                rel_x = x0 - col_x
                day = _day_from_word(col_x, x0, token)
                if day is not None:
                    days.append((day, y0))
                    continue
                if BIN_X_MIN <= rel_x <= BIN_X_MAX and token in SETA_BIN_MAP:
                    bins_by_y[int(round(y0 / 6.0))].add(token)

            if not days:
                continue

            bin_items = sorted(
                (keys * 6.0, bins) for keys, bins in bins_by_y.items() if bins
            )

            for day, y_day in days:
                if day > cal_mod.monthrange(year, month)[1]:
                    continue
                matched: set[str] = set()
                for y_bins, letters in bin_items:
                    if abs(y_bins - y_day) <= DAY_MATCH_Y:
                        matched |= letters
                for letter in sorted(matched):
                    entries.append((year, month, day, SETA_BIN_MAP[letter]))

    return sorted(set(entries))


def _is_civic_extrema(line: str) -> bool:
    if re.fullmatch(r"[\d,;\s\+]+", line):
        return True
    if re.match(r"^[DP]\(", line):
        return True
    if line.upper().startswith(("DA ", "FINO A ", "TRANNE(", "P(", "D(")):
        return True
    return False


def extract_zone_addresses(zone_pdf: Path, zone_num: int) -> list[str]:
    if not zone_pdf.exists():
        return []
    doc = fitz.open(zone_pdf)
    text = "\n".join(page.get_text("text") for page in doc)
    text = text.replace("\ufffd", " ")
    zone_tag = f"Z{zone_num}"
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    addresses: list[str] = []
    skip_headers = {
        "SERVIZIO DI RACCOLTA",
        "Toponimo",
        "Estremi civici",
        "NON",
        "RECUPERABILE",
        "ORGANICO",
        "PLASTICA",
        "CARTA",
        "VETRO",
        "SFALCI",
        "Fascia oraria",
    }

    i = 0
    while i < len(lines):
        line = lines[i]
        if re.fullmatch(r"Z\d+", line):
            if line != zone_tag:
                i += 1
                continue
            i += 1
            while i < len(lines) and not re.fullmatch(r"Z\d+", lines[i]):
                row = lines[i]
                if row in skip_headers or re.search(r"Programma attiv", row, re.I):
                    i += 1
                    continue
                if WEEKDAYS.match(row):
                    break
                if re.fullmatch(r"\d{2}\.\d{2}-\d{2}\.\d{2}", row):
                    i += 1
                    continue
                if re.search(r"dal 1 marzo al 30", row, re.I):
                    i += 1
                    continue
                if _is_civic_extrema(row):
                    if addresses:
                        addresses[-1] = f"{addresses[-1]}, {row}"
                    i += 1
                    continue
                if len(row) >= 3 and row not in addresses:
                    addresses.append(row)
                i += 1
            continue
        i += 1
    return addresses


def convert_pdf(
    source: str,
    *,
    slug: str,
    comune: str,
    zone_label: str,
    zone_num: int | None,
    zone_pdf: Path | None,
    outdir: Path,
    work_pdf: Path,
) -> dict:
    pdf_path = download_if_needed(source, work_pdf)
    doc = fitz.open(pdf_path)
    entries = extract_entries(doc)
    if not entries:
        raise RuntimeError(f"No calendar entries extracted from {source}")

    addresses: list[str] = []
    if zone_num is not None and zone_pdf is not None:
        addresses = extract_zone_addresses(zone_pdf, zone_num)

    grouped: dict[int, list[tuple[int, int, int, int]]] = defaultdict(list)
    for item in entries:
        grouped[item[0]].append(item)

    outdir.mkdir(parents=True, exist_ok=True)
    for year, year_entries in sorted(grouped.items()):
        out_path = outdir / f"{slug}-{year}.h"
        write_year_file(
            out_path=out_path,
            comune_name=comune,
            zone_label=zone_label,
            provider="SETA",
            addresses=addresses,
            year=year,
            entries=year_entries,
        )

    return {
        "years": sorted(grouped),
        "entries": {str(y): len(grouped[y]) for y in grouped},
        "addresses": len(addresses),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--comune", required=True)
    parser.add_argument("--zone", required=True)
    parser.add_argument("--zone-num", type=int)
    parser.add_argument("--zone-pdf")
    parser.add_argument("--outdir", default="docs/calendars")
    parser.add_argument("--work-pdf", default="tmp_calendars/seta/_one.pdf")
    args = parser.parse_args()

    info = convert_pdf(
        args.source,
        slug=args.slug,
        comune=args.comune,
        zone_label=args.zone,
        zone_num=args.zone_num,
        zone_pdf=Path(args.zone_pdf) if args.zone_pdf else None,
        outdir=Path(args.outdir),
        work_pdf=Path(args.work_pdf),
    )
    print(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
