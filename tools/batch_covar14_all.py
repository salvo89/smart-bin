"""Batch convert Covar14 calendar PDFs and build docs/calendars/index.json."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.covar14_pdf_to_h import (  # noqa: E402
    download_if_needed,
    extract_addresses,
    extract_entries,
    list_pdfs,
    write_year_file,
)

CALENDAR_PAGE = "https://www.covar14.it/it/servizi-e-impianti/servizi/calendario-di-raccolta"
OUT_DIR = ROOT / "docs" / "calendars"
WORK_DIR = ROOT / "tmp_calendars" / "covar14"
INDEX_PATH = OUT_DIR / "index.json"
MANIFEST_PATH = WORK_DIR / "manifest.json"

COMUNE_ALIASES = {
    "CASTAGNOLE P.TE": "castagnole-piemonte",
    "CASTAGNOLE PIEMONTE": "castagnole-piemonte",
    "LA LOGGIA": "la-loggia",
    "PIOBESI": "piobesi-torinese",
    "PIOBESI T.SE": "piobesi-torinese",
    "PIOBESI TORINESE": "piobesi-torinese",
    "RIVALTA": "rivalta-di-torino",
    "RIVALTA DI TORINO": "rivalta-di-torino",
}

SKIP_COMUNI = {"candiolo"}  # already converted and index curated


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def title_case_street(name: str) -> str:
  parts = name.split()
  out = []
  for p in parts:
    if p in {"DI", "DE", "DEL", "DELLA", "DEI", "DELLE", "DA", "AL", "ALLA"}:
      out.append(p.lower() if p != "DI" else "di")
    elif re.fullmatch(r"VIA|VICOLO|PIAZZA|STRADA|CORSO|VIALE|LOCALITA|LOCALITÀ|BORGATA|CASCINA", p, re.I):
      out.append(p.title())
    else:
      out.append(p[:1].upper() + p[1:].lower() if p else p)
  return " ".join(out)


def parse_pdf_meta(url: str, label: str) -> tuple[str, str, str, str]:
    """Return (comune_id, comune_name, zone_slug_suffix, zone_label)."""
    name = unquote(url.rsplit("/", 1)[-1])
    name = re.sub(r"\.pdf.*$", "", name, flags=re.I)
    name = re.sub(r"^Calendario\s+Covar14\s+2026\s+", "", name, flags=re.I).strip()

    zone_match = re.search(r"\bZONA\s+(.+)$", name, flags=re.I)
    if zone_match:
      comune_raw = name[: zone_match.start()].strip()
      zone_raw = zone_match.group(1).strip()
      zone_raw = re.sub(r"_\d+$", "", zone_raw)
      zone_slug = slugify(f"z{zone_raw.replace(' ', '')}")
      zone_label = f"Zona {zone_raw}"
    else:
      comune_raw = name
      zone_slug = "z1"
      zone_label = label if label.lower() != "zona 1" else "Zona unica"

    comune_key = comune_raw.upper()
    comune_id = COMUNE_ALIASES.get(comune_key, slugify(comune_raw))
    comune_name = comune_raw.title()
    if comune_id == "la-loggia":
      comune_name = "La Loggia"
    elif comune_id == "piobesi-torinese":
      comune_name = "Piobesi Torinese"
    elif comune_id == "rivalta-di-torino":
      comune_name = "Rivalta di Torino"
    elif comune_id == "castagnole-piemonte":
      comune_name = "Castagnole Piemonte"

    return comune_id, comune_name, zone_slug, zone_label


def convert_one(url: str, label: str) -> dict:
    comune_id, comune_name, zone_slug, zone_label = parse_pdf_meta(url, label)
    file_slug = f"{comune_id}-{zone_slug}"
    pdf_path = WORK_DIR / f"{file_slug}.pdf"
    download_if_needed(url, pdf_path)
    doc = fitz.open(pdf_path)
    addresses = extract_addresses(doc)
    entries = extract_entries(doc)
    if not entries:
        raise RuntimeError(f"No entries extracted for {file_slug}")

    grouped: dict[int, list[tuple[int, int, int, int]]] = defaultdict(list)
    for item in entries:
        grouped[item[0]].append(item)

    for year, year_entries in sorted(grouped.items()):
        out_path = OUT_DIR / f"{file_slug}-{year}.h"
        write_year_file(
            out_path=out_path,
            comune_name=comune_name,
            zone_label=zone_label,
            provider="Covar14",
            addresses=addresses,
            year=year,
            entries=year_entries,
        )

    years = sorted(grouped)
    return {
        "comune_id": comune_id,
        "comune_name": comune_name,
        "file_slug": file_slug,
        "zone_label": zone_label,
        "url": url,
        "addresses": addresses,
        "years": years,
        "entries": {str(y): len(grouped[y]) for y in years},
    }


def build_index(manifest: list[dict], existing_index: dict) -> dict:
    comuni_map: dict[str, dict] = {}

    # Keep curated Candiolo streets from existing index.
    for comune in existing_index.get("comuni", []):
        if comune["id"] in SKIP_COMUNI:
            comuni_map[comune["id"]] = {
                "id": comune["id"],
                "name": comune["name"],
                "vie": list(comune["vie"]),
            }

    for item in manifest:
        cid = item["comune_id"]
        if cid not in comuni_map:
            comuni_map[cid] = {
                "id": cid,
                "name": item["comune_name"],
                "vie": [],
            }
        calendar_base = f"calendars/{item['file_slug']}"
        seen = {(v["name"], v["calendar"]) for v in comuni_map[cid]["vie"]}
        if item["addresses"]:
            for addr in item["addresses"]:
                name = title_case_street(addr)
                key = (name, calendar_base)
                if key not in seen:
                    comuni_map[cid]["vie"].append({"name": name, "calendar": calendar_base})
                    seen.add(key)
        else:
            key = (item["zone_label"], calendar_base)
            if key not in seen:
                comuni_map[cid]["vie"].append({"name": item["zone_label"], "calendar": calendar_base})
                seen.add(key)

    years = sorted({int(y) for item in manifest for y in item["years"]})
    if not years:
        years = existing_index.get("years", [2026, 2027])

    comuni = sorted(comuni_map.values(), key=lambda c: c["name"].lower())
    for comune in comuni:
        comune["vie"].sort(key=lambda v: v["name"].lower())

    return {"years": years, "comuni": comuni}


def main() -> int:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = list_pdfs(CALENDAR_PAGE)
    if not pdfs:
        raise SystemExit("No PDFs found on Covar14 calendar page")

    existing_index = json.loads(INDEX_PATH.read_text(encoding="utf-8")) if INDEX_PATH.exists() else {"years": [2026, 2027], "comuni": []}

    manifest = []
    errors = []
    for label, url in pdfs:
        comune_id, _, _, _ = parse_pdf_meta(url, label)
        if comune_id in SKIP_COMUNI:
            continue
        try:
            info = convert_one(url, label)
            manifest.append(info)
            print(f"OK {info['file_slug']} years={info['years']} entries={info['entries']}")
        except Exception as exc:  # noqa: BLE001
            errors.append({"label": label, "url": url, "error": str(exc)})
            print(f"ERR {label}: {exc}")

    manifest_path = MANIFEST_PATH
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    index = build_index(manifest, existing_index)
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {INDEX_PATH} ({len(index['comuni'])} comuni)")

    if errors:
        err_path = WORK_DIR / "errors.json"
        err_path.write_text(json.dumps(errors, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        print(f"{len(errors)} errors -> {err_path}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
