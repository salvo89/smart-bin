# -*- coding: utf-8 -*-
"""Clean discovered sources and merge into docs/calendars/sources.json."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "docs" / "calendars" / "sources.json"
DISC = ROOT / "tmp_calendars" / "discover_sources.json"

ACSEL_NAME_FIX = {
    "borgone": ("borgone-susa", "Borgone Susa"),
    "chiusa-san-michele": ("chiusa-di-san-michele", "Chiusa di San Michele"),
    "villardora": ("villar-dora", "Villar Dora"),
    "sant-ambrogio-bertassi": ("sant-ambrogio-di-torino", "Sant'Ambrogio di Torino"),
    "bussoleno-zona-1": ("bussoleno", "Bussoleno"),
    "bussoleno-zona-2": ("bussoleno", "Bussoleno"),
}

ACSEL_BLOCKLIST = {
    "codice-etico",
    "informativa-di-comportamento-per-persone-esterne",
}


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def is_calendar_pdf(url: str, label: str) -> bool:
    u = (url + " " + label).lower()
    if not url.lower().endswith(".pdf") and ".pdf" not in url.lower():
        return False
    bad = (
        "compostaggio",
        "abc-del",
        "abc_del",
        "pannolin",
        "guida",
        "carta-dei-servizi",
        "qualit",
        "ingombranti",
        "ecomobile",
        "codice-etico",
        "informativa",
    )
    if any(b in u for b in bad):
        return False
    # prefer calendar-ish
    good = ("calend", "2026", "2027", "ecocalend")
    return any(g in u for g in good) or True


def clean_discovered(raw: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}

    for c in raw:
        cid = c["id"]
        provider = c["provider"]

        if provider == "ACSEL":
            if cid in ACSEL_BLOCKLIST:
                continue
            if "2026" not in (c.get("pdfs") or [{}])[0].get("url", "") and cid not in {
                "sant-antonino-di-susa"
            }:
                # keep only calendar-looking uploads
                urls = " ".join(p["url"] for p in c.get("pdfs", []))
                if "-2026" not in urls and "2026" not in urls:
                    continue
            if cid in ACSEL_NAME_FIX:
                new_id, new_name = ACSEL_NAME_FIX[cid]
                # preserve zone label from old name
                zone = None
                if "zona" in c["name"].lower():
                    m = re.search(r"zona\s*(\d+)", c["name"], re.I)
                    zone = f"Zona {m.group(1)}" if m else c["name"]
                cid = new_id
                c = dict(c)
                c["id"] = new_id
                c["name"] = new_name
                if zone and c.get("pdfs"):
                    for p in c["pdfs"]:
                        p["label"] = zone

        pdfs = []
        for p in c.get("pdfs", []):
            if provider == "TeknoService" and not is_calendar_pdf(p["url"], p.get("label", "")):
                continue
            if provider == "TeknoService":
                # keep only files that look like the comune calendar
                stem = p["url"].rsplit("/", 1)[-1].lower()
                if "2026" not in stem and "calend" not in stem:
                    # still allow comune-named pdfs without year
                    if not re.search(r"[a-z]", stem):
                        continue
                # drop guides
                if any(x in stem for x in ("compost", "abc", "pannolin", "guida")):
                    continue
            pdfs.append(p)

        # Tekno: prefer single best calendar pdf
        if provider == "TeknoService" and pdfs:
            scored = []
            for p in pdfs:
                stem = p["url"].rsplit("/", 1)[-1].lower()
                score = 0
                if "2026" in stem:
                    score += 5
                if cid.replace("-", "") in stem.replace("-", "").replace("_", ""):
                    score += 3
                if "calend" in stem:
                    score += 2
                scored.append((score, p))
            scored.sort(key=lambda x: -x[0])
            pdfs = [scored[0][1]]
            pdfs[0]["label"] = "Calendario 2026"

        if provider == "TeknoService" and not pdfs and not c.get("pdfs"):
            # skip page-only without useful pdf
            continue

        rec = by_id.get(cid)
        if rec is None:
            c = dict(c)
            c["pdfs"] = pdfs
            by_id[cid] = c
        else:
            # merge pdfs
            seen = {p["url"] for p in rec.get("pdfs", [])}
            for p in pdfs:
                if p["url"] not in seen:
                    rec["pdfs"].append(p)
                    seen.add(p["url"])

    # Final ACSEL name polish
    for rec in by_id.values():
        if rec["provider"] == "ACSEL":
            if rec["id"] == "sant-ambrogio-di-torino":
                rec["name"] = "Sant'Ambrogio di Torino"
            if rec["id"] == "sant-antonino-di-susa":
                rec["name"] = "Sant'Antonino di Susa"
            # dedupe pdf labels
            rec["pdfs"].sort(key=lambda p: p.get("label", ""))

    return sorted(by_id.values(), key=lambda c: c["name"].casefold())


def main() -> None:
    raw = json.loads(DISC.read_text(encoding="utf-8"))
    cleaned = clean_discovered(raw)
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    existing = {c["id"]: c for c in sources["comuni"]}

    added = []
    for c in cleaned:
        if c["id"] in existing:
            # merge missing pdfs into existing CCS/CIDIU if any
            prev = existing[c["id"]]
            if c["provider"] == prev.get("provider") and c.get("pdfs"):
                seen = {p["url"] for p in prev.get("pdfs", [])}
                for p in c["pdfs"]:
                    if p["url"] not in seen:
                        prev.setdefault("pdfs", []).append(p)
                        seen.add(p["url"])
            continue
        existing[c["id"]] = c
        added.append(c)

    sources["comuni"] = sorted(existing.values(), key=lambda c: c["name"].casefold())
    sources["generatedAt"] = "2026-07-28"
    note = "Ampliato con ACSEL (Val Susa), TeknoService/CCA (Canavese), CCS e CIDIU residui."
    sources.setdefault("notes", [])
    if note not in sources["notes"]:
        sources["notes"].append(note)

    SOURCES.write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"added {len(added)} -> total {len(sources['comuni'])}")
    from collections import Counter

    print(Counter(c["provider"] for c in sources["comuni"]))
    print(Counter(c["provider"] for c in added))
    for c in added:
        print(f"+ {c['provider']:12} {c['name']:28} pdfs={len(c.get('pdfs', []))}")


if __name__ == "__main__":
    main()
