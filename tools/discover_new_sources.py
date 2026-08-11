# -*- coding: utf-8 -*-
"""Discover calendar sources from ACSEL, TeknoService/CCA, CCS, CIDIU, CISA."""
from __future__ import annotations

import json
import re
import ssl
import subprocess
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "docs" / "calendars" / "sources.json"
OUT = ROOT / "tmp_calendars" / "discover_sources.json"


def fetch(url: str, timeout: int = 90) -> str:
    try:
        import urllib.request

        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Escilo"})
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")
    except Exception:
        r = subprocess.run(
            ["curl.exe", "-k", "-L", "-s", "--max-time", str(timeout), url],
            capture_output=True,
            check=False,
        )
        if r.returncode != 0:
            raise RuntimeError(f"fetch failed {url}: {r.stderr[:200]!r}")
        return r.stdout.decode("utf-8", "replace")


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href = None
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._parts = []

    def handle_data(self, data):
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            label = " ".join(" ".join(self._parts).split())
            self.links.append((self._href, label))
            self._href = None
            self._parts = []


def links_from(html: str, base: str) -> list[tuple[str, str]]:
    p = LinkParser()
    p.feed(html)
    out = []
    for href, label in p.links:
        if not href:
            continue
        out.append((urljoin(base, href), label))
    return out


def discover_acsel() -> list[dict]:
    """PDFs on acselspa.it/calendari + wp-content uploads 2025/12 pattern."""
    page = "https://www.acselspa.it/calendari-raccolta-rifiuti/"
    html = fetch(page)
    found: dict[str, dict] = {}

    # Direct PDF links on page
    for url, label in links_from(html, page):
        if not url.lower().endswith(".pdf"):
            continue
        name = Path(url.split("?")[0]).stem
        name = re.sub(r"[-_]2026.*$", "", name, flags=re.I)
        name = name.replace("-", " ").replace("_", " ").title()
        # Known fixes
        fixes = {
            "Sant Antonino": "Sant'Antonino di Susa",
            "Sant Ambrogio": "Sant'Ambrogio di Torino",
            "Sauze D Oulx": "Sauze d'Oulx",
            "Sauze Di Cesana": "Sauze di Cesana",
            "Borgone Di Susa": "Borgone Susa",
            "Chiusa Di San Michele": "Chiusa di San Michele",
            "Meana Di Susa": "Meana di Susa",
            "San Giorio Di Susa": "San Giorio di Susa",
            "Villar Dora": "Villar Dora",
            "Villar Focchiardo": "Villar Focchiardo",
        }
        for a, b in fixes.items():
            if name.lower() == a.lower():
                name = b
        cid = slugify(name)
        found[cid] = {
            "id": cid,
            "name": name,
            "provider": "ACSEL",
            "sourcePage": page,
            "years": [2026],
            "notes": ["PDF calendario 2026 da acselspa.it."],
            "pdfs": [{"year": 2026, "label": "Calendario", "url": url}],
        }

    # Also probe known comuni via media library pattern
    comuni = [
        "Almese",
        "Avigliana",
        "Bardonecchia",
        "Borgone-Susa",
        "Bruzolo",
        "Bussoleno",
        "Caprie",
        "Caselette",
        "Cesana-Torinese",
        "Chianocco",
        "Chiomonte",
        "Chiusa-di-San-Michele",
        "Claviere",
        "Condove",
        "Exilles",
        "Giaglione",
        "Gravere",
        "Mattie",
        "Meana-di-Susa",
        "Mompantero",
        "Moncenisio",
        "Novalesa",
        "Oulx",
        "Rubiana",
        "Salbertrand",
        "San-Didero",
        "San-Giorio-di-Susa",
        "Sant-Ambrogio",
        "Sant-Antonino",
        "Sauze-d-Oulx",
        "Sauze-di-Cesana",
        "Sestriere",
        "Susa",
        "Vaie",
        "Venaus",
        "Villar-Dora",
        "Villar-Focchiardo",
    ]
    # Skip heavy HEAD probing; rely on page + sitemap/media listing if present
    # Try listing uploads folder via known filenames from news
    extras = [
        ("Sant'Antonino di Susa", "https://www.acselspa.it/wp-content/uploads/2025/12/SANT-ANTONINO-2026.pdf"),
    ]
    for name, url in extras:
        cid = slugify(name)
        if cid not in found:
            found[cid] = {
                "id": cid,
                "name": name,
                "provider": "ACSEL",
                "sourcePage": page,
                "years": [2026],
                "notes": ["PDF calendario 2026 da acselspa.it."],
                "pdfs": [{"year": 2026, "label": "Calendario", "url": url}],
            }
    return sorted(found.values(), key=lambda c: c["name"].casefold())


def discover_ccs_remaining(existing_ids: set[str]) -> list[dict]:
    page = "https://www.ccs.to.it/calendari-raccolta"
    html = fetch(page)
    by: dict[str, dict] = {}
    name_map = {
        "andezeno": "Andezeno",
        "arignano": "Arignano",
        "baldissero": "Baldissero Torinese",
        "cambiano": "Cambiano",
        "carmagnola": "Carmagnola",
        "chieri": "Chieri",
        "isolabella": "Isolabella",
        "marentino": "Marentino",
        "mombello": "Mombello di Torino",
        "moncucco": "Moncucco Torinese",
        "montaldo": "Montaldo Torinese",
        "moriondo": "Moriondo Torinese",
        "pavarolo": "Pavarolo",
        "pecetto": "Pecetto Torinese",
        "pino": "Pino Torinese",
        "poirino": "Poirino",
        "pralormo": "Pralormo",
        "rivapressochieri": "Riva presso Chieri",
        "santena": "Santena",
    }
    for url, label in links_from(html, page):
        if "serveDownload.php" not in url or "t=raccolta" not in url:
            continue
        m = re.search(r"f=([^&]+)\.PDF", url, re.I)
        if not m:
            continue
        raw = m.group(1).upper()
        # extract comune key
        key = None
        for k in sorted(name_map, key=len, reverse=True):
            if raw.startswith(k.upper().replace("-", "")):
                key = k
                break
        if key is None:
            # fallback: letters prefix
            key = re.sub(r"[0-9].*$", "", raw).lower()
        name = name_map.get(key, key.title())
        cid = slugify(name)
        if cid in existing_ids:
            continue
        zone = label.strip() or raw
        # clean zone label
        zone_label = re.sub(r"\s*\(Ott\..*$", "", zone).strip()
        if not zone_label.lower().startswith("zona"):
            # derive from filename suffix
            suf = raw[len(key.replace("-", "").upper()) :]
            zone_label = f"Zona {suf}" if suf else "Zona unica"
        rec = by.setdefault(
            cid,
            {
                "id": cid,
                "name": name,
                "provider": "CCS",
                "sourcePage": page,
                "years": [2026],
                "notes": [
                    "PDF CCS validi ottobre 2025 - dicembre 2026.",
                    "Disponibile anche web-app https://www.latuadifferenziata.it/pwarfoweb/home",
                ],
                "pdfs": [],
            },
        )
        rec["pdfs"].append({"year": 2026, "label": zone_label, "url": url})
    for rec in by.values():
        rec["pdfs"].sort(key=lambda p: p["label"])
    return sorted(by.values(), key=lambda c: c["name"].casefold())


def discover_cidiu_remaining(existing_ids: set[str]) -> list[dict]:
    comuni = [
        "Buttigliera Alta",
        "Coazze",
        "Druento",
        "Reano",
        "Rosta",
        "San Gillio",
        "Sangano",
        "Trana",
        "Valgioie",
        "Villarbasse",
    ]
    out = []
    for name in comuni:
        cid = slugify(name)
        if cid in existing_ids:
            continue
        page = f"https://cidiu.it/cidiu/comune-di-{cid}/"
        try:
            html = fetch(page)
        except Exception as exc:
            print(f"CIDIU skip {name}: {exc}")
            continue
        if "calendario" not in html.lower():
            print(f"CIDIU no calendar text {name}")
            continue
        out.append(
            {
                "id": cid,
                "name": name,
                "provider": "CIDIU",
                "sourcePage": page,
                "years": [2026],
                "notes": [
                    "Calendario settimanale HTML per zona su cidiu.it (porta a porta).",
                    "PDF festivi/sfalci sulla stessa pagina.",
                ],
                "pdfs": [],
            }
        )
        print(f"CIDIU ok {name}")
    return out


def discover_tekno_cca(existing_ids: set[str]) -> list[dict]:
    """Probe TeknoService pages for CCA comuni with downloadable calendars."""
    # Larger / known CCA comuni (exclude already covered SETA/SCS)
    candidates = [
        "Rivarolo Canavese",
        "Castellamonte",
        "Cuorgnè",
        "Favria",
        "Bosconero",
        "Caluso",
        "Strambino",
        "San Giorgio Canavese",
        "San Giusto Canavese",
        "San Maurizio Canavese",  # may be CISA
        "Feletto",
        "Ozegna",
        "Agliè",
        "Bairo",
        "Baldissero Canavese",
        "Barone Canavese",
        "Bollengo",
        "Borgiallo",
        "Borgofranco d'Ivrea",
        "Borgomasino",
        "Brosso",
        "Busano",
        "Candia Canavese",
        "Caravino",
        "Cascinette d'Ivrea",
        "Castelnuovo Nigra",
        "Chiaverano",
        "Ciconio",
        "Cintano",
        "Colleretto Castelnuovo",
        "Colleretto Giacosa",
        "Cossano Canavese",
        "Cuceglio",
        "Fiorano Canavese",
        "Forno Canavese",
        "Lessolo",
        "Levone",
        "Locana",
        "Loranzè",
        "Maglione",
        "Mazzè",
        "Mercenasco",
        "Nomaglio",
        "Oglianico",
        "Orio Canavese",
        "Palazzo Canavese",
        "Parella",
        "Pavone Canavese",
        "Perosa Canavese",
        "Pertusio",
        "Piverone",
        "Pont Canavese",
        "Prascorsano",
        "Pratiglione",
        "Quagliuzzo",
        "Quassolo",
        "Quincinetto",
        "Ribordone",
        "Rivara",
        "Rivarossa",
        "Rocca Canavese",  # may be CISA
        "Romano Canavese",
        "Rueglio",
        "Salassa",
        "Salerano Canavese",
        "Samone",
        "San Colombano Belmonte",
        "San Martino Canavese",
        "San Ponso",
        "Scarmagno",
        "Settimo Rottaro",
        "Settimo Vittone",
        "Sparone",
        "Strambinello",
        "Tavagnasco",
        "Torre Canavese",
        "Traversella",
        "Valperga",
        "Valprato Soana",
        "Vestignè",
        "Vialfrè",
        "Vidracco",
        "Villareggia",
        "Vische",
        "Vistrorio",
        "Alpette",
        "Chiesanuova",
        "Issiglio",
        "Frassinetto",
        "Ingria",
        "Ronco Canavese",
        "Valchiusa",
        "Val di Chy",
    ]
    out = []
    for name in candidates:
        cid = slugify(name)
        if cid in existing_ids:
            continue
        page = f"https://www.teknoserviceitalia.com/piemonte/torino/{cid}/"
        try:
            html = fetch(page)
        except Exception:
            continue
        if "Consorzio Canavesano" not in html and "Canavesano Ambiente" not in html:
            # page may still be valid
            if "Calendario" not in html:
                continue
        pdfs = []
        for url, label in links_from(html, page):
            low = url.lower()
            if ".pdf" not in low:
                continue
            if "calend" in low or "calend" in label.lower() or "scarica" in label.lower():
                pdfs.append(
                    {
                        "year": 2026,
                        "label": label or "Calendario",
                        "url": url,
                    }
                )
        # Also match generic download buttons near calendario
        if not pdfs:
            for url, label in links_from(html, page):
                if url.lower().endswith(".pdf"):
                    pdfs.append({"year": 2026, "label": label or "PDF", "url": url})
        if not pdfs:
            # keep as source page even without direct pdf if calendario section exists
            if "Calendario raccolta" not in html and "calendario" not in html.lower():
                continue
            print(f"TEKNO page-only {name}")
            out.append(
                {
                    "id": cid,
                    "name": name,
                    "provider": "TeknoService",
                    "sourcePage": page,
                    "years": [2026],
                    "notes": [
                        "Gestore TeknoService per Consorzio Canavesano Ambiente (CCA).",
                        "Calendario sulla pagina comunale TeknoService (verificare PDF).",
                    ],
                    "pdfs": [],
                }
            )
            continue
        print(f"TEKNO pdf {name} n={len(pdfs)}")
        out.append(
            {
                "id": cid,
                "name": name,
                "provider": "TeknoService",
                "sourcePage": page,
                "years": [2026],
                "notes": [
                    "Gestore TeknoService per Consorzio Canavesano Ambiente (CCA).",
                    "PDF calendario da teknoserviceitalia.com.",
                ],
                "pdfs": pdfs,
            }
        )
    return out


def discover_acsel_media() -> list[dict]:
    """Scrape ACSEL uploads directory listing if available, else media search page."""
    # Try common upload index / year folder
    urls = [
        "https://www.acselspa.it/wp-content/uploads/2025/12/",
        "https://www.acselspa.it/wp-content/uploads/2026/01/",
        "https://www.acselspa.it/?s=calendario+2026",
    ]
    found: dict[str, dict] = {}
    for page in urls:
        try:
            html = fetch(page)
        except Exception as exc:
            print(f"ACSEL media skip {page}: {exc}")
            continue
        for url, label in links_from(html, page):
            if not url.lower().endswith(".pdf"):
                continue
            if "2026" not in url and "2026" not in label:
                continue
            stem = Path(url.split("?")[0]).stem
            if "calend" not in stem.lower() and "2026" not in stem:
                # still accept *2026.pdf comune names
                if not re.search(r"20\d{2}", stem):
                    continue
            raw = re.sub(r"[-_ ]?20\d{2}.*$", "", stem, flags=re.I)
            raw = raw.replace("_", "-").replace(" ", "-")
            name = raw.replace("-", " ").title()
            name = (
                name.replace("Sant Antonino", "Sant'Antonino di Susa")
                .replace("Sant Ambrogio", "Sant'Ambrogio di Torino")
                .replace("Sauze D Oulx", "Sauze d'Oulx")
                .replace("Borgone Susa", "Borgone Susa")
                .replace("Di Susa", "di Susa")
                .replace("Di San", "di San")
            )
            cid = slugify(name)
            found[cid] = {
                "id": cid,
                "name": name,
                "provider": "ACSEL",
                "sourcePage": "https://www.acselspa.it/calendari-raccolta-rifiuti/",
                "years": [2026],
                "notes": ["PDF calendario 2026 da acselspa.it."],
                "pdfs": [{"year": 2026, "label": "Calendario", "url": url}],
            }
            print(f"ACSEL {name}")
    return sorted(found.values(), key=lambda c: c["name"].casefold())


def main() -> None:
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    existing_ids = {c["id"] for c in sources["comuni"]}
    discovered: list[dict] = []

    print("=== CCS remaining ===")
    discovered += discover_ccs_remaining(existing_ids)
    print("=== CIDIU remaining ===")
    discovered += discover_cidiu_remaining(existing_ids)
    print("=== ACSEL ===")
    discovered += discover_acsel()
    discovered += discover_acsel_media()
    print("=== TeknoService / CCA ===")
    discovered += discover_tekno_cca(existing_ids)

    # Dedup by id preferring entries with pdfs
    by_id: dict[str, dict] = {}
    for c in discovered:
        if c["id"] in existing_ids:
            continue
        prev = by_id.get(c["id"])
        if prev is None or (not prev.get("pdfs") and c.get("pdfs")):
            by_id[c["id"]] = c

    new_list = sorted(by_id.values(), key=lambda c: c["name"].casefold())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(new_list, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"DISCOVERED {len(new_list)} -> {OUT}")
    for c in new_list:
        print(f"  {c['provider']:12} {c['name']:30} pdfs={len(c.get('pdfs', []))}")


if __name__ == "__main__":
    main()
