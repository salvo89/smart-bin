# -*- coding: utf-8 -*-
"""Convert ACSEL Val Susa calendar PDFs (color-coded annual grid) to Smart Bin .h files."""
from __future__ import annotations

import argparse
import calendar
import re
import sys
import unicodedata
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

# Legend swatches on ACSEL annual calendars (RGB 0..1).
COLOR_BINS: dict[tuple[float, float, float], int] = {
    (0.0, 0.44, 0.24): 2,  # indifferenziato
    (0.53, 0.34, 0.22): 1,  # organico
    (0.03, 0.3, 0.63): 5,  # vetro
    (1.0, 0.83, 0.0): 3,  # plastica
    (0.93, 0.11, 0.14): 0,  # carta
}

# Weekday labels in "solo Indifferenziato porta a porta" grids (accent-folded).
_WD_PREFIXES = ("sabat", "luned", "marted", "mercoled", "gioved", "venerd", "domenic")


def normalize(text: str) -> str:
    return " ".join(text.replace("\ufffd", "'").split())


def nearest_bin(rgb: tuple[float, ...]) -> int | None:
    best = None
    best_dist = 1e9
    rounded = tuple(round(c, 2) for c in rgb[:3])
    for color, bin_id in COLOR_BINS.items():
        dist = sum((a - b) ** 2 for a, b in zip(rounded, color))
        if dist < best_dist:
            best_dist = dist
            best = bin_id
    return best if best_dist < 0.08 else None


def extract_addresses(page: fitz.Page) -> list[str]:
    lines = [normalize(x) for x in page.get_text("text").splitlines()]
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if not line:
            continue
        up = line.upper()
        if up.startswith(ADDRESS_PREFIXES) or any(
            up.startswith(p.strip()) for p in ADDRESS_PREFIXES
        ):
            if line not in seen:
                seen.add(line)
                out.append(line)
        elif up.startswith("BORGATA ") or up.startswith("CASCINA "):
            if line not in seen:
                seen.add(line)
                out.append(line)
    return out


def zone_label_on_page(page: fitz.Page) -> str | None:
    for line in page.get_text("text").splitlines():
        m = re.search(r"ZONA\s*(\d+)", line, re.I)
        if m:
            return f"Zona {m.group(1)}"
    return None


def _fold_alpha(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text)
    return "".join(c for c in folded if c.isascii() and c.isalpha()).lower()


def _is_weekday_label(text: str) -> bool:
    token = _fold_alpha(text)
    return any(token.startswith(p) for p in _WD_PREFIXES) and 3 <= len(token) <= 12


def extract_indiff_weekday_grid(
    page: fitz.Page, year: int, *, bin_id: int = 2
) -> list[tuple[int, int, int, int]]:
    """Parse single-page ACSEL flyers with weekday+day columns (solo Indifferenziato).

    Used when other streams are isole di prossimità and the PDF has no color grid page.
    """
    words = page.get_text("words")
    months: list[tuple[float, float, int]] = []
    seen: set[str] = set()
    for x0, y0, x1, _y1, text, *_ in words:
        raw = text.strip()
        up = raw.upper()
        if up in MONTHS and up not in seen and raw.isupper():
            months.append(((x0 + x1) / 2, y0, MONTHS[up]))
            seen.add(up)
    if len(months) < 12:
        return []

    months = sorted(months, key=lambda t: (t[1], t[0]))
    y0 = months[0][1]
    row1 = sorted([m for m in months if abs(m[1] - y0) < 25], key=lambda t: t[0])
    row2 = sorted([m for m in months if abs(m[1] - y0) >= 25], key=lambda t: t[0])
    if len(row1) < 6 or len(row2) < 6:
        return []

    row2_y = row2[0][1]
    min_x = min(m[0] for m in months) - 50
    max_x = max(m[0] for m in months) + 80
    max_y = row2_y + 130

    labels = [
        (w[0], w[1], w[2], w[4])
        for w in words
        if _is_weekday_label(w[4]) and y0 - 5 < w[1] < max_y and min_x <= w[0] <= max_x
    ]
    days = [
        (w[0], w[1], w[2], int(w[4]))
        for w in words
        if w[4].isdigit()
        and 1 <= int(w[4]) <= 31
        and y0 + 5 < w[1] < max_y
        and min_x <= w[0] <= max_x
    ]

    entries: set[tuple[int, int, int, int]] = set()
    for lx0, ly0, _lx1, _lab in labels:
        best = None
        best_dist = 1e9
        for dx0, dy0, _dx1, day in days:
            if abs(dy0 - ly0) > 10 or dx0 < lx0 - 5:
                continue
            dist = dx0 - lx0
            if dist < best_dist:
                best_dist = dist
                best = day
        if best is None or best_dist > 80:
            continue
        row = row1 if ly0 < row2_y - 5 else row2
        month = min(row, key=lambda m: abs(m[0] - lx0))[2]
        if best <= calendar.monthrange(year, month)[1]:
            entries.add((year, month, best, bin_id))
    return sorted(entries)


def extract_color_grid_entries(page: fitz.Page, year: int) -> list[tuple[int, int, int, int]]:
    words = page.get_text("words")
    pw, ph = page.rect.width, page.rect.height
    landscape = pw > ph

    month_triplets: list[tuple[float, float, int]] = []
    for x0, y0, _x1, _y1, text, *_ in words:
        up = text.strip().upper()
        if up in MONTHS:
            month_triplets.append((x0, y0, MONTHS[up]))

    if not month_triplets:
        return []

    xs = [m[0] for m in month_triplets]
    ys = [m[1] for m in month_triplets]
    month_headers: list[tuple[float, float, int]]
    if max(xs) - min(xs) > max(ys) - min(ys):
        month_headers = sorted([(x, y, mon) for x, y, mon in month_triplets], key=lambda t: t[0])
    else:
        month_headers = sorted([(y, x, mon) for x, y, mon in month_triplets], key=lambda t: t[0])

    anchors: list[tuple[int, float, float, int]] = []
    if landscape:
        for i, (mx, _my, mon) in enumerate(month_headers):
            x0 = mx - 12
            x1 = month_headers[i + 1][0] - 8 if i + 1 < len(month_headers) else pw - 5
            for wx0, wy0, _wx1, _wy1, text, *_ in words:
                if x0 <= wx0 <= x1 and re.fullmatch(r"\d{1,2}", text):
                    day = int(text)
                    if 1 <= day <= 31:
                        anchors.append((day, wx0, wy0, mon))
    else:
        for i, (my, _mx, mon) in enumerate(month_headers):
            y0 = my - 12
            y1 = month_headers[i + 1][0] - 8 if i + 1 < len(month_headers) else ph - 5
            for wx0, wy0, _wx1, _wy1, text, *_ in words:
                if y0 <= wy0 <= y1 and re.fullmatch(r"\d{1,2}", text):
                    day = int(text)
                    if 1 <= day <= 31:
                        anchors.append((day, wx0, wy0, mon))

    fills: list[tuple[float, float, int]] = []
    for draw in page.get_drawings():
        fill = draw.get("fill")
        rect = draw.get("rect")
        if not fill or not rect or rect.height < 2 or rect.width < 2:
            continue
        if landscape and rect.y0 < 65:
            continue
        if not landscape and rect.x0 < 10:
            continue
        bin_id = nearest_bin(fill)
        if bin_id is None:
            continue
        fills.append(((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2, bin_id))

    entries: set[tuple[int, int, int, int]] = set()
    for cx, cy, bin_id in fills:
        best = None
        best_dist = 1e9
        for day, ax, ay, month in anchors:
            dist = ((cx - ax) ** 2 + (cy - ay) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best = (month, day, bin_id)
        if best and best_dist < 40:
            entries.add((year, best[0], best[1], best[2]))

    return sorted(entries)


def extract_entries(page: fitz.Page, year: int) -> list[tuple[int, int, int, int]]:
    color = extract_color_grid_entries(page, year)
    if len(color) >= 20:
        return color
    weekday = extract_indiff_weekday_grid(page, year)
    if len(weekday) > len(color):
        return weekday
    return color


def detect_year(doc: fitz.Document) -> int:
    for page in doc:
        for _x0, _y0, _x1, _y1, text, *_ in page.get_text("words"):
            m = re.fullmatch(r"20\d{2}", text.strip())
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
    zone_label: str | None = None,
) -> list[dict]:
    pdf_path = download_if_needed(source, work_pdf)
    doc = fitz.open(pdf_path)
    if pdf_path.read_bytes()[:4] != b"%PDF":
        raise RuntimeError(f"Not a PDF: {pdf_path}")

    year = detect_year(doc)
    results: list[dict] = []
    zone_pages: list[tuple[int, str | None, list[str], list[tuple[int, int, int, int]]]] = []

    for page_index in range(doc.page_count):
        page = doc[page_index]
        entries = extract_entries(page, year)
        if not entries:
            continue
        zone_pages.append(
            (page_index, zone_label_on_page(page), extract_addresses(page), entries)
        )

    if not zone_pages:
        raise RuntimeError(f"No calendar entries extracted for {slug_base}")

    if zone_label:
        all_entries: list[tuple[int, int, int, int]] = []
        all_addresses: list[str] = []
        for _pi, _zl, addrs, entries in zone_pages:
            all_entries.extend(entries)
            all_addresses.extend(addrs)
        m = re.search(r"(\d+)", zone_label)
        slug = f"{slug_base}-z{m.group(1)}" if m else f"{slug_base}-zunica"
        zone_pages = [(0, zone_label, all_addresses, sorted(set(all_entries)))]
    else:
        # Prefer color-grid pages (>=20). Keep weekday-grid pages (>=20) when
        # that is the only content (isole di prossimità / solo Indifferenziato).
        substantial = [zp for zp in zone_pages if len(zp[3]) >= 20]
        if substantial:
            zone_pages = substantial
        else:
            # Accept smaller weekday grids (biweekly ~26) if nothing better.
            modest = [zp for zp in zone_pages if len(zp[3]) >= 12]
            if modest:
                zone_pages = modest

    multi_zone = len(zone_pages) > 1 and not zone_label
    for page_index, zlabel, addresses, entries in zone_pages:
        if multi_zone:
            zslug = re.search(r"(\d+)", zlabel or "") if zlabel else None
            slug = f"{slug_base}-z{zslug.group(1)}" if zslug else f"{slug_base}-z{page_index + 1}"
            label = zlabel or f"Zona {page_index + 1}"
        else:
            slug = f"{slug_base}-zunica" if not zone_label else slug
            label = zone_label or "Zona unica"

        grouped: dict[int, list[tuple[int, int, int, int]]] = defaultdict(list)
        for item in entries:
            grouped[item[0]].append(item)

        outdir.mkdir(parents=True, exist_ok=True)
        years_written: list[int] = []
        for y, year_entries in sorted(grouped.items()):
            write_year_file(
                out_path=outdir / f"{slug}-{y}.h",
                comune_name=comune,
                zone_label=label,
                provider="ACSEL",
                addresses=addresses,
                year=y,
                entries=sorted(set(year_entries)),
            )
            years_written.append(y)

        results.append(
            {
                "slug": slug,
                "zone_label": label,
                "years": years_written,
                "entries": {str(y): len(grouped[y]) for y in years_written},
                "addresses": addresses,
            }
        )

    return results


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("--slug-base", required=True)
    p.add_argument("--comune", required=True)
    p.add_argument("--outdir", default="docs/calendars")
    p.add_argument("--work-pdf", default="tmp_calendars/acsel/_one.pdf")
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
