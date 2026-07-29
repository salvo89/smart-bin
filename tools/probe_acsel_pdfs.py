# -*- coding: utf-8 -*-
"""Probe missing ACSEL 2026 calendar PDFs by filename convention."""
from __future__ import annotations

import json
import ssl
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "docs" / "calendars" / "sources.json"

CANDIDATES = {
    "bardonecchia": "Bardonecchia",
    "cesana-torinese": ("CESANA-TORINESE-2026.pdf", "Cesana Torinese"),
    "cesana": ("CESANA-2026.pdf", "Cesana Torinese"),
    "chiomonte": "Chiomonte",
    "claviere": "Claviere",
    "exilles": "Exilles",
    "giaglione": "Giaglione",
    "gravere": "Gravere",
    "mattie": "Mattie",
    "meana-di-susa": ("MEANA-DI-SUSA-2026.pdf", "Meana di Susa"),
    "meana": ("MEANA-2026.pdf", "Meana di Susa"),
    "moncenisio": "Moncenisio",
    "novalesa": "Novalesa",
    "oulx": "Oulx",
    "salbertrand": "Salbertrand",
    "san-didero": ("SAN-DIDERO-2026.pdf", "San Didero"),
    "san-giorio-di-susa": ("SAN-GIORIO-DI-SUSA-2026.pdf", "San Giorio di Susa"),
    "san-giorio": ("SAN-GIORIO-2026.pdf", "San Giorio di Susa"),
    "sauze-d-oulx": ("SAUZE-D-OULX-2026.pdf", "Sauze d'Oulx"),
    "sauze-di-cesana": ("SAUZE-DI-CESANA-2026.pdf", "Sauze di Cesana"),
    "sestriere": "Sestriere",
    "venaus": "Venaus",
    "villar-focchiardo": ("VILLAR-FOCCHIARDO-2026.pdf", "Villar Focchiardo"),
}


def exists(url: str) -> bool:
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return 200 <= resp.status < 400
    except Exception:
        r = subprocess.run(
            ["curl.exe", "-k", "-sI", "--max-time", "30", url],
            capture_output=True,
            text=True,
            check=False,
        )
        return "200" in (r.stdout.splitlines() or [""])[0]


import re
import unicodedata


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def main() -> None:
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    existing = {c["id"] for c in sources["comuni"]}
    folders = [
        "https://www.acselspa.it/wp-content/uploads/2025/12/",
        "https://www.acselspa.it/wp-content/uploads/2026/01/",
    ]
    added = []
    for key, val in CANDIDATES.items():
        if isinstance(val, tuple):
            fname, name = val
        else:
            fname = f"{val.upper().replace(' ', '-')}-2026.pdf"
            name = val
        cid = slugify(name)
        if cid in existing:
            continue
        for folder in folders:
            url = folder + fname
            if exists(url):
                rec = {
                    "id": cid,
                    "name": name,
                    "provider": "ACSEL",
                    "sourcePage": "https://www.acselspa.it/calendari-raccolta-rifiuti/",
                    "years": [2026],
                    "notes": ["PDF calendario 2026 da acselspa.it."],
                    "pdfs": [{"year": 2026, "label": "Calendario", "url": url}],
                }
                sources["comuni"].append(rec)
                existing.add(cid)
                added.append(name)
                print("OK", name, url)
                break
        else:
            print("MISS", name)

    sources["comuni"].sort(key=lambda c: c["name"].casefold())
    SOURCES.write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("added", len(added), "total", len(sources["comuni"]))


if __name__ == "__main__":
    main()
