"""Batch convert SETA ecocalendar PDFs and merge docs/calendars/index.json."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.covar14_pdf_to_h import list_pdfs  # noqa: E402
from tools.seta_pdf_to_h import convert_pdf, download_if_needed  # noqa: E402

OUT_DIR = ROOT / "docs" / "calendars"
WORK_DIR = ROOT / "tmp_calendars" / "seta"
INDEX_PATH = OUT_DIR / "index.json"
SOURCES_PATH = OUT_DIR / "sources.json"
MANIFEST_PATH = WORK_DIR / "manifest.json"

SETA_COMUNI = [
    ("780-borgaro-torinese", "borgaro-torinese", "Borgaro Torinese"),
    ("781-brandizzo", "brandizzo", "Brandizzo"),
    ("782-brozolo", "brozolo", "Brozolo"),
    ("783-brusasco", "brusasco", "Brusasco"),
    ("784-casalborgone", "casalborgone", "Casalborgone"),
    ("785-caselle-torinese", "caselle-torinese", "Caselle Torinese"),
    ("786-castagneto-po", "castagnole-po", "Castagneto Po"),
    ("787-castiglione-torinese", "castiglione-torinese", "Castiglione Torinese"),
    ("788-cavagnolo", "cavagnolo", "Cavagnolo"),
    ("789-chivasso", "chivasso", "Chivasso"),
    ("790-cinzano", "cinzano", "Cinzano"),
    ("791-foglizzo", "foglizzo", "Foglizzo"),
    ("792-gassino-torinese", "gassino-torinese", "Gassino Torinese"),
    ("793-lauriano", "lauriano", "Lauriano"),
    ("794-leini", "leini", "Leinì"),
    ("795-lombardore", "lombardore", "Lombardore"),
    ("862-mappano", "mappano", "Mappano"),
    ("796-montanaro", "montanaro", "Montanaro"),
    ("797-monteu-da-po", "monteu-da-po", "Monteu da Po"),
    ("798-rivalba", "rivalba", "Rivalba"),
    ("799-rondissone", "rondissone", "Rondissone"),
    ("800-san-benigno-canavese", "san-benigno-canavese", "San Benigno Canavese"),
    ("801-san-mauro-torinese", "san-mauro-torinese", "San Mauro Torinese"),
    ("802-san-raffaele-cimena", "san-raffaele-cimena", "San Raffaele Cimena"),
    ("803-san-sebastiano-da-po", "san-sebastiano-da-po", "San Sebastiano da Po"),
    ("804-sciolze", "sciolze", "Sciolze"),
    ("805-settimo-torinese", "settimo-torinese", "Settimo Torinese"),
    ("806-torrazza-piemonte", "torrazza-piemonte", "Torrazza Piemonte"),
    ("807-verolengo", "verolengo", "Verolengo"),
    ("808-verrua-savoia", "verrua-savoia", "Verrua Savoia"),
    ("809-volpiano", "volpiano", "Volpiano"),
]


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def title_case_street(name: str) -> str:
    parts = name.split()
    out = []
    for part in parts:
        upper = part.upper()
        if upper in {"DI", "DE", "DEL", "DELLA", "DEI", "DELLE", "DA", "AL", "ALLA"}:
            out.append(part.lower() if upper != "DI" else "di")
        elif re.fullmatch(
            r"VIA|VICOLO|PIAZZA|STRADA|CORSO|VIALE|LOCALITA|LOCALITÀ|BORGATA|CASCINA|FRAZIONE",
            part,
            re.I,
        ):
            out.append(part.title())
        else:
            out.append(part[:1].upper() + part[1:].lower() if part else part)
    return " ".join(out)


def is_ecocalendar(label: str, url: str) -> bool:
    u = url.lower()
    if "/ecocalendari-" not in u:
        return False
    if "indicazioni-per-la-raccolta" in u:
        return False
    if not u.endswith(".pdf"):
        return False
    return "ecocalendario" in u


def parse_zone(label: str, url: str) -> tuple[str, str, int | None]:
    label = " ".join(label.split())
    url_lower = url.lower()

    m = re.search(r"zona[-_]([a-z0-9]+)", url_lower)
    if m:
        zraw = m.group(1)
        if zraw.isdigit():
            num = int(zraw)
            return f"z{num}", f"Zona {num}", num
        return f"z{zraw.lower()}", f"Zona {zraw.upper()}", None

    m = re.search(r"\bZONA\s+([A-Z0-9]+)\b", label, re.I)
    if m:
        zraw = m.group(1)
        if zraw.isdigit():
            num = int(zraw)
            return f"z{num}", f"Zona {num}", num
        return f"z{zraw.lower()}", f"Zona {zraw.upper()}", None

    # Prefer zunica over phantom z1 when the PDF has no zone token.
    return "zunica", "Zona unica", None


def zone_file_slug(comune_id: str) -> str:
    return comune_id.replace("-canavese", "").replace("-torinese", "").replace("-piemonte", "")


def fetch_comune_pdfs(page_slug: str) -> tuple[str, list[tuple[str, str]], str | None]:
    page_url = f"https://www.setaspa.com/comuni/148-comuni/{page_slug}"
    pdfs = [(label, url) for label, url in list_pdfs(page_url) if is_ecocalendar(label, url)]
    zone_url = None
    for label, url in list_pdfs(page_url):
        if "elenco vie" in label.lower() and "/images/zone/" in url.lower():
            zone_url = url
            break
    return page_url, pdfs, zone_url


def merge_index(manifest: list[dict], existing: dict) -> dict:
    comuni_map = {c["id"]: {"id": c["id"], "name": c["name"], "vie": list(c["vie"])} for c in existing.get("comuni", [])}

    for item in manifest:
        cid = item["comune_id"]
        if cid not in comuni_map:
            comuni_map[cid] = {"id": cid, "name": item["comune_name"], "vie": []}
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

    years = sorted({int(y) for item in manifest for y in item["years"]} | set(existing.get("years", [])))
    comuni = sorted(comuni_map.values(), key=lambda c: c["name"].lower())
    for comune in comuni:
        comune["vie"].sort(key=lambda v: v["name"].lower())
    return {"years": years, "comuni": comuni}


def merge_sources(manifest: list[dict], existing: dict) -> dict:
    by_id = {c["id"]: c for c in existing.get("comuni", []) if c.get("provider") != "SETA"}
    grouped: dict[str, dict] = {}
    for item in manifest:
        cid = item["comune_id"]
        if cid not in grouped:
            grouped[cid] = {
                "id": cid,
                "name": item["comune_name"],
                "provider": "SETA",
                "sourcePage": item["source_page"],
                "years": [],
                "notes": ["PDF ecocalendario da setaspa.com per zona."],
                "pdfs": [],
            }
        rec = grouped[cid]
        rec["years"] = sorted(set(rec["years"]) | set(item["years"]))
        rec["pdfs"].append(
            {
                "year": max(item["years"]),
                "label": item["zone_label"],
                "url": item["url"],
            }
        )
    for rec in grouped.values():
        rec["pdfs"].sort(key=lambda p: (p["label"], p["url"]))
        by_id[rec["id"]] = rec
    comuni = sorted(by_id.values(), key=lambda c: c["name"].lower())
    return {
        "generatedAt": existing.get("generatedAt", "2026-07-28"),
        "notes": existing.get("notes", []),
        "comuni": comuni,
    }


def main() -> int:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    existing_index = json.loads(INDEX_PATH.read_text(encoding="utf-8")) if INDEX_PATH.exists() else {"years": [], "comuni": []}
    existing_sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8")) if SOURCES_PATH.exists() else {"comuni": []}

    manifest = []
    errors = []

    for page_slug, comune_id, comune_name in SETA_COMUNI:
        try:
            source_page, pdfs, zone_url = fetch_comune_pdfs(page_slug)
            if not pdfs:
                raise RuntimeError("no ecocalendar PDFs found")

            zone_pdf_path = None
            if zone_url:
                zone_pdf_path = WORK_DIR / f"{zone_file_slug(comune_id)}-zone.pdf"
                download_if_needed(zone_url, zone_pdf_path)

            for label, url in pdfs:
                zone_slug, zone_label, zone_num = parse_zone(label, url)
                file_slug = f"{comune_id}-{zone_slug}"
                work_pdf = WORK_DIR / f"{file_slug}.pdf"
                info = convert_pdf(
                    url,
                    slug=file_slug,
                    comune=comune_name,
                    zone_label=zone_label,
                    zone_num=zone_num,
                    zone_pdf=zone_pdf_path,
                    outdir=OUT_DIR,
                    work_pdf=work_pdf,
                )
                from tools.seta_pdf_to_h import extract_zone_addresses

                addresses = (
                    extract_zone_addresses(zone_pdf_path, zone_num)
                    if zone_pdf_path and zone_num
                    else []
                )
                item = {
                    "comune_id": comune_id,
                    "comune_name": comune_name,
                    "file_slug": file_slug,
                    "zone_label": zone_label,
                    "zone_num": zone_num,
                    "url": url,
                    "source_page": source_page,
                    "years": info["years"],
                    "entries": info["entries"],
                    "addresses": addresses,
                }
                manifest.append(item)
                print(f"OK {file_slug} years={info['years']} entries={info['entries']} streets={len(addresses)}")
        except Exception as exc:  # noqa: BLE001
            errors.append({"comune": comune_name, "error": str(exc)})
            print(f"ERR {comune_name}: {exc}")

    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    INDEX_PATH.write_text(
        json.dumps(merge_index(manifest, existing_index), ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    SOURCES_PATH.write_text(
        json.dumps(merge_sources(manifest, existing_sources), ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote manifest ({len(manifest)} zones), index, sources")
    if errors:
        (WORK_DIR / "errors.json").write_text(json.dumps(errors, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        print(f"{len(errors)} comune errors")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
