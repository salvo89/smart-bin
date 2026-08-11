# -*- coding: utf-8 -*-
"""Merge SETA spazzamento (bin 6) into existing zone calendars.

Sources: piani di spazzamento on each comune page at setaspa.com
(e.g. https://www.setaspa.com/comuni/148-comuni/780-borgaro-torinese)

- Servizio di spazzamento manuale - Stradario (PDF table)
- Servizio di spazzamento meccanizzato - Stradario (PDF table)

Does not create new calendars: merges Spazzamento into existing *-YYYY.h by
matching Escilo vie (or zone-PDF streets for zone-label-only comuni) to the
stradario toponimi, voting a dominant spa-zone code, expanding weekday rules.
"""
from __future__ import annotations

import argparse
import calendar as calmod
import json
import re
import ssl
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.covar14_pdf_to_h import write_year_file  # noqa: E402
from tools.download_safe import download_if_needed  # noqa: E402

BIN_SPA = 6
ENTRY_RE = re.compile(
    r"\{(\d{4})\s*,\s*(\d{1,2})\s*,\s*(\d{1,2})\s*,\s*(-?\d+)\s*\}"
)
UA = {"User-Agent": "Mozilla/5.0 EsciloSetaSpa/1.0 (+https://escilo.it/)"}
CTX = ssl.create_default_context()

WEEKDAY = {
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
    "DOMENICA": 6,
}
MONTH = {
    "GENNAIO": 1,
    "FEBBRAIO": 2,
    "MARZO": 3,
    "APRILE": 4,
    "MAGGIO": 5,
    "GIUGNO": 6,
    "LUGLIO": 7,
    "AGOSTO": 8,
    "SETTEMBRE": 9,
    "OTTOBRE": 10,
    "NOVEMBRE": 11,
    "DICEMBRE": 12,
}
ZONE_LABEL_RE = re.compile(r"^zona\b", re.I)


def fold_text(s: str) -> str:
    s = str(s).upper()
    for a, b in (
        ("À", "A"),
        ("È", "E"),
        ("É", "E"),
        ("Ì", "I"),
        ("Ò", "O"),
        ("Ù", "U"),
        ("°", " "),
        ("º", " "),
        ("\ufffd", " "),
        ("–", " "),
        ("—", " "),
        ("-", " "),
    ):
        s = s.replace(a, b)
    s = re.sub(r"[^\x00-\x7F]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_street(s: str) -> str:
    s = fold_text(s)
    s = s.replace("'", "").replace("’", "").replace(".", "")
    s = re.sub(
        r"^(VIA|VIALE|CORSO|PIAZZA|PIAZZALE|STRADA|LARGO|VICOLO|CASCINA|AREA)\s+",
        "",
        s,
    )
    s = re.sub(r"\([^)]*\)", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, context=CTX, timeout=90) as r:
        return r.read().decode("utf-8", "replace")


def abs_url(href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return "https://www.setaspa.com" + href
    return "https://www.setaspa.com/" + href


def discover_links(page_url: str) -> dict[str, list[dict]]:
    """Return {manuale:[], meccanizzato:[], mercati:[], zone_elenco:[]}."""
    html = fetch(page_url)
    pairs = re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        html,
        flags=re.I | re.S,
    )
    out: dict[str, list[dict]] = defaultdict(list)
    seen: set[str] = set()
    for href, inner in pairs:
        label = re.sub(r"<[^>]+>", " ", inner)
        label = " ".join(label.split())
        url = abs_url(href)
        if url in seen:
            continue
        blob = (label + " " + url).lower()
        kind = None
        if "spazzamento" in blob and "manual" in blob and "stradario" in blob:
            kind = "manuale"
        elif "spazzamento" in blob and "meccanizz" in blob and "stradario" in blob:
            kind = "meccanizzato"
        elif "pulizia" in blob and "mercat" in blob:
            kind = "mercati"
        elif "elenco vie" in blob or ("/images/zone/" in blob and blob.endswith(".pdf")):
            kind = "zone_elenco"
        if kind:
            seen.add(url)
            out[kind].append({"label": label, "url": url})
    return dict(out)


def extract_weekdays(text: str) -> list[int]:
    t = fold_text(text)
    # "dal lunedì al sabato"
    m = re.search(
        r"DAL\s+(LUNED\w*|MARTED\w*|MERCOLED\w*|GIOVED\w*|VENERD\w*|SABATO|DOMENICA)"
        r"\s+AL\s+(LUNED\w*|MARTED\w*|MERCOLED\w*|GIOVED\w*|VENERD\w*|SABATO|DOMENICA)",
        t,
    )
    if m:
        a = extract_weekdays(m.group(1))
        b = extract_weekdays(m.group(2))
        if a and b:
            lo, hi = a[0], b[0]
            if lo <= hi:
                days = list(range(lo, hi + 1))
            else:
                days = list(range(lo, 7)) + list(range(0, hi + 1))
            # escluso X
            excl = re.findall(
                r"ESCLUSO\s+(LUNED\w*|MARTED\w*|MERCOLED\w*|GIOVED\w*|VENERD\w*|SABATO|DOMENICA)",
                t,
            )
            for e in excl:
                for d in extract_weekdays(e):
                    if d in days:
                        days.remove(d)
            return days
    found: list[int] = []
    for name, idx in WEEKDAY.items():
        token = fold_text(name)
        if re.search(rf"\b{re.escape(token)}\b", t) and idx not in found:
            found.append(idx)
    return found


def extract_months_range(text: str) -> list[int] | None:
    """Parse '(MARZO - GIUGNO)' or 'MARZO GIUGNO LUGLIO' → month list, or None."""
    t = fold_text(text)
    m = re.search(
        r"\b(GENNAIO|FEBBRAIO|MARZO|APRILE|MAGGIO|GIUGNO|LUGLIO|AGOSTO|SETTEMBRE|OTTOBRE|NOVEMBRE|DICEMBRE)"
        r"\s+(-|A|AL|FINO AL)?\s*"
        r"(GENNAIO|FEBBRAIO|MARZO|APRILE|MAGGIO|GIUGNO|LUGLIO|AGOSTO|SETTEMBRE|OTTOBRE|NOVEMBRE|DICEMBRE)\b",
        t,
    )
    if m:
        a, b = MONTH[m.group(1)], MONTH[m.group(3)]
        if a <= b:
            return list(range(a, b + 1))
        return list(range(a, 13)) + list(range(1, b + 1))
    months = [MONTH[n] for n in MONTH if n in t]
    return months or None


def nth_weekday(year: int, month: int, weekday: int, n: int) -> int | None:
    weeks = calmod.monthcalendar(year, month)
    days = [w[weekday] for w in weeks if w[weekday] != 0]
    if n == -1:
        return days[-1] if days else None
    if 1 <= n <= len(days):
        return days[n - 1]
    return None


def split_seasonal_clauses(giorno: str) -> list[str]:
    """Split multi-line / seasonal giorno rules into clauses."""
    raw = re.sub(r"\s+", " ", giorno).strip()
    if not raw:
        return []
    # Split on ') dal ' boundaries typical of SETA seasonal dual rules
    parts = re.split(r"(?<=\))\s+(?=dal\s)", raw, flags=re.I)
    if len(parts) > 1:
        return [p.strip() for p in parts if p.strip()]
    # Also split on newline leftovers already flattened
    parts = re.split(r"\s+(?=dal\s+lun)", raw, flags=re.I)
    if len(parts) > 1:
        return [p.strip() for p in parts if p.strip()]
    return [raw]


def expand_clause(year: int, clause: str) -> list[tuple[int, int, int, int]]:
    t = fold_text(clause)
    if not t or "DEFINIR" in t:
        return []

    weekdays = extract_weekdays(clause)
    if not weekdays:
        return []

    months = extract_months_range(clause) or list(range(1, 13))

    # ultimo X del mese
    if "ULTIMO" in t and "MESE" in t:
        out = []
        for month in months:
            for wd in weekdays:
                day = nth_weekday(year, month, wd, -1)
                if day:
                    out.append((year, month, day, BIN_SPA))
        return out

    # una volta al mese / ogni mese
    if re.search(r"UNA\s+VOLTA\s+AL\s+MESE|OGNI\s+MESE", t):
        out = []
        for month in months:
            for wd in weekdays:
                day = nth_weekday(year, month, wd, 1)
                if day:
                    out.append((year, month, day, BIN_SPA))
        return out

    # una volta ogni due mesi
    if re.search(r"OGNI\s+DUE\s+MESI|UNA\s+VOLTA\s+OGNI\s+2\s+MESI", t):
        out = []
        for month in months:
            if month % 2 == 0:
                continue
            for wd in weekdays:
                day = nth_weekday(year, month, wd, 1)
                if day:
                    out.append((year, month, day, BIN_SPA))
        return out

    # ogni due settimane / biweekly
    biweekly = bool(re.search(r"OGNI\s+DUE\s+SETTIMANE|OGNI\s+15\s+GIORNI", t))

    out: list[tuple[int, int, int, int]] = []
    for month in months:
        weeks = calmod.monthcalendar(year, month)
        for wd in weekdays:
            days = [w[wd] for w in weeks if w[wd] != 0]
            if biweekly:
                days = days[::2]
            for day in days:
                out.append((year, month, day, BIN_SPA))
    return out


def expand_giorno(year: int, giorno: str) -> list[tuple[int, int, int, int]]:
    entries: list[tuple[int, int, int, int]] = []
    for clause in split_seasonal_clauses(giorno):
        entries.extend(expand_clause(year, clause))
    return sorted(set(entries))


def load_entries(path: Path) -> list[tuple[int, int, int, int]]:
    text = path.read_text(encoding="utf-8")
    return [(int(y), int(m), int(d), int(b)) for y, m, d, b in ENTRY_RE.findall(text)]


def merge_spa(
    existing: list[tuple[int, int, int, int]],
    spa: list[tuple[int, int, int, int]],
) -> list[tuple[int, int, int, int]]:
    kept = [e for e in existing if e[3] != BIN_SPA]
    return sorted(set(kept) | set(spa))


def parse_spa_pdf(path: Path, tipo: str) -> tuple[dict[str, list[str]], dict[str, set[str]]]:
    """Return schedules[zona]=[giorno,...], street_zones[norm]=set(zona)."""
    doc = fitz.open(path)
    schedules: dict[str, list[str]] = defaultdict(list)
    street_zones: dict[str, set[str]] = defaultdict(set)
    for page in doc:
        tabs = page.find_tables()
        if not tabs or not tabs.tables:
            continue
        for table in tabs.tables:
            rows = table.extract()
            if not rows or len(rows) < 2:
                continue
            header = [fold_text(str(c or "")) for c in rows[0]]

            def col(*names: str) -> int | None:
                for i, h in enumerate(header):
                    if any(n in h for n in names):
                        return i
                return None

            iz = col("ZONA", "CODICE")
            it = col("TOPONIMO")
            ig = col("GIORNO")
            if it is None or ig is None:
                continue
            for row in rows[1:]:
                if not row or it >= len(row):
                    continue
                topo = " ".join(str(row[it] or "").split())
                if not topo or len(topo) < 3:
                    continue
                if "definir" in topo.lower():
                    continue
                giorno = " ".join(str(row[ig] or "").split()) if ig < len(row) else ""
                if not giorno or "definir" in giorno.lower():
                    continue
                zona = ""
                if iz is not None and iz < len(row):
                    zona = " ".join(str(row[iz] or "").split())
                key = spa_code(tipo, zona, giorno)
                if giorno not in schedules[key]:
                    schedules[key].append(giorno)
                street_zones[norm_street(topo)].add(key)
                # also index full folded toponimo without stripping prefix
                street_zones[fold_text(topo).replace("'", "")].add(key)
    doc.close()
    return dict(schedules), dict(street_zones)


def parse_zone_elenco_streets(path: Path) -> dict[str, list[str]]:
    """Parse SETA images/zone/*.pdf → collection-zone label → street names.

    Zone labels look like 'SMART SOLO RSU - ZONA A', 'ZONA 1', 'Z1', etc.
    """
    doc = fitz.open(path)
    by_zone: dict[str, list[str]] = defaultdict(list)
    for page in doc:
        tabs = page.find_tables()
        if not tabs or not tabs.tables:
            continue
        for table in tabs.tables:
            rows = table.extract()
            if not rows or len(rows) < 2:
                continue
            header = [fold_text(str(c or "")) for c in rows[0]]

            def col(*names: str) -> int | None:
                for i, h in enumerate(header):
                    if any(n in h for n in names):
                        return i
                return None

            iz = col("ZONA")
            it = col("TOPONIMO")
            if iz is None or it is None:
                continue
            for row in rows[1:]:
                if not row or iz >= len(row) or it >= len(row):
                    continue
                zona = " ".join(str(row[iz] or "").split())
                topo = " ".join(str(row[it] or "").split())
                if not zona or not topo or len(topo) < 3:
                    continue
                by_zone[zona].append(topo)
    doc.close()
    return dict(by_zone)


def map_calendar_to_zone_streets(
    cal_slug: str,
    zone_label: str,
    zone_streets: dict[str, list[str]],
) -> list[str]:
    """Best-effort map Escilo calendar (za/zb/z1/…) to zone-elenco streets."""
    if not zone_streets:
        return []
    # extract token from slug / label: za → A, z1 → 1, zb → B
    m = re.search(r"-z([a-z0-9]+)$", cal_slug)
    token = (m.group(1) if m else "").upper()
    if token == "UNICA":
        out: list[str] = []
        for sts in zone_streets.values():
            out.extend(sts)
        return out

    candidates: list[tuple[int, str, list[str]]] = []
    for zname, sts in zone_streets.items():
        zf = fold_text(zname)
        score = 0
        if token and re.search(rf"\bZONA\s*{re.escape(token)}\b", zf):
            score += 5
        # Z1, Z1A, Z1B, Z2A… for numeric tokens
        if token and re.search(rf"\bZ\s*{re.escape(token)}[A-Z]?\b", zf):
            score += 5
        if token and token.isalpha() and len(token) <= 2:
            # letter zones: ZONA A / SMART … ZONA B
            if re.search(rf"\bZONA\s+{re.escape(token)}\b", zf):
                score += 5
            if re.search(rf"\bZ{re.escape(token)}\b", zf):
                score += 4
        # named zones: zcentro / zest / zovest / znord / zsud / zcapoluogo
        named = {
            "CENTRO": ("CENTRO", "CENTER"),
            "EST": ("EST", "EAST"),
            "OVEST": ("OVEST", "WEST"),
            "NORD": ("NORD", "NORTH"),
            "SUD": ("SUD", "SOUTH"),
            "CAPOLUOGO": ("CAPOLUOGO",),
            "OLTREPO": ("OLTREPO", "OLTRE PO", "PESCARITO"),
        }
        for key, alts in named.items():
            if token == key or token.startswith(key):
                if any(a in zf for a in alts):
                    score += 4
        if token and token in zf.replace(" ", ""):
            score += 1
        # prefer porta-a-porta / SMART SOLO RSU over SMART 5 FRAZIONI when both match
        if "SMART 5" in zf:
            score -= 1
        if "SOLO RSU" in zf or "PORTA" in zf:
            score += 1
        if score > 0:
            candidates.append((score, zname, sts))
    if not candidates:
        return []
    candidates.sort(key=lambda x: -x[0])
    best = candidates[0][0]
    out = []
    for score, _name, sts in candidates:
        if score == best:
            out.extend(sts)
    return out


def lookup_codes(street: str, street_zones: dict[str, set[str]]) -> set[str]:
    n = norm_street(street)
    if not n:
        return set()
    if n in street_zones:
        return set(street_zones[n])
    for k, zones in street_zones.items():
        if norm_street(k) == n:
            return set(zones)
    parts = n.split()
    if not parts:
        return set()
    token = parts[-1]
    if len(token) <= 3:
        return set()
    hits: list[tuple[str, set[str]]] = []
    for k, zones in street_zones.items():
        kn = norm_street(k)
        kn_parts = kn.split()
        if not kn_parts:
            continue
        if kn.endswith(token) or token == kn_parts[-1]:
            hits.append((k, zones))
    if len(hits) == 1:
        return set(hits[0][1])
    if hits:
        hits.sort(key=lambda x: len(norm_street(x[0])))
        return set(hits[0][1])
    return set()


def dates_for_code(
    code: str,
    schedules: dict[str, list[str]],
    year: int,
) -> list[tuple[int, int, int, int]]:
    entries: list[tuple[int, int, int, int]] = []
    for giorno in schedules.get(code, []):
        entries.extend(expand_giorno(year, giorno))
    return sorted(set(e for e in entries if e[0] == year))


def density_ok(n: int) -> bool:
    # Allow up to ~3x/week (~156); block near-daily Mon–Sat (~313).
    return 4 <= n <= 180


def spa_code(tipo: str, zona: str, giorno: str) -> str:
    z = " ".join(zona.split()) if zona else ""
    if z:
        return f"{tipo}:{z}"
    # No zone column: group by weekday rule so we don't union Fri+Sat streets.
    rule = fold_text(giorno)[:80] or "UNKNOWN"
    return f"{tipo}:rule:{rule}"


def select_code(
    votes: Counter[str],
    schedules: dict[str, list[str]],
    year: int,
) -> str | None:
    if not votes:
        return None
    # Prefer meccanizzato, then codes whose expansion is in a sane density range.
    ranked = []
    for code, n in votes.most_common():
        if code not in schedules:
            continue
        spa = dates_for_code(code, schedules, year)
        ok = density_ok(len(spa))
        mec = code.startswith("meccanizzato:")
        ranked.append((ok, mec, n, -len(spa), code, spa))
    if not ranked:
        return None
    # Prefer density-ok; among those prefer meccanizzato, then votes, then fewer days.
    # Deterministic tie-break on code name.
    ranked.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4]), reverse=True)
    best = ranked[0]
    if not best[0]:
        # no density-ok code — still allow if we have something with days (<= max)
        for item in ranked:
            if item[5] and len(item[5]) <= 180:
                return item[4]
        return None
    return best[4]


def escilo_calendars(index_path: Path, comune_id: str) -> dict[str, list[str]]:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    comune = next(c for c in data["comuni"] if c["id"] == comune_id)
    by_cal: dict[str, list[str]] = defaultdict(list)
    for v in comune.get("vie") or []:
        by_cal[v["calendar"]].append(v["name"])
    return dict(by_cal)


def zone_label_from_file(path: Path, comune_name: str, slug: str) -> str:
    first = path.read_text(encoding="utf-8").splitlines()[0]
    zm = re.search(r"(Zona\s+[^(]+)", first, re.I)
    if zm:
        return zm.group(1).strip()
    label = first.split("(")[0].replace("//", "").strip()
    label = re.sub(rf"^{re.escape(comune_name)}\s+", "", label, flags=re.I)
    return label or slug


def streets_for_calendar(
    cal_path: str,
    names: list[str],
    zone_streets: dict[str, list[str]],
) -> list[str]:
    concrete = [n for n in names if not ZONE_LABEL_RE.match(n.strip())]
    if len(concrete) >= 2:
        return concrete
    # zone-label only (or nearly): pull streets from zone elenco PDF
    slug = cal_path.replace("calendars/", "")
    label = names[0] if names else ""
    mapped = map_calendar_to_zone_streets(slug, label, zone_streets)
    if mapped:
        return mapped
    if concrete:
        return concrete
    # last resort: all zone streets
    out: list[str] = []
    for sts in zone_streets.values():
        out.extend(sts)
    return out


def merge_comune(
    *,
    comune_id: str,
    comune_name: str,
    years: list[int],
    outdir: Path,
    schedules: dict[str, list[str]],
    street_zones: dict[str, set[str]],
    zone_streets: dict[str, list[str]],
    dry_run: bool,
    min_matched: int = 1,
) -> tuple[int, int]:
    by_cal = escilo_calendars(outdir / "index.json", comune_id)
    merged = skipped = 0
    for cal_path, names in sorted(by_cal.items()):
        streets = streets_for_calendar(cal_path, names, zone_streets)
        slug = cal_path.replace("calendars/", "")
        votes: Counter[str] = Counter()
        matched = 0
        for st in streets:
            codes = lookup_codes(st, street_zones)
            if codes:
                matched += 1
                for c in codes:
                    votes[c] += 1
        if matched < min_matched or not votes:
            print(f"  skip {slug}: matched {matched}/{len(streets)}")
            skipped += 1
            continue

        for year in years:
            path = outdir / f"{slug}-{year}.h"
            if not path.exists():
                continue
            code = select_code(votes, schedules, year)
            if not code:
                print(f"  skip {slug}-{year}: no usable spa code votes={dict(votes.most_common(3))}")
                skipped += 1
                continue
            spa = dates_for_code(code, schedules, year)
            if not density_ok(len(spa)):
                # try next-best density-ok among voted
                alt = None
                for c, _n in votes.most_common():
                    if c == code:
                        continue
                    cand = dates_for_code(c, schedules, year)
                    if density_ok(len(cand)):
                        alt, spa, code = c, cand, c
                        break
                if alt is None and len(spa) > 180:
                    print(
                        f"  skip {slug}-{year}: spa too dense ({len(spa)}) code={code} "
                        f"votes={dict(votes.most_common(3))}"
                    )
                    skipped += 1
                    continue
                if len(spa) < 4:
                    print(f"  skip {slug}-{year}: too few spa days {len(spa)} code={code}")
                    skipped += 1
                    continue
            existing = load_entries(path)
            before = sum(1 for e in existing if e[3] == BIN_SPA)
            new_entries = merge_spa(existing, spa)
            after = sum(1 for e in new_entries if e[3] == BIN_SPA)
            print(
                f"  merge {path.name}: matched={matched}/{len(streets)} "
                f"code={code} votes={dict(votes.most_common(3))} spa {before}->{after}"
            )
            if not dry_run:
                write_year_file(
                    out_path=path,
                    comune_name=comune_name,
                    zone_label=zone_label_from_file(path, comune_name, slug),
                    provider="SETA",
                    addresses=[],
                    year=year,
                    entries=new_entries,
                )
            merged += 1
    return merged, skipped


def update_sources(
    sources_path: Path,
    updates: dict[str, list[dict]],
    dry_run: bool,
) -> None:
    data = json.loads(sources_path.read_text(encoding="utf-8"))
    note = (
        "Spazzamento SETA (stradario manuale/meccanizzato) mergiato come bin "
        "Spazzamento nelle zone esistenti."
    )
    for cid, links in updates.items():
        comune = next(c for c in data["comuni"] if c["id"] == cid)
        notes = list(comune.get("notes") or [])
        if note not in notes:
            notes.append(note)
        comune["notes"] = notes
        pdfs = list(comune.get("pdfs") or [])
        for link in links:
            if any(p.get("url") == link["url"] for p in pdfs):
                continue
            pdfs.append(
                {
                    "year": 2026,
                    "label": link["label"],
                    "url": link["url"],
                }
            )
        comune["pdfs"] = pdfs
    if not dry_run:
        sources_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"sources.json updated for: {', '.join(sorted(updates))}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, action="append", help="Year(s) to merge (default: 2026 2027)")
    ap.add_argument("--comune", action="append", help="Escilo comune id (repeatable)")
    ap.add_argument("--all", action="store_true", help="All SETA comuni with spa PDFs")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--cache-dir",
        type=Path,
        default=ROOT / "tmp_calendars" / "seta_spa",
    )
    ap.add_argument("--discover-only", action="store_true")
    args = ap.parse_args()
    years = args.year or [2026, 2027]
    outdir = ROOT / "docs" / "calendars"
    sources_path = outdir / "sources.json"
    sources = json.loads(sources_path.read_text(encoding="utf-8"))
    seta = [c for c in sources["comuni"] if c.get("provider") == "SETA"]
    if args.comune:
        wanted = set(args.comune)
        targets = [c for c in seta if c["id"] in wanted]
    else:
        targets = seta if args.all else [c for c in seta if c["id"] == "borgaro-torinese"]

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    discover_path = args.cache_dir / "discover.json"
    discovered: dict[str, dict] = {}

    total_m = total_s = 0
    source_updates: dict[str, list[dict]] = {}

    for comune in targets:
        cid = comune["id"]
        print(f"\n== {cid} ==")
        try:
            links = discover_links(comune["sourcePage"])
        except Exception as exc:  # noqa: BLE001
            print(f"  discover error: {exc}")
            continue
        discovered[cid] = {"page": comune["sourcePage"], "links": links}
        time.sleep(0.1)

        man = links.get("manuale") or []
        mec = links.get("meccanizzato") or []
        if not man and not mec:
            print("  no spa stradario PDFs")
            continue
        if args.discover_only:
            print("  man", [x["url"] for x in man])
            print("  mec", [x["url"] for x in mec])
            continue

        schedules: dict[str, list[str]] = {}
        street_zones: dict[str, set[str]] = defaultdict(set)
        for kind, items in (("manuale", man), ("meccanizzato", mec)):
            for i, item in enumerate(items):
                dest = args.cache_dir / f"{cid}-{kind}{i}.pdf"
                download_if_needed(item["url"], dest)
                sch, stz = parse_spa_pdf(dest, kind)
                schedules.update(sch)
                for k, zs in stz.items():
                    street_zones[k] |= zs

        zone_streets: dict[str, list[str]] = {}
        for item in links.get("zone_elenco") or []:
            dest = args.cache_dir / f"{cid}-zone.pdf"
            try:
                download_if_needed(item["url"], dest)
                zone_streets = parse_zone_elenco_streets(dest)
            except Exception as exc:  # noqa: BLE001
                print(f"  zone elenco warn: {exc}")

        print(
            f"  spa codes={len(schedules)} streets={len(street_zones)} "
            f"zone_elenco_zones={len(zone_streets)}"
        )
        m, s = merge_comune(
            comune_id=cid,
            comune_name=comune["name"],
            years=years,
            outdir=outdir,
            schedules=schedules,
            street_zones=dict(street_zones),
            zone_streets=zone_streets,
            dry_run=args.dry_run,
        )
        total_m += m
        total_s += s
        source_updates[cid] = man + mec

    discover_path.write_text(
        json.dumps(discovered, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if source_updates and not args.discover_only:
        update_sources(sources_path, source_updates, args.dry_run)

    print(f"\nDone merged={total_m} skipped={total_s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
