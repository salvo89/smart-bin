import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "calendars" / "sources.json"
MANIFEST = ROOT / "tmp_calendars" / "covar14" / "manifest.json"
CALENDAR_PAGE = "https://www.covar14.it/it/servizi-e-impianti/servizi/calendario-di-raccolta"


def load_covar14_comuni() -> list[dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    grouped: dict[str, dict] = {}
    for item in manifest:
        cid = item["comune_id"]
        if cid not in grouped:
            grouped[cid] = {
                "id": cid,
                "name": item["comune_name"],
                "provider": "Covar14",
                "sourcePage": CALENDAR_PAGE,
                "years": sorted({int(y) for y in item["years"]}),
                "notes": [
                    "PDF 2026 pubblicati per singola zona (marzo-dicembre 2026).",
                    "I PDF 2026 includono anche gennaio-febbraio 2027 in coda al libretto.",
                ],
                "pdfs": [],
            }
        grouped[cid]["pdfs"].append(
            {
                "year": 2026,
                "label": item["zone_label"],
                "url": item["url"],
            }
        )
        grouped[cid]["years"] = sorted(
            set(grouped[cid]["years"]) | {int(y) for y in item["years"]}
        )

    # Include curated Candiolo if manifest skipped it.
    if "candiolo" not in grouped:
        grouped["candiolo"] = {
            "id": "candiolo",
            "name": "Candiolo",
            "provider": "Covar14",
            "sourcePage": CALENDAR_PAGE,
            "years": [2026, 2027],
            "notes": [
                "PDF 2026 pubblicati per singola zona (marzo-dicembre 2026).",
                "I PDF 2026 includono anche gennaio-febbraio 2027 in coda al libretto.",
            ],
            "pdfs": [
                {"year": 2026, "label": "Zona 1", "url": "https://www.covar14.it/sites/default/files/calendari_raccolta/2026/Calendario%20Covar14%202026%20CANDIOLO%20ZONA%201_1.pdf"},
                {"year": 2026, "label": "Zona 2", "url": "https://www.covar14.it/sites/default/files/calendari_raccolta/2026/Calendario%20Covar14%202026%20CANDIOLO%20ZONA%202.pdf"},
                {"year": 2026, "label": "Zona 3", "url": "https://www.covar14.it/sites/default/files/calendari_raccolta/2026/Calendario%20Covar14%202026%20CANDIOLO%20ZONA%203.pdf"},
                {"year": 2026, "label": "Zona 4", "url": "https://www.covar14.it/sites/default/files/calendari_raccolta/2026/Calendario%20Covar14%202026%20CANDIOLO%20ZONA%204.pdf"},
                {"year": 2026, "label": "Zona 5", "url": "https://www.covar14.it/sites/default/files/calendari_raccolta/2026/Calendario%20Covar14%202026%20CANDIOLO%20ZONA%205.pdf"},
                {"year": 2026, "label": "Zona 6", "url": "https://www.covar14.it/sites/default/files/calendari_raccolta/2026/Calendario%20Covar14%202026%20CANDIOLO%20ZONA%206.pdf"},
            ],
        }

    comuni = sorted(grouped.values(), key=lambda c: c["name"].lower())
    for comune in comuni:
        comune["pdfs"].sort(key=lambda p: p["label"])
    return comuni


def main() -> int:
    data = {
        "generatedAt": "2026-07-28",
        "notes": [
            "Catalogo fonti per la pagina web Escilo.",
            "Queste fonti descrivono provenienza e disponibilita' dei calendari PDF/HTML per comune.",
            "La presenza qui non implica che il comune sia gia' convertito in docs/calendars/*.h.",
        ],
        "comuni": load_covar14_comuni()
        + [
            {
                "id": "rivalba",
                "name": "Rivalba",
                "provider": "SETA",
                "sourcePage": "https://www.setaspa.com/comuni/148-comuni/798-rivalba",
                "years": [2026, 2027],
                "notes": [
                    "Pagina comune con PDF ecocalendario e stradario zone.",
                    "Il PDF verificato copre Luglio 2026 - Gennaio 2027.",
                ],
                "pdfs": [
                    {
                        "year": 2026,
                        "label": "Elenco vie per zona",
                        "url": "https://www.setaspa.com/images/zone/rivalba.pdf",
                    },
                    {
                        "year": 2026,
                        "label": "Ecocalendario Luglio 2026 - Gennaio 2027",
                        "url": "https://www.setaspa.com/images/ecocalendari-2026/ECOCALENDARIO-Luglio2026-Gennaio2027_Rivalba.pdf",
                    },
                ],
            },
            {
                "id": "settimo-torinese",
                "name": "Settimo Torinese",
                "provider": "SETA",
                "sourcePage": "https://www.setaspa.com/comuni/148-comuni/805-settimo-torinese",
                "years": [2026],
                "notes": ["PDF 2026 disponibili per zone 1..6."],
                "pdfs": [
                    {
                        "year": 2026,
                        "label": "Elenco vie per zona",
                        "url": "https://www.setaspa.com/images/zone/settimo.pdf",
                    },
                    {
                        "year": 2026,
                        "label": "Zona 1",
                        "url": "https://www.setaspa.com/images/ecocalendari-2026/ECOCALENDARIO-2026_Settimo-Torinese_zona-1.pdf",
                    },
                    {
                        "year": 2026,
                        "label": "Zona 2",
                        "url": "https://www.setaspa.com/images/ecocalendari-2026/ECOCALENDARIO-2026_Settimo-Torinese_zona-2.pdf",
                    },
                    {
                        "year": 2026,
                        "label": "Zona 3",
                        "url": "https://www.setaspa.com/images/ecocalendari-2026/ECOCALENDARIO-2026_Settimo-Torinese_zona-3.pdf",
                    },
                    {
                        "year": 2026,
                        "label": "Zona 4",
                        "url": "https://www.setaspa.com/images/ecocalendari-2026/ECOCALENDARIO-2026_Settimo-Torinese_zona-4.pdf",
                    },
                    {
                        "year": 2026,
                        "label": "Zona 5",
                        "url": "https://www.setaspa.com/images/ecocalendari-2026/ECOCALENDARIO-2026_Settimo-Torinese_zona-5.pdf",
                    },
                    {
                        "year": 2026,
                        "label": "Zona 6",
                        "url": "https://www.setaspa.com/images/ecocalendari-2026/ECOCALENDARIO-2026_Settimo-Torinese_zona-6.pdf",
                    },
                ],
            },
            {
                "id": "ivrea",
                "name": "Ivrea",
                "provider": "SCS",
                "sourcePage": "https://scsivrea.it/calendario-2-0/calendario-comune-di-ivrea/",
                "years": [2026],
                "notes": [
                    "Pagina comune con PDF 2026 per molte zone alfabetiche e sottozone.",
                    "Verificato almeno il set di link pubblicati nella pagina il 2026-07-28.",
                ],
                "pdfs": [
                    {
                        "year": 2026,
                        "label": "Zona A",
                        "url": "https://scsivrea.it/wp-content/uploads/2025/12/Calendario-2026_UD_IVREAZONA-A-Copia.pdf",
                    },
                    {
                        "year": 2026,
                        "label": "Zona B",
                        "url": "https://scsivrea.it/wp-content/uploads/2025/12/Calendario-2026_UD_IVREA-ZONA-B.pdf",
                    },
                    {
                        "year": 2026,
                        "label": "Zona C",
                        "url": "https://scsivrea.it/wp-content/uploads/2025/12/Calendario-2026_UD_IVREA-ZONA-C.pdf",
                    },
                    {
                        "year": 2026,
                        "label": "Zona G",
                        "url": "https://scsivrea.it/wp-content/uploads/2026/02/Calendario-2026_UD_IVREA-ZONA-G.pdf",
                    },
                    {
                        "year": 2026,
                        "label": "Zona S",
                        "url": "https://scsivrea.it/wp-content/uploads/2025/12/Calendario-2026_UD_IVREA-ZONA-S.pdf",
                    },
                ],
            },
            {
                "id": "torino",
                "name": "Torino",
                "provider": "AMIAT",
                "sourcePage": "https://www.amiat.it/i-nostri-servizi/servizi-di-raccolta-differenziata.html",
                "years": [2026],
                "notes": [
                    "Il sito Amiat espone il calendario personalizzato via ricerca indirizzo.",
                    "Come PDF diretto e' stato verificato solo il calendario festivita' 2026.",
                ],
                "pdfs": [
                    {
                        "year": 2026,
                        "label": "Calendario festivita' 2026",
                        "url": "https://www.amiat.it/content/dam/amiat/documents/servizi/Calendario-Festivit%C3%A0-Torino_2026.pdf",
                    },
                ],
            },
        ],
    }

    OUT.write_text(json.dumps(data, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
