# -*- coding: utf-8 -*-
"""Convert CIDIU weekly HTML calendars to Escilo .h yearly data files."""
from __future__ import annotations

import argparse
import calendar as cal_mod
import re
import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.covar14_pdf_to_h import write_year_file  # noqa: E402
from tools.download_safe import download_bytes  # noqa: E402

def _norm_wd(s: str) -> str:
    s = s.lower()
    for a, b in (("à", "a"), ("è", "e"), ("é", "e"), ("ì", "i"), ("ò", "o"), ("ù", "u"), ("�", "e")):
        s = s.replace(a, b)
    return s


WEEKDAY_IT = {
    "lunedi": 0,
    "martedi": 1,
    "mercoledi": 2,
    "giovedi": 3,
    "venerdi": 4,
    "sabato": 5,
    "domenica": 6,
}

BIN_PATTERNS = [
    (re.compile(r"carta", re.I), 0),
    (re.compile(r"organico", re.I), 1),
    (re.compile(r"indifferenz", re.I), 2),
    (re.compile(r"plastica", re.I), 3),
    (re.compile(r"vetro", re.I), 5),
    (re.compile(r"lattine", re.I), 5),
    (re.compile(r"sfalc|verde|potatur", re.I), 4),
]


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.tables: list[list[list[str]]] = []
        self.cur: list[list[str]] | None = None
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.capture = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
            self.cur = []
        elif self.in_table and tag == "tr":
            self.row = []
        elif self.in_table and tag in {"td", "th"}:
            self.cell = []
            self.capture = True

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None and self.row is not None:
            self.row.append(" ".join(self.cell).strip())
            self.cell = None
            self.capture = False
        elif tag == "tr" and self.row is not None and self.cur is not None:
            if any(self.row):
                self.cur.append(self.row)
            self.row = None
        elif tag == "table" and self.cur is not None:
            self.tables.append(self.cur)
            self.cur = None
            self.in_table = False

    def handle_data(self, data):
        if self.capture and self.cell is not None:
            self.cell.append(data)


def _bins(text: str) -> list[int]:
    bins = []
    for rx, idx in BIN_PATTERNS:
        if rx.search(text):
            bins.append(idx)
    return sorted(set(bins))


def parse_weekly_zones(html: str) -> dict[str, dict[int, list[int]]]:
    """
    Return {zone_name: {weekday0-6: [bin_ids]}}.

    Supports both layouts:
    - rows = zones, columns = weekdays (Collegno/Rivoli/Grugliasco)
    - rows = weekdays, columns = zones (Alpignano/Giaveno/Pianezza/Venaria)
    """
    parser = TableParser()
    parser.feed(html)
    zones: dict[str, dict[int, list[int]]] = {}

    for table in parser.tables:
        if len(table) < 2:
            continue
        local: dict[str, dict[int, list[int]]] = {}

        header_idx = None
        col_wd: dict[int, int] = {}
        for ri, row in enumerate(table):
            header = [_norm_wd(c) for c in row]
            found: dict[int, int] = {}
            for i, cell in enumerate(header):
                for name, wd in WEEKDAY_IT.items():
                    if name in cell:
                        found[i] = wd
            if len(found) >= 3:
                header_idx = ri
                col_wd = found
                break

        if header_idx is not None:
            for row in table[header_idx + 1 :]:
                if not row:
                    continue
                zone = " ".join(row[0].split())
                if not zone or _norm_wd(zone) in {
                    "zona",
                    "utenze non domestiche",
                    "giorno",
                }:
                    continue
                schedule: dict[int, list[int]] = defaultdict(list)
                for ci, wd in col_wd.items():
                    if ci >= len(row):
                        continue
                    for b in _bins(row[ci]):
                        if b not in schedule[wd]:
                            schedule[wd].append(b)
                if schedule:
                    local[zone] = {k: sorted(v) for k, v in schedule.items()}
            if local:
                zones.update(local)
                continue

        # Layout B: rows = weekdays, columns = zones
        for ri, row in enumerate(table):
            cells = [" ".join(c.split()) for c in row]
            norms = [_norm_wd(c) for c in cells]
            if not norms or "giorno" not in norms[0]:
                continue
            zone_cols = [(i, cells[i]) for i in range(1, len(cells)) if cells[i]]
            if not zone_cols:
                continue
            for row2 in table[ri + 1 :]:
                if not row2:
                    continue
                wd_cell = _norm_wd(row2[0])
                wd = None
                for name, wdi in WEEKDAY_IT.items():
                    if name in wd_cell:
                        wd = wdi
                        break
                if wd is None:
                    continue
                for ci, zname in zone_cols:
                    if ci >= len(row2):
                        continue
                    bins = _bins(row2[ci])
                    if not bins:
                        continue
                    schedule = local.setdefault(zname, {})
                    cur = schedule.setdefault(wd, [])
                    for b in bins:
                        if b not in cur:
                            cur.append(b)
            break

        for zname, schedule in local.items():
            zones[zname] = {k: sorted(v) for k, v in schedule.items()}

    return zones


def expand_year(schedule: dict[int, list[int]], year: int) -> list[tuple[int, int, int, int]]:
    entries: list[tuple[int, int, int, int]] = []
    for month in range(1, 13):
        for day in range(1, cal_mod.monthrange(year, month)[1] + 1):
            wd = cal_mod.weekday(year, month, day)  # Mon=0
            for b in schedule.get(wd, []):
                entries.append((year, month, day, b))
    return entries


def zone_slug(name: str) -> str:
    s = name.lower()
    for a, b in {
        "à": "a",
        "è": "e",
        "é": "e",
        "ì": "i",
        "ò": "o",
        "ù": "u",
        "'": "",
    }.items():
        s = s.replace(a, b)
    s = re.sub(r"^zona\s+", "", s)
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s[:40] or "z"


def convert_comune(
    source_page: str,
    *,
    comune_id: str,
    comune_name: str,
    years: list[int],
    outdir: Path,
) -> list[dict]:
    raw = download_bytes(source_page)
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            html = raw.decode(enc)
            break
        except UnicodeDecodeError:
            html = raw.decode("utf-8", "replace")
    zones = parse_weekly_zones(html)
    if not zones:
        raise RuntimeError(f"No weekly zone table found on {source_page}")

    outdir.mkdir(parents=True, exist_ok=True)
    results = []
    for zone_name, schedule in zones.items():
        file_slug = f"{comune_id}-z{zone_slug(zone_name)}"
        # HTML headers often already include "Zona …"
        zone_label = (
            zone_name
            if zone_name.strip().lower().startswith("zona ")
            else f"Zona {zone_name}"
        )

        for year in years:
            entries = expand_year(schedule, year)
            write_year_file(
                out_path=outdir / f"{file_slug}-{year}.h",
                comune_name=comune_name,
                zone_label=zone_label,
                provider="CIDIU",
                addresses=[],
                year=year,
                entries=entries,
            )
        results.append(
            {
                "slug": file_slug,
                "zone_label": zone_label,
                "years": years,
                "entries": {
                    str(y): len(expand_year(schedule, y)) for y in years
                },
                "addresses": [],
                "zone_name": zone_name,
            }
        )
    return results


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("source_page")
    p.add_argument("--comune-id", required=True)
    p.add_argument("--comune", required=True)
    p.add_argument("--years", default="2026")
    p.add_argument("--outdir", default="docs/calendars")
    args = p.parse_args()
    years = [int(x) for x in args.years.split(",") if x.strip()]
    info = convert_comune(
        args.source_page,
        comune_id=args.comune_id,
        comune_name=args.comune,
        years=years,
        outdir=Path(args.outdir),
    )
    print([(i["slug"], i["entries"]) for i in info])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
