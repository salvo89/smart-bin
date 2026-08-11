# -*- coding: utf-8 -*-
"""Merge SCS Ivrea verde/sfalci fixed days into existing letter-zone calendars.

Does NOT create separate zone calendars: Verde (bin 4) is added to the
existing differenziata .h files. Street maps pick the dominant sfalci zone
per letter zone (best effort when overlays differ).

Usage:
  py -3 tools/merge_scs_sfalci_verde.py
  py -3 tools/merge_scs_sfalci_verde.py --year 2026 --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.covar14_pdf_to_h import write_year_file  # noqa: E402
from tools.download_safe import download_bytes, download_if_needed  # noqa: E402
from tools.scs_pdf_to_h import day_columns, month_rows, nearest_bin  # noqa: E402

UD_PAGE = "https://scsivrea.it/calendario-2-0/calendario-comune-di-ivrea/"
SFALCI_PAGE = "https://scsivrea.it/calendario-comune-di-ivrea-raccolta-sfalci/"
SFALCI_PDF = (
    "https://scsivrea.it/wp-content/uploads/2026/02/"
    "Ivrea-Zona-{zone:02d}-Calendario-2026_verde-e-sfalci.pdf"
)

ENTRY_RE = re.compile(
    r"\{(\d{4})\s*,\s*(\d{1,2})\s*,\s*(\d{1,2})\s*,\s*(-?\d+)\s*\}"
)


def norm_street(s: str) -> str:
    s = s.upper()
    for a, b in (("À", "A"), ("È", "E"), ("É", "E"), ("Ì", "I"), ("Ò", "O"), ("Ù", "U")):
        s = s.replace(a, b)
    s = re.sub(r"^VIA\s+|^VIALE\s+|^CORSO\s+|^PIAZZA\s+|^STRADA\s+|^VICOLO\s+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.split(r"\s+DAL\s+|\s+DA\s+CIVICO|\s+/|\s+FINO", s)[0].strip()
    return s


def parse_tables(html: str) -> list[list[list[str]]]:
    tables: list[list[list[str]]] = []
    for tmatch in re.finditer(r"<table\b[^>]*>(.*?)</table>", html, re.I | re.S):
        rows: list[list[str]] = []
        for rmatch in re.finditer(r"<tr\b[^>]*>(.*?)</tr>", tmatch.group(1), re.I | re.S):
            cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", rmatch.group(1), re.I | re.S)
            clean = [" ".join(re.sub(r"<[^>]+>", " ", c).split()) for c in cells]
            if any(clean):
                rows.append(clean)
        if rows:
            tables.append(rows)
    return tables


def extract_verde_entries(page: fitz.Page, year: int) -> list[tuple[int, int, int, int]]:
    months = month_rows(page)
    if not months:
        return []
    day_cols_cache = {m: day_columns(page, y0, y1) for m, y0, y1 in months}
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
        if nearest_bin(fill) != 4:
            continue
        month = next((m for m, y0, y1 in months if y0 <= cy < y1), None)
        if month is None:
            continue
        cols = day_cols_cache.get(month) or []
        if not cols:
            continue
        day, dx = min(cols, key=lambda item: abs(cx - item[1]))
        if abs(cx - dx) > 20:
            continue
        entries.add((year, month, day, 4))
    return sorted(entries)


def load_entries(path: Path) -> list[tuple[int, int, int, int]]:
    text = path.read_text(encoding="utf-8")
    return [(int(y), int(m), int(d), int(b)) for y, m, d, b in ENTRY_RE.findall(text)]


def letter_to_slug(letter: str) -> str:
    return "z" + letter.upper().replace(" ", "").lower().replace(".", "")


def street_maps() -> tuple[dict[str, str], dict[str, str]]:
    sf_html = download_bytes(SFALCI_PAGE).decode("utf-8", "replace")
    ud_html = download_bytes(UD_PAGE).decode("utf-8", "replace")

    street_to_sf: dict[str, str] = {}
    for rows in parse_tables(sf_html):
        for row in rows:
            if len(row) < 2:
                continue
            street, zone = row[0], row[1]
            if "nome" in street.lower():
                continue
            m = re.search(r"(\d+)", zone)
            if not m:
                continue
            street_to_sf[norm_street(street)] = m.group(1)

    street_to_letter: dict[str, str] = {}
    for rows in parse_tables(ud_html):
        if len(rows) < 2:
            continue
        header = [c.lower() for c in rows[0]]
        zcol = next((i for i, h in enumerate(header) if "zona" in h), None)
        if zcol is None:
            continue
        for row in rows[1:]:
            if len(row) <= zcol:
                continue
            street = row[0]
            zone = row[zcol]
            if not street or "indirizzo" in street.lower():
                continue
            zm = re.search(r"zona\s*([a-z0-9.]+)", zone, re.I)
            letter = zm.group(1).upper() if zm else zone.strip().upper()
            street_to_letter[norm_street(street)] = letter
    return street_to_sf, street_to_letter


def dominant_sfalci_by_letter(
    street_to_sf: dict[str, str], street_to_letter: dict[str, str]
) -> dict[str, tuple[str, float, int]]:
    votes: dict[str, Counter[str]] = defaultdict(Counter)
    for st, letter in street_to_letter.items():
        sf = street_to_sf.get(st)
        if sf:
            votes[letter][sf] += 1
    out: dict[str, tuple[str, float, int]] = {}
    for letter, ctr in votes.items():
        total = sum(ctr.values())
        sf, n = ctr.most_common(1)[0]
        out[letter] = (sf, n / total if total else 0.0, total)
    return out


def merge_verde(
    existing: list[tuple[int, int, int, int]],
    verde: list[tuple[int, int, int, int]],
) -> list[tuple[int, int, int, int]]:
    kept = [e for e in existing if e[3] != 4]
    return sorted(set(kept) | set(verde))


def strip_sfalci_from_index(index_path: Path, dry_run: bool) -> int:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    ivrea = next(c for c in data["comuni"] if c["id"] == "ivrea")
    before = len(ivrea["vie"])
    ivrea["vie"] = [v for v in ivrea["vie"] if "sfalci" not in v.get("calendar", "")]
    removed = before - len(ivrea["vie"])
    if dry_run:
        print(f"[dry-run] index would remove {removed} sfalci zones")
        return removed
    index_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"index.json: removed {removed} dedicated sfalci zones")
    return removed


def update_sources(sources_path: Path, year: int, dry_run: bool) -> None:
    data = json.loads(sources_path.read_text(encoding="utf-8"))
    ivrea = next(c for c in data["comuni"] if c["id"] == "ivrea")
    pdfs = list(ivrea.get("pdfs") or [])
    existing_urls = {p.get("url") for p in pdfs}
    added = 0
    for z in range(1, 8):
        url = SFALCI_PDF.format(zone=z)
        if url in existing_urls:
            continue
        pdfs.append({"year": year, "label": f"Verde/sfalci zona {z}", "url": url})
        added += 1
    notes = [
        n
        for n in (ivrea.get("notes") or [])
        if "overlay diverso" not in n and "merge automatico" not in n
    ]
    note = (
        "Verde/sfalci 2026 mergiati nei calendari zona lettera (bin Verde); "
        "fonti PDF zone sfalci 1-7 (mappa vie -> zona dominante)."
    )
    if note not in notes:
        notes.append(note)
    if dry_run:
        print(f"[dry-run] sources would add {added} pdfs / refresh note")
        return
    ivrea["pdfs"] = pdfs
    ivrea["notes"] = notes
    sources_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"sources.json: +{added} sfalci pdfs, notes updated")


def delete_standalone_sfalci(outdir: Path, year: int, dry_run: bool) -> int:
    removed = 0
    for path in sorted(outdir.glob(f"ivrea-sfalci-z*-{year}.h")):
        print(f"delete standalone {path.name}")
        if not dry_run:
            path.unlink()
        removed += 1
    return removed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--outdir", type=Path, default=ROOT / "docs" / "calendars")
    ap.add_argument("--work", type=Path, default=ROOT / "tmp_calendars" / "scs_sfalci")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    outdir: Path = args.outdir
    work: Path = args.work
    work.mkdir(parents=True, exist_ok=True)

    print("Downloading street maps...")
    street_to_sf, street_to_letter = street_maps()
    dominance = dominant_sfalci_by_letter(street_to_sf, street_to_letter)
    fallback_sf = Counter(street_to_sf.values()).most_common(1)[0][0]
    print(
        f"streets sfalci={len(street_to_sf)} UD={len(street_to_letter)} "
        f"fallback_sf={fallback_sf}"
    )

    verde_by_zone: dict[str, list[tuple[int, int, int, int]]] = {}
    for z in range(1, 8):
        url = SFALCI_PDF.format(zone=z)
        pdf_path = download_if_needed(url, work / f"ivrea-sfalci-z{z}.pdf")
        entries = extract_verde_entries(fitz.open(pdf_path)[0], args.year)
        if len(entries) < 8:
            raise RuntimeError(f"Too few verde entries for zona {z}: {len(entries)}")
        verde_by_zone[str(z)] = entries
        print(f"sfalci zona {z}: {len(entries)} Verde days")

    # All existing letter-zone calendars (exclude standalone sfalci leftovers).
    letter_files = sorted(
        p
        for p in outdir.glob(f"ivrea-z*-{args.year}.h")
        if "sfalci" not in p.name
    )
    merged = 0
    for path in letter_files:
        # ivrea-za-2026.h -> A ; ivrea-zz1-2026.h -> Z.1
        m = re.match(r"ivrea-z([a-z0-9]+)-" + str(args.year) + r"\.h$", path.name, re.I)
        if not m:
            continue
        raw = m.group(1).upper()
        # zm1 -> M.1, zz3 -> Z.3, za -> A
        if len(raw) >= 2 and raw[0].isalpha() and raw[1:].isdigit():
            letter = f"{raw[0]}.{raw[1:]}"
        else:
            letter = raw

        if letter in dominance:
            sf_zone, share, n = dominance[letter]
            how = f"dominant sf{sf_zone} {share:.0%} n={n}"
        else:
            sf_zone, share, n = fallback_sf, 0.0, 0
            how = f"fallback sf{sf_zone}"

        verde = verde_by_zone[sf_zone]
        existing = load_entries(path)
        before4 = sum(1 for e in existing if e[3] == 4)
        merged_entries = merge_verde(existing, verde)
        after4 = sum(1 for e in merged_entries if e[3] == 4)
        print(f"merge {path.name} <- {how}: verde {before4} -> {after4}")
        if not args.dry_run:
            first = path.read_text(encoding="utf-8").splitlines()[0]
            zone_label = f"Zona {letter}"
            zm = re.search(r"Zona\s+([^(]+)", first, re.I)
            if zm:
                zone_label = zm.group(0).strip()
            write_year_file(
                out_path=path,
                comune_name="Ivrea",
                zone_label=zone_label,
                provider="SCS",
                addresses=[],
                year=args.year,
                entries=merged_entries,
            )
        merged += 1

    delete_standalone_sfalci(outdir, args.year, args.dry_run)
    strip_sfalci_from_index(outdir / "index.json", args.dry_run)
    update_sources(outdir / "sources.json", args.year, args.dry_run)
    print(f"done: merged_into={merged} letter calendars (no dedicated sfalci zones)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
