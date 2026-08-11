# -*- coding: utf-8 -*-
"""Import CIDIU spazzamento meccanizzato (bin 6) from cidiu.it.

For each CIDIU comune with a dedicated calendario-spazzamento-meccanizzato-* page
(or embedded SETT table on the comune page):

1. Parse zone → 2026 dates from the calendar page.
2. Write docs/calendars/{id}-spa-{slug}-YYYY.h (Spazzamento only).
3. Add street vies from the comune page <option data-zona> selectors into
   docs/calendars/index.json (keeps existing zona-raccolta labels).
4. When spa zone names clearly map to a raccolta calendar, also merge the
   union of matching spa dates into that raccolta .h (SETA-style).

Comuni without meccanizzato calendars are skipped (noted in sources).
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
import time
import urllib.request
from collections import defaultdict
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
sys_path_note = str(ROOT)
import sys

sys.path.insert(0, sys_path_note)

from tools.covar14_pdf_to_h import write_year_file  # noqa: E402

BIN_SPA = 6
UA = {"User-Agent": "Mozilla/5.0 EsciloCidiuSpa/1.0 (+https://escilo.it/)"}
CTX = ssl.create_default_context()
ENTRY_RE = re.compile(
    r"\{(\d{4})\s*,\s*(\d{1,2})\s*,\s*(\d{1,2})\s*,\s*(-?\d+)\s*\}"
)
ZONE_LABEL_RE = re.compile(r"^zona\b", re.I)

# Escilo comune id → dedicated meccanizzato calendar URL (None = try embed / skip)
CAL_PAGES: dict[str, str | None] = {
    "alpignano": "https://cidiu.it/cidiu/calendario-spazzamento-meccanizzato-alpignano/",
    "buttigliera-alta": None,
    "coazze": None,
    "collegno": "https://cidiu.it/cidiu/calendario-spazzamento-meccanizzato-collegno/",
    "druento": "https://cidiu.it/cidiu/calendario-spazzamento-meccanizzato-druento/",
    "giaveno": None,
    "grugliasco": "https://cidiu.it/cidiu/calendario-spazzamento-meccanizzato-grugliasco/",
    "pianezza": None,  # embedded table on comune page
    "reano": None,
    "rivoli": "https://cidiu.it/cidiu/calendario-spazzamento-meccanizzato-rivoli/",
    "sangano": None,
    "trana": None,
    "venaria-reale": "https://cidiu.it/cidiu/calendario-spazzamento-meccanizzato-venaria/",
    "villarbasse": None,
}

# spa zone token → raccolta calendar path (best-effort name merge)
SPA_TO_RACCOLTA: dict[str, list[tuple[str, str]]] = {
    # (needle in folded spa zone name, calendar path) — first match wins
    "grugliasco": [
        ("FABBRICHETTA", "calendars/grugliasco-zfabbrichetta"),
        ("GERBIDO", "calendars/grugliasco-zgerbido"),
        ("SAN SEBASTIANO", "calendars/grugliasco-zsansebastiano"),
        ("S SEBASTIANO", "calendars/grugliasco-zsansebastiano"),
        ("PARADISO", "calendars/grugliasco-zparadiso"),
        ("LESNA", "calendars/grugliasco-zlesnaquaglia"),
        ("QUAGLIA", "calendars/grugliasco-zlesnaquaglia"),
        ("S GIACOMO", "calendars/grugliasco-zsangiacomo"),
        ("SAN GIACOMO", "calendars/grugliasco-zsangiacomo"),
        ("S MARIA", "calendars/grugliasco-zsantamaria"),
        ("SANTA MARIA", "calendars/grugliasco-zsantamaria"),
        ("CENTRO", "calendars/grugliasco-zcentro"),
    ],
    "collegno": [
        ("BORGONUOVO", "calendars/collegno-zborgonuovo"),
        ("CENTRO STORICO", "calendars/collegno-zcentrostorico"),
        ("LUXEMBURG", "calendars/collegno-zluxemburg"),
        ("OLTREDORA", "calendars/collegno-zoltredoraepip"),
        ("OLTRE DORA", "calendars/collegno-zoltredoraepip"),
        ("PARADISO INDUSTRIALE", "calendars/collegno-zparadisoindustriale"),
        ("PARADISO NORD", "calendars/collegno-zparadisonord"),
        ("PARADISO SUD", "calendars/collegno-zparadisosud"),
        ("SAVONERA", "calendars/collegno-zsavonera"),
        ("TERRACORTA", "calendars/collegno-zterracorta"),
    ],
}

WEEKDAY_IT = {
    "LUNEDI": 0,
    "LUNEDÌ": 0,
    "MARTEDI": 1,
    "MARTEDÌ": 1,
    "MERCOLEDI": 2,
    "MERCOLEDÌ": 2,
    "GIOVEDI": 3,
    "GIOVEDÌ": 3,
    "VENERDI": 4,
    "VENERDÌ": 4,
    "SABATO": 5,
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, context=CTX, timeout=90) as r:
        return r.read().decode("utf-8", "replace")


def fold(s: str) -> str:
    s = unescape(str(s)).upper()
    for a, b in (
        ("À", "A"),
        ("È", "E"),
        ("É", "E"),
        ("Ì", "I"),
        ("Ò", "O"),
        ("Ù", "U"),
        ("–", " "),
        ("—", " "),
        ("-", " "),
        (".", " "),
        ("'", ""),
        ("’", ""),
        ("/", " "),
        (",", " "),
        ("(", " "),
        (")", " "),
    ):
        s = s.replace(a, b)
    s = re.sub(r"&#\d+;", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def slugify(zone: str) -> str:
    s = fold(zone).lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s[:48] or "zona"


def load_entries(path: Path) -> list[tuple[int, int, int, int]]:
    text = path.read_text(encoding="utf-8")
    return [(int(y), int(m), int(d), int(b)) for y, m, d, b in ENTRY_RE.findall(text)]


def merge_spa(
    existing: list[tuple[int, int, int, int]],
    spa: list[tuple[int, int, int, int]],
) -> list[tuple[int, int, int, int]]:
    kept = [e for e in existing if e[3] != BIN_SPA]
    return sorted(set(kept) | set(spa))


def strip_scripts(html: str) -> str:
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.I | re.S)
    return re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.I | re.S)


def parse_calendar_page(html: str, year: int) -> dict[str, list[tuple[int, int, int, int]]]:
    """h3 zone title → list of (y,m,d,6)."""
    clean = strip_scripts(html)
    blocks = re.findall(
        r"<h3[^>]*>(.*?)</h3>\s*(.*?)(?=<h3|<h2|$)", clean, flags=re.I | re.S
    )
    out: dict[str, list[tuple[int, int, int, int]]] = {}
    for h, body in blocks:
        ht = " ".join(re.sub(r"<[^>]+>", " ", h).split())
        bt = " ".join(re.sub(r"<[^>]+>", " ", body).split())
        m = re.search(rf"Date spazzamento\s*{year}\s*:\s*(.+)", bt, flags=re.I)
        if not m:
            continue
        ht = unescape(ht)
        ht = re.split(r"\s*[—–\-]\s*Ogni\b", ht, maxsplit=1, flags=re.I)[0].strip()
        ht = re.sub(
            r"\s*[—–\-]\s*(luned\w*|marted\w*|mercoled\w*|gioved\w*|venerd\w*|sabato)\s*$",
            "",
            ht,
            flags=re.I,
        ).strip()
        zone = re.sub(r"\s*[—–\-]\s*", " ", ht)
        zone = re.sub(r"\s+", " ", zone).strip()
        if not zone or len(zone) > 100:
            continue
        dates: list[tuple[int, int, int, int]] = []
        for dd, mm in re.findall(r"(\d{1,2})/(\d{1,2})", m.group(1)):
            dates.append((year, int(mm), int(dd), BIN_SPA))
        if dates:
            out[zone] = sorted(set(dates))
    return out


def parse_pianezza_embedded(html: str, year: int) -> dict[str, list[tuple[int, int, int, int]]]:
    """Parse SETT N (weekday) month-day tables from Pianezza comune page."""
    clean = strip_scripts(html)
    text = " ".join(re.sub(r"<[^>]+>", " ", clean).split())
    text = unescape(text)
    m = re.search(r"SETT\s*1[-–]?3\s*\(luned", text, flags=re.I)
    if not m:
        return {}
    chunk = text[m.start() : m.start() + 8000]
    out: dict[str, list[tuple[int, int, int, int]]] = defaultdict(list)
    row_re = re.compile(
        r"SETT\s*([0-9][-–0-9]*)\s*\(\s*(luned\w*|marted\w*|mercoled\w*|gioved\w*|venerd\w*|sabato)\s*\)\s*"
        r"((?:\d{1,2}(?:\s*[-–]\s*\d{1,2})?\s*)+?)(?=\s*SETT\s|\s*$)",
        flags=re.I,
    )
    for rm in row_re.finditer(chunk):
        sett = rm.group(1).replace("–", "-")
        wd = fold(rm.group(2)).lower()
        key = f"SETT {sett} ({wd})"
        cells = re.findall(r"\d{1,2}(?:\s*[-–]\s*\d{1,2})?", rm.group(3))
        # Table columns: Mar..Dec (10 months). Some rows also start Jan/Feb — take last 10 if longer.
        if len(cells) >= 10:
            cells = cells[-10:]
        for i, cell in enumerate(cells[:10]):
            month = 3 + i
            for day in re.findall(r"\d{1,2}", cell):
                d = int(day)
                if 1 <= d <= 31:
                    out[key].append((year, month, d, BIN_SPA))
        # Aliases matching data-zona fragments: "SETT 1 giovedì", "SETT 1-3 lunedì"
        for alias in (
            f"SETT {sett} {wd}",
            f"SETT {sett.split('-')[0]} {wd}",
        ):
            out[alias].extend(out[key])
        # SETT 1-3 also aliases to SETT 1 and SETT 3 for street labels that list both
        if "-" in sett:
            for part in sett.split("-"):
                out[f"SETT {part} {wd}"].extend(out[key])
    return {k: sorted(set(v)) for k, v in out.items() if v}


def parse_street_options(html: str) -> list[dict]:
    """Parse first meccanizzato select (via-select-alfabetico) street→zones."""
    m = re.search(
        r"<select[^>]*id=['\"]via-select-alfabetico['\"][^>]*>(.*?)</select>",
        html,
        flags=re.I | re.S,
    )
    if not m:
        # fallback: first select with data-zona
        m = re.search(r"<select[^>]*>(.*?)</select>", html, flags=re.I | re.S)
    if not m:
        return []
    rows = []
    for attrs, label in re.findall(
        r"<option([^>]*)>(.*?)</option>", m.group(1), flags=re.I | re.S
    ):
        zona = re.search(r"data-zona=['\"]([^'\"]*)['\"]", attrs, flags=re.I)
        sett = re.search(r"data-settimana=['\"]([^'\"]*)['\"]", attrs, flags=re.I)
        if not zona:
            continue
        z = unescape(zona.group(1)).strip()
        if z in {"", "-"}:
            continue
        lab = unescape(" ".join(re.sub(r"<[^>]+>", " ", label).split()))
        if not lab or lab in {"–", "-"}:
            continue
        rows.append(
            {
                "street": lab,
                "zona": z,
                "settimana": unescape(sett.group(1)).strip() if sett else None,
            }
        )
    return rows


def resolve_schedule_keys(
    comune_id: str,
    zona: str,
    settimana: str | None,
    schedules: dict[str, list],
) -> list[str]:
    """Map option data-zona (+ optional data-settimana) to schedule keys."""
    parts = [p.strip() for p in re.split(r"\s*,\s*", zona) if p.strip()]
    keys: list[str] = []
    sched_fold = {fold(k): k for k in schedules}

    for part in parts:
        pf = fold(part)

        # Alpignano: "NORD - mercoledì pomeriggio" + settimana N
        if comune_id == "alpignano":
            side = "NORD" if "NORD" in pf else ("SUD" if "SUD" in pf else None)
            wd = None
            for name in WEEKDAY_IT:
                if fold(name) in pf:
                    wd = fold(name)
                    break
            sett_n = None
            if settimana:
                sm = re.search(r"(\d+)", settimana)
                if sm:
                    sett_n = sm.group(1)
            if side and sett_n:
                cand = fold(f"SETTIMANA {sett_n} {side}")
                if cand in sched_fold:
                    keys.append(sched_fold[cand])
                    continue
            # fallback: all matching side
            if side:
                for fk, orig in sched_fold.items():
                    if side in fk and (not wd or wd in fk):
                        keys.append(orig)
                if keys:
                    continue

        # Pianezza: zona already like "SETT 1 venerdì mattina"
        if comune_id == "pianezza":
            # strip mattina/pomeriggio
            base = re.sub(r"\s+(MATTINA|POMERIGGIO)\s*$", "", pf)
            base = re.sub(r"\s+", " ", base).strip()
            # SETT 1-3 LUNEDI → try several
            if base in sched_fold:
                keys.append(sched_fold[base])
                continue
            for fk, orig in sched_fold.items():
                if base in fk or fk in base:
                    keys.append(orig)
            if keys:
                continue

        # Venaria / Rivoli / Grugliasco / Collegno: fuzzy contain
        if pf in sched_fold:
            keys.append(sched_fold[pf])
            continue
        # strip weekday suffix for venaria-style
        best = None
        best_score = 0
        for fk, orig in sched_fold.items():
            score = 0
            if pf == fk:
                score = 100
            elif pf in fk or fk in pf:
                score = 50 + min(len(pf), len(fk))
            else:
                # token overlap
                ta, tb = set(pf.split()), set(fk.split())
                inter = ta & tb
                if len(inter) >= 2:
                    score = 10 * len(inter)
            if score > best_score:
                best_score = score
                best = orig
        if best and best_score >= 10:
            keys.append(best)

    # unique preserve order
    seen = set()
    out = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def raccolta_for_spa_zone(comune_id: str, zone: str) -> list[str]:
    """Return zero or more raccolta calendar paths for this spa zone."""
    rules = SPA_TO_RACCOLTA.get(comune_id) or []
    fz = fold(zone)
    hits: list[str] = []
    for needle, cal in rules:
        n = fold(needle)
        if n not in fz:
            continue
        # prefer longer needles already ordered; skip weak CENTRO inside CENTRO STORICO
        # when a CENTRO STORICO rule exists and matched earlier
        if needle == "CENTRO" and "CENTRO STORICO" in fz:
            if any("centrostorico" in h for h in hits):
                continue
        hits.append(cal)
        break  # first (most specific ordered) match
    return hits


def zone_label_from_file(path: Path, comune_name: str, slug: str) -> str:
    first = path.read_text(encoding="utf-8").splitlines()[0]
    zm = re.search(r"(Zona\s+[^(]+)", first, re.I)
    if zm:
        return zm.group(1).strip()
    label = first.split("(")[0].replace("//", "").strip()
    label = re.sub(rf"^{re.escape(comune_name)}\s+", "", label, flags=re.I)
    return label or slug


def update_index_streets(
    index_path: Path,
    comune_id: str,
    street_calendars: dict[str, str],
    spa_zone_labels: list[tuple[str, str]],
) -> None:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    comune = next(c for c in data["comuni"] if c["id"] == comune_id)
    existing = list(comune.get("vie") or [])
    # drop previous spa street vies we may have added (calendars/*-spa-*)
    kept = [
        v
        for v in existing
        if "-spa-" not in v.get("calendar", "")
        and not str(v.get("name", "")).startswith("Spazzamento ")
    ]
    # keep raccolta zone labels, append spa zone labels + streets
    new_vie = kept[:]
    for label, cal in spa_zone_labels:
        new_vie.append({"name": label, "calendar": cal})
    for street, cal in sorted(street_calendars.items(), key=lambda x: x[0].lower()):
        new_vie.append({"name": street, "calendar": cal})
    comune["vie"] = new_vie
    index_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def update_sources(
    sources_path: Path,
    comune_id: str,
    cal_url: str | None,
    source_page: str,
    note: str,
    dry_run: bool,
) -> None:
    data = json.loads(sources_path.read_text(encoding="utf-8"))
    comune = next(c for c in data["comuni"] if c["id"] == comune_id)
    notes = list(comune.get("notes") or [])
    if note not in notes:
        notes.append(note)
    comune["notes"] = notes
    pdfs = list(comune.get("pdfs") or [])
    if cal_url and not any(p.get("url") == cal_url for p in pdfs):
        pdfs.append(
            {
                "year": 2026,
                "label": "Calendario spazzamento meccanizzato",
                "url": cal_url,
            }
        )
    if source_page and not any(p.get("url") == source_page for p in pdfs):
        # source page already in sourcePage; skip duplicate unless useful
        pass
    comune["pdfs"] = pdfs
    if not dry_run:
        sources_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def process_comune(
    *,
    comune_id: str,
    comune_name: str,
    source_page: str,
    year: int,
    outdir: Path,
    dry_run: bool,
    cache_dir: Path,
) -> dict:
    cal_url = CAL_PAGES.get(comune_id)
    cache_dir.mkdir(parents=True, exist_ok=True)
    page_html = fetch(source_page)
    time.sleep(0.25)
    (cache_dir / f"{comune_id}.html").write_text(page_html, encoding="utf-8")

    schedules: dict[str, list[tuple[int, int, int, int]]] = {}
    if cal_url:
        cal_html = fetch(cal_url)
        time.sleep(0.25)
        (cache_dir / f"cal_{comune_id}.html").write_text(cal_html, encoding="utf-8")
        schedules = parse_calendar_page(cal_html, year)
    elif comune_id == "pianezza":
        schedules = parse_pianezza_embedded(page_html, year)

    if not schedules:
        return {"id": comune_id, "status": "no_schedules", "cal_url": cal_url}

    streets = parse_street_options(page_html)
    print(f"  schedules={len(schedules)} streets={len(streets)}")

    # Write spa .h files
    spa_cals: dict[str, str] = {}  # zone name → calendar path without year
    for zone, dates in sorted(schedules.items(), key=lambda x: x[0]):
        slug = slugify(zone)
        cal_path = f"calendars/{comune_id}-spa-{slug}"
        spa_cals[zone] = cal_path
        hpath = outdir / f"{comune_id}-spa-{slug}-{year}.h"
        print(f"  write {hpath.name} days={len(dates)}")
        if not dry_run:
            write_year_file(
                out_path=hpath,
                comune_name=comune_name,
                zone_label=f"Spazzamento {zone}",
                provider="CIDIU",
                addresses=[],
                year=year,
                entries=dates,
            )

    # Merge into raccolta calendars by name
    merged_into: dict[str, set[str]] = defaultdict(set)
    for zone, dates in schedules.items():
        for racc in raccolta_for_spa_zone(comune_id, zone):
            merged_into[racc].add(zone)

    for racc, zones in merged_into.items():
        slug = racc.replace("calendars/", "")
        hpath = outdir / f"{slug}-{year}.h"
        if not hpath.exists():
            continue
        spa_dates: list[tuple[int, int, int, int]] = []
        for z in zones:
            spa_dates.extend(schedules[z])
        spa_dates = sorted(set(spa_dates))
        existing = load_entries(hpath)
        before = sum(1 for e in existing if e[3] == BIN_SPA)
        new_entries = merge_spa(existing, spa_dates)
        after = sum(1 for e in new_entries if e[3] == BIN_SPA)
        print(
            f"  merge {hpath.name}: zones={sorted(zones)} spa {before}->{after}"
        )
        if not dry_run:
            write_year_file(
                out_path=hpath,
                comune_name=comune_name,
                zone_label=zone_label_from_file(hpath, comune_name, slug),
                provider="CIDIU",
                addresses=[],
                year=year,
                entries=new_entries,
            )

    # Map streets → spa calendar
    street_calendars: dict[str, str] = {}
    unresolved = 0
    for row in streets:
        keys = resolve_schedule_keys(
            comune_id, row["zona"], row.get("settimana"), schedules
        )
        if not keys:
            unresolved += 1
            continue
        # union dates if multi; point to first zone's calendar if single,
        # else write combined slug calendar
        if len(keys) == 1:
            street_calendars[row["street"]] = spa_cals[keys[0]]
        else:
            union: list[tuple[int, int, int, int]] = []
            for k in keys:
                union.extend(schedules[k])
            union = sorted(set(union))
            comb = slugify("+".join(keys))
            cal_path = f"calendars/{comune_id}-spa-{comb}"
            hpath = outdir / f"{comune_id}-spa-{comb}-{year}.h"
            if not dry_run:
                write_year_file(
                    out_path=hpath,
                    comune_name=comune_name,
                    zone_label=f"Spazzamento {' / '.join(keys)}",
                    provider="CIDIU",
                    addresses=[],
                    year=year,
                    entries=union,
                )
            street_calendars[row["street"]] = cal_path

    spa_zone_labels = [
        (f"Spazzamento {z}", spa_cals[z]) for z in sorted(spa_cals.keys())
    ]

    if not dry_run:
        update_index_streets(
            outdir / "index.json",
            comune_id,
            street_calendars,
            spa_zone_labels,
        )
        update_sources(
            outdir / "sources.json",
            comune_id,
            cal_url,
            source_page,
            "Spazzamento meccanizzato CIDIU (HTML) importato come calendari spa-* "
            "e mergiato nelle zone raccolta quando i nomi coincidono.",
            dry_run=False,
        )

    return {
        "id": comune_id,
        "status": "ok",
        "schedules": len(schedules),
        "streets_mapped": len(street_calendars),
        "streets_unresolved": unresolved,
        "merged_raccolta": len(merged_into),
        "cal_url": cal_url,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--comune", action="append", help="Escilo comune id (repeatable)")
    ap.add_argument("--all", action="store_true", help="All CIDIU comuni")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--cache-dir",
        type=Path,
        default=ROOT / "tmp_calendars" / "cidiu_spa",
    )
    args = ap.parse_args()

    outdir = ROOT / "docs" / "calendars"
    sources = json.loads((outdir / "sources.json").read_text(encoding="utf-8"))
    cidiu = [c for c in sources["comuni"] if c.get("provider") == "CIDIU"]
    if args.comune:
        want = set(args.comune)
        cidiu = [c for c in cidiu if c["id"] in want]
    elif not args.all:
        ap.error("Specify --all or --comune")

    results = []
    for c in cidiu:
        print(f"== {c['id']}")
        if CAL_PAGES.get(c["id"]) is None and c["id"] != "pianezza":
            print("  skip: no meccanizzato calendar page")
            results.append({"id": c["id"], "status": "skipped_no_page"})
            continue
        try:
            r = process_comune(
                comune_id=c["id"],
                comune_name=c["name"],
                source_page=c["sourcePage"],
                year=args.year,
                outdir=outdir,
                dry_run=args.dry_run,
                cache_dir=args.cache_dir,
            )
            if (
                not args.dry_run
                and isinstance(r, dict)
                and r.get("status") == "ok"
                and c["id"] == "alpignano"
            ):
                from tools.unify_alpignano_street_calendars import main as unify_alp

                print("  unify alpignano street calendars…")
                unify_alp()
                r["unified_streets"] = True
        except Exception as e:
            print(f"  ERR {e}")
            r = {"id": c["id"], "status": "error", "error": str(e)}
        results.append(r)

    print("\nSUMMARY")
    for r in results:
        print(" ", r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
