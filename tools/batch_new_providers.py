# -*- coding: utf-8 -*-
"""Batch-convert provider calendars into .h files and merge index.json."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.acsel_pdf_to_h import convert_pdf as convert_acsel  # noqa: E402
from tools.ccs_pdf_to_h import convert_pdf as convert_ccs  # noqa: E402
from tools.cisa_pdf_to_h import convert_pdf as convert_cisa  # noqa: E402
from tools.cidiu_html_to_h import convert_comune as convert_cidiu  # noqa: E402
from tools.scs_pdf_to_h import convert_pdf as convert_scs  # noqa: E402
from tools.teknoservice_pdf_to_h import convert_pdf as convert_tekno  # noqa: E402

OUT_DIR = ROOT / "docs" / "calendars"
SOURCES = OUT_DIR / "sources.json"
INDEX = OUT_DIR / "index.json"
WORK = ROOT / "tmp_calendars" / "batch_new"
MANIFEST = WORK / "manifest.json"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def title_case_street(name: str) -> str:
    parts = name.split()
    out = []
    for part in parts:
        upper = part.upper()
        if upper in {"DI", "DE", "DEL", "DELLA", "DEI", "DELLE", "DA", "AL", "ALLA"}:
            out.append("di" if upper == "DI" else part.lower())
        elif re.fullmatch(
            r"VIA|VICOLO|PIAZZA|STRADA|CORSO|VIALE|LOCALITA|LOCALITÀ|BORGATA|CASCINA|FRAZIONE|PIAZZALE",
            part,
            re.I,
        ):
            out.append(part.title())
        else:
            out.append(part[:1].upper() + part[1:].lower() if part else part)
    return " ".join(out)


def zone_file_slug(label: str) -> str:
    label = re.sub(r"(?i)\.?pdf$", "", label.strip()).strip()
    m = re.search(r"zona\s*([a-z0-9]+)", label, re.I)
    if m:
        return "z" + m.group(1).lower()
    return "z" + slugify(label)[:16]


def merge_index(manifest: list[dict], existing: dict) -> dict:
    comuni_map = {c["id"]: dict(c) for c in existing.get("comuni", [])}
    for item in manifest:
        cid = item["comune_id"]
        if cid not in comuni_map:
            comuni_map[cid] = {"id": cid, "name": item["comune_name"], "vie": []}
        rec = comuni_map[cid]
        # drop previous vies for same calendar base when re-importing
        calendar_base = f"calendars/{item['file_slug']}"
        rec["vie"] = [v for v in rec.get("vie", []) if v.get("calendar") != calendar_base]
        seen = {(v["name"], v["calendar"]) for v in rec["vie"]}
        if item.get("addresses"):
            for addr in item["addresses"]:
                name = title_case_street(addr)
                key = (name, calendar_base)
                if key not in seen:
                    rec["vie"].append({"name": name, "calendar": calendar_base})
                    seen.add(key)
        else:
            name = item["zone_label"]
            key = (name, calendar_base)
            if key not in seen:
                rec["vie"].append({"name": name, "calendar": calendar_base})
                seen.add(key)
        comuni_map[cid] = rec

    years = sorted(
        set(existing.get("years", []))
        | {int(y) for item in manifest for y in item.get("years", [])}
    )
    comuni = sorted(comuni_map.values(), key=lambda c: c["name"].lower())
    for comune in comuni:
        comune["vie"].sort(key=lambda v: v["name"].lower())
    return {"years": years, "comuni": comuni}


def process_ccs(comune: dict, manifest: list, errors: list) -> None:
    cid = comune["id"]
    name = comune["name"]
    for pdf in comune.get("pdfs", []):
        label = pdf["label"]
        url = pdf["url"]
        zslug = zone_file_slug(label)
        file_slug = f"{cid}-{zslug}"
        try:
            info = convert_ccs(
                url,
                slug=file_slug,
                comune=name,
                zone_label=label if label.lower().startswith("zona") else f"Zona {label}",
                outdir=OUT_DIR,
                work_pdf=WORK / "ccs" / f"{file_slug}.pdf",
            )
            manifest.append(
                {
                    "provider": "CCS",
                    "comune_id": cid,
                    "comune_name": name,
                    "file_slug": file_slug,
                    "zone_label": label if label.lower().startswith("zona") else f"Zona {label}",
                    "years": info["years"],
                    "entries": info["entries"],
                    "addresses": info["addresses"],
                    "url": url,
                }
            )
            print(f"OK CCS {file_slug} years={info['years']} entries={info['entries']}")
        except Exception as exc:  # noqa: BLE001
            errors.append({"provider": "CCS", "comune": name, "label": label, "error": str(exc)})
            print(f"ERR CCS {name} {label}: {exc}")


def process_cisa(comune: dict, manifest: list, errors: list) -> None:
    cid = comune["id"]
    name = comune["name"]
    for pdf in comune.get("pdfs", []):
        label = pdf["label"]
        url = pdf["url"]
        base = "za" if "zona a" in label.lower() else "zb" if "zona b" in label.lower() else zone_file_slug(label)
        slug_base = f"{cid}-{base}"
        try:
            results = convert_cisa(
                url,
                comune=name,
                zone_base=label,
                slug_base=slug_base,
                outdir=OUT_DIR,
                work_pdf=WORK / "cisa" / f"{slug_base}.pdf",
            )
            for info in results:
                manifest.append(
                    {
                        "provider": "CISA",
                        "comune_id": cid,
                        "comune_name": name,
                        "file_slug": info["slug"],
                        "zone_label": info["zone_label"],
                        "years": info["years"],
                        "entries": info["entries"],
                        "addresses": info["addresses"],
                        "url": url,
                    }
                )
                print(
                    f"OK CISA {info['slug']} years={info['years']} entries={info['entries']}"
                )
        except Exception as exc:  # noqa: BLE001
            errors.append({"provider": "CISA", "comune": name, "label": label, "error": str(exc)})
            print(f"ERR CISA {name} {label}: {exc}")


def process_acsel(comune: dict, manifest: list, errors: list) -> None:
    cid = comune["id"]
    name = comune["name"]
    for pdf in comune.get("pdfs", []):
        url = pdf["url"]
        label = pdf.get("label", "Calendario")
        zslug = zone_file_slug(label)
        zone_label = label if re.search(r"zona", label, re.I) else None
        # Named non-numeric ACSEL annexes (e.g. SANT-AMBROGIO-BERTASSI-2026.pdf).
        if zone_label is None:
            fname = url.rsplit("/", 1)[-1].lower()
            for token in ("bertassi",):
                if token in fname:
                    zone_label = token.title()
                    zslug = "z" + token
                    break
        try:
            results = convert_acsel(
                url,
                slug_base=cid,
                comune=name,
                outdir=OUT_DIR,
                work_pdf=WORK / "acsel" / f"{cid}-{zslug}.pdf",
                zone_label=zone_label,
            )
            for info in results:
                manifest.append(
                    {
                        "provider": "ACSEL",
                        "comune_id": cid,
                        "comune_name": name,
                        "file_slug": info["slug"],
                        "zone_label": info["zone_label"],
                        "years": info["years"],
                        "entries": info["entries"],
                        "addresses": info["addresses"],
                        "url": url,
                    }
                )
                print(
                    f"OK ACSEL {info['slug']} years={info['years']} entries={info['entries']}"
                )
        except Exception as exc:  # noqa: BLE001
            errors.append({"provider": "ACSEL", "comune": name, "error": str(exc)})
            print(f"ERR ACSEL {name}: {exc}")


def process_tekno(comune: dict, manifest: list, errors: list) -> None:
    cid = comune["id"]
    name = comune["name"]
    years = comune.get("years") or [2026]
    for pdf in comune.get("pdfs", []):
        url = pdf["url"]
        try:
            info = convert_tekno(
                url,
                slug_base=cid,
                comune=name,
                outdir=OUT_DIR,
                work_pdf=WORK / "teknoservice" / f"{cid}.pdf",
                years=years,
            )
            manifest.append(
                {
                    "provider": "TeknoService",
                    "comune_id": cid,
                    "comune_name": name,
                    "file_slug": info["slug"],
                    "zone_label": info["zone_label"],
                    "years": info["years"],
                    "entries": info["entries"],
                    "addresses": info["addresses"],
                    "url": url,
                }
            )
            print(
                f"OK TeknoService {info['slug']} years={info['years']} entries={info['entries']}"
            )
        except Exception as exc:  # noqa: BLE001
            errors.append({"provider": "TeknoService", "comune": name, "error": str(exc)})
            print(f"ERR TeknoService {name}: {exc}")


def scs_zone_slug(url: str, label: str) -> str:
    name = url.rsplit("/", 1)[-1].lower().removesuffix(".pdf")
    m = re.search(r"ivreazona-([a-z0-9.]+)", name, re.I)
    if m:
        return "z" + m.group(1).replace(".", "")
    # Do not let ".pdf" bleed into the zone token (e.g. zona-b.pdf → b, not bpdf).
    m = re.search(r"zona-([a-z0-9]+(?:\.[0-9]+)?)", name, re.I)
    if m:
        return "z" + m.group(1).replace(".", "")
    return zone_file_slug(label)


def process_scs(comune: dict, manifest: list, errors: list) -> None:
    cid = comune["id"]
    name = comune["name"]
    for pdf in comune.get("pdfs", []):
        label = re.sub(r"(?i)\.?pdf$", "", str(pdf["label"] or "")).strip() or "Calendario"
        url = pdf["url"]
        zslug = scs_zone_slug(url, label)
        file_slug = f"{cid}-{zslug}"
        zone_label = label if label.lower().startswith("zona") else f"Zona {label}"
        try:
            info = convert_scs(
                url,
                slug=file_slug,
                comune=name,
                zone_label=zone_label,
                outdir=OUT_DIR,
                work_pdf=WORK / "scs" / f"{file_slug}.pdf",
            )
            manifest.append(
                {
                    "provider": "SCS",
                    "comune_id": cid,
                    "comune_name": name,
                    "file_slug": info["slug"],
                    "zone_label": info["zone_label"],
                    "years": info["years"],
                    "entries": info["entries"],
                    "addresses": info["addresses"],
                    "url": url,
                }
            )
            print(
                f"OK SCS {info['slug']} years={info['years']} entries={info['entries']}"
            )
        except Exception as exc:  # noqa: BLE001
            errors.append({"provider": "SCS", "comune": name, "label": label, "error": str(exc)})
            print(f"ERR SCS {name} {label}: {exc}")


def process_cidiu(comune: dict, manifest: list, errors: list) -> None:
    cid = comune["id"]
    name = comune["name"]
    page = comune["sourcePage"]
    years = comune.get("years") or [2026]
    try:
        results = convert_cidiu(
            page,
            comune_id=cid,
            comune_name=name,
            years=years,
            outdir=OUT_DIR,
        )
        for info in results:
            manifest.append(
                {
                    "provider": "CIDIU",
                    "comune_id": cid,
                    "comune_name": name,
                    "file_slug": info["slug"],
                    "zone_label": info["zone_label"],
                    "years": info["years"],
                    "entries": info["entries"],
                    "addresses": [],
                    "url": page,
                }
            )
            print(f"OK CIDIU {info['slug']} years={info['years']} entries={info['entries']}")
    except Exception as exc:  # noqa: BLE001
        errors.append({"provider": "CIDIU", "comune": name, "error": str(exc)})
        print(f"ERR CIDIU {name}: {exc}")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider",
        action="append",
        help="Limit to provider id(s): CCS, CISA, ACSEL, TeknoService, SCS, CIDIU",
    )
    args = parser.parse_args()
    only = {p.strip() for p in args.provider} if args.provider else None

    WORK.mkdir(parents=True, exist_ok=True)
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    existing_index = (
        json.loads(INDEX.read_text(encoding="utf-8"))
        if INDEX.exists()
        else {"years": [2026, 2027], "comuni": []}
    )

    manifest: list[dict] = []
    errors: list[dict] = []

    for comune in sources.get("comuni", []):
        provider = comune.get("provider")
        if only and provider not in only:
            continue
        if provider == "CCS":
            process_ccs(comune, manifest, errors)
        elif provider == "CISA":
            process_cisa(comune, manifest, errors)
        elif provider == "ACSEL":
            process_acsel(comune, manifest, errors)
        elif provider == "TeknoService":
            process_tekno(comune, manifest, errors)
        elif provider == "SCS":
            process_scs(comune, manifest, errors)
        elif provider == "CIDIU":
            process_cidiu(comune, manifest, errors)

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    INDEX.write_text(
        json.dumps(merge_index(manifest, existing_index), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"manifest={len(manifest)} errors={len(errors)} -> {INDEX}")
    if errors:
        (WORK / "errors.json").write_text(
            json.dumps(errors, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
