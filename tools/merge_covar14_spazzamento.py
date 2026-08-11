# -*- coding: utf-8 -*-
"""Merge Covar14 spazzamento (bin 6) into existing zone calendars.

Source: https://www.covar14.it/it/search-calendario-spazzamento
(Drupal facet search by comune + via → Zona / tipo / giorno / orario).

Strategy (same as CCS Chieri):
1. Scrape per-comune zone schedules + street→spa-zone map
2. Match Escilo vie to Covar streets
3. Pick dominant spa zone code(s) per Escilo calendar
4. Expand nth-weekday / month rules into concrete dates
5. Merge into existing *-YYYY.h (no new calendars)
"""
from __future__ import annotations

import argparse
import calendar as calmod
import json
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.covar14_pdf_to_h import write_year_file  # noqa: E402

BIN_SPA = 6
ENTRY_RE = re.compile(
    r"\{(\d{4})\s*,\s*(\d{1,2})\s*,\s*(\d{1,2})\s*,\s*(-?\d+)\s*\}"
)
SEARCH = "https://www.covar14.it/it/search-calendario-spazzamento"
CTX = ssl.create_default_context()
UA = {"User-Agent": "Mozilla/5.0 EsciloCovarSpa/1.0 (+https://escilo.it/)"}

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
ORDINAL = {
    "I": 1,
    "1": 1,
    "PRIMO": 1,
    "II": 2,
    "2": 2,
    "SECONDO": 2,
    "III": 3,
    "3": 3,
    "TERZO": 3,
    "IV": 4,
    "4": 4,
    "QUARTO": 4,
    "V": 5,
    "5": 5,
}


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.in_cell = False
        self.rows: list[list[str]] = []
        self.cur: list[str] = []
        self.buf: list[str] = []

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        if tag == "table":
            self.in_table = True
        elif self.in_table and tag in {"td", "th"}:
            self.in_cell = True
            self.buf = []
        elif self.in_table and tag == "tr":
            self.cur = []

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag in {"td", "th"} and self.in_cell:
            text = re.sub(r"\s+", " ", "".join(self.buf)).strip()
            self.cur.append(text)
            self.in_cell = False
        elif tag == "tr" and self.in_table and self.cur:
            self.rows.append(self.cur)
            self.cur = []
        elif tag == "table":
            self.in_table = False

    def handle_data(self, data):  # noqa: ANN001
        if self.in_cell:
            self.buf.append(data)


def fetch(url: str, cache: Path | None = None, sleep_s: float = 0.12) -> str:
    if cache and cache.exists() and cache.stat().st_size > 500:
        return cache.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, context=CTX, timeout=90) as r:
        body = r.read().decode("utf-8", "replace")
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(body, encoding="utf-8")
    if sleep_s:
        time.sleep(sleep_s)
    return body


def parse_tables(html: str) -> list[list[str]]:
    p = TableParser()
    p.feed(html)
    return p.rows


def norm_street(s: str) -> str:
    s = str(s).upper()
    for a, b in (
        ("À", "A"),
        ("È", "E"),
        ("É", "E"),
        ("Ì", "I"),
        ("Ò", "O"),
        ("Ù", "U"),
        ("'", ""),
        ("’", ""),
        (".", ""),
        ("°", ""),
        ("DEG", ""),
    ):
        s = s.replace(a, b)
    s = re.sub(
        r"^(VIA|VIALE|CORSO|PIAZZA|STRADA|LARGO|VICOLO|CASCINA)\s+",
        "",
        s,
    )
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def load_entries(path: Path) -> list[tuple[int, int, int, int]]:
    text = path.read_text(encoding="utf-8")
    return [(int(y), int(m), int(d), int(b)) for y, m, d, b in ENTRY_RE.findall(text)]


def merge_spa(
    existing: list[tuple[int, int, int, int]],
    spa: list[tuple[int, int, int, int]],
) -> list[tuple[int, int, int, int]]:
    kept = [e for e in existing if e[3] != BIN_SPA]
    return sorted(set(kept) | set(spa))


def fold_text(s: str) -> str:
    s = s.upper()
    for a, b in (
        ("À", "A"),
        ("È", "E"),
        ("É", "E"),
        ("Ì", "I"),
        ("Ò", "O"),
        ("Ù", "U"),
        ("°", " "),
        ("º", " "),
        ("�", " "),
        ("–", " "),
        ("—", " "),
        ("-", " "),
    ):
        s = s.replace(a, b)
    # drop leftover non-ascii so month tokens stay contiguous across bad encoding
    s = re.sub(r"[^\x00-\x7F]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def extract_weekdays(text: str) -> list[int]:
    t = fold_text(text)
    found: list[int] = []
    for name, idx in WEEKDAY.items():
        if fold_text(name) in t and idx not in found:
            found.append(idx)
    return found


def extract_months(text: str) -> list[int]:
    t = fold_text(text)
    found: list[int] = []
    for name, num in MONTH.items():
        if name in t and num not in found:
            found.append(num)
    return found


def extract_ordinals(text: str) -> list[int]:
    t = fold_text(text)
    # I E III LUNEDI / I LUNEDI DEL MESE / 1 E 3
    found: list[int] = []
    for m in re.finditer(
        r"\b(IV|III|II|I|V|1|2|3|4|5|PRIMO|SECONDO|TERZO|QUARTO)\b",
        t,
    ):
        # only count ordinals near weekday / DEL MESE context
        start = max(0, m.start() - 5)
        end = min(len(t), m.end() + 40)
        window = t[start:end]
        if "LUNED" in window or "MARTED" in window or "MERCOLED" in window or "GIOVED" in window or "VENERD" in window or "SABATO" in window or "DOMENICA" in window or "DEL MESE" in window or "MESE" in window:
            n = ORDINAL.get(m.group(1))
            if n and n not in found:
                found.append(n)
    return found


def interrupted_months(orario: str) -> set[int]:
    t = fold_text(orario)
    m = re.search(
        r"SERVIZIO\s+INTERR\w*\s+(?:NEI\s+)?MESI?\s+DI\s+(.+?)(?=\s+I\b|\s+II\b|\s+III\b|\s+IV\b|\s+OFFERTA|\s+MATTINO|$)",
        t,
    )
    if not m:
        m = re.search(
            r"INTERR\w*\s+(?:NEL(?:LA|LE)?\s+)?MESE?\s+DI\s+(.+?)(?=\s+I\b|\s+II\b|\s+III\b|\s+IV\b|\s+MATTINO|$)",
            t,
        )
    if not m:
        return set()
    return set(extract_months(m.group(1)))


def active_months(orario: str) -> list[int]:
    t = fold_text(orario)
    # "Servizio attivo nei mesi di APRILE (1/30) - GIUGNO ..."
    m = re.search(
        r"ATTIVO\s+NEI\s+MESI\s+DI\s+(.+?)(?=\s+I\b|\s+II\b|\s+III\b|\s+IV\b|$)",
        t,
    )
    if m:
        return extract_months(m.group(1))
    # Prefer service-months clause after "DEL MESE", not "Interrotto nei mesi di …"
    m = re.search(r"DEL MESE\s+MESI\s+DI\s+(.+)", t)
    if not m:
        m = re.search(r"DEL MESE.{0,10}MESI\s+DI\s+(.+)", t)
    if not m:
        parts = list(re.finditer(r"(?<!NEI )MESI\s+DI\s+", t))
        if parts:
            start = parts[-1].end()
            return extract_months(t[start:])
        return []
    return extract_months(m.group(1))


def nth_weekday(year: int, month: int, weekday: int, n: int) -> int | None:
    """Return day-of-month for the n-th weekday (1-based), or None."""
    weeks = calmod.monthcalendar(year, month)
    days = [w[weekday] for w in weeks if w[weekday] != 0]
    if 1 <= n <= len(days):
        return days[n - 1]
    return None


def expand_month_scoped(
    year: int, orario: str
) -> list[tuple[int, int, int, int]] | None:
    """Handle 'I MERCOLEDI DEL MESE (APRILE) I E III … (GIUGNO LUGLIO …)'."""
    t = fold_text(orario)
    matches = list(
        re.finditer(
            r"((?:I|II|III|IV|V|E|\s)+)\s*"
            r"(LUNED\w*|MARTED\w*|MERCOLED\w*|GIOVED\w*|VENERD\w*|SABATO|DOMENICA)"
            r"\s+DEL MESE\s*\(([^)]+)\)",
            t,
        )
    )
    if not matches:
        return None
    out: list[tuple[int, int, int, int]] = []
    for m in matches:
        ordinals = extract_ordinals(m.group(1) + " DEL MESE")
        weekdays = extract_weekdays(m.group(2))
        months = extract_months(m.group(3))
        if not ordinals or not weekdays or not months:
            continue
        for month in months:
            for wd in weekdays:
                for n in ordinals:
                    day = nth_weekday(year, month, wd, n)
                    if day:
                        out.append((year, month, day, BIN_SPA))
    return sorted(set(out)) if out else None


def expand_rule(
    year: int,
    weekday_text: str,
    orario: str,
) -> list[tuple[int, int, int, int]]:
    scoped = expand_month_scoped(year, orario)
    if scoped is not None:
        return scoped

    weekdays = extract_weekdays(weekday_text) or extract_weekdays(orario)
    if not weekdays:
        return []
    months = active_months(orario)
    stopped = interrupted_months(orario)
    ordinals = extract_ordinals(orario)
    if not months:
        months = [m for m in range(1, 13) if m not in stopped]
    if not ordinals:
        # every matching weekday in active months (weekly / blank orario)
        ordinals = [1, 2, 3, 4, 5]

    out: list[tuple[int, int, int, int]] = []
    for month in months:
        if month in stopped:
            continue
        for wd in weekdays:
            for n in ordinals:
                day = nth_weekday(year, month, wd, n)
                if day:
                    out.append((year, month, day, BIN_SPA))
    return out


def zone_specificity(
    zona: str, schedules: dict[str, list[tuple[str, str, str]]]
) -> int:
    """Higher = more useful calendar rule (prefer meccanizzato with months/ordinals)."""
    best = 0
    for tipo, _giorno, orario in schedules.get(zona, []):
        score = 0
        t = fold_text(tipo + " " + orario)
        if "MECCANIZZATO" in t or "MISTO" in t:
            score += 3
        if extract_ordinals(orario):
            score += 3
        if active_months(orario) or expand_month_scoped(2026, orario):
            score += 3
        if orario.strip():
            score += 1
        if "MANUALE" in t and not orario.strip():
            score -= 1
        best = max(best, score)
    return best


def parse_zone_schedules(html: str) -> dict[str, list[tuple[str, str, str]]]:
    """zona -> list of (tipo, giorno, orario)."""
    rows = parse_tables(html)
    out: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for r in rows:
        if len(r) < 4:
            continue
        if r[0].strip().lower() == "zona":
            continue
        zona = r[0].strip()
        tipo = r[1].strip()
        giorno = r[2].strip()
        orario = r[3].strip()
        if not zona or not giorno:
            continue
        out[zona].append((tipo, giorno, orario))
    return dict(out)


def dates_for_zone(
    zona: str,
    schedules: dict[str, list[tuple[str, str, str]]],
    year: int,
) -> list[tuple[int, int, int, int]]:
    rules = schedules.get(zona, [])
    if not rules:
        return []
    # Prefer dated meccanizzato/misto rules over weekly blank/manual fillers.
    dated = [
        (t, g, o)
        for t, g, o in rules
        if o.strip()
        and (
            extract_ordinals(o)
            or active_months(o)
            or expand_month_scoped(year, o)
        )
    ]
    mec = [
        (t, g, o)
        for t, g, o in rules
        if "MECCANIZZATO" in fold_text(t) or "MISTO" in fold_text(t)
    ]
    nonempty = [(t, g, o) for t, g, o in rules if o.strip()]
    use = dated or mec or nonempty or rules
    entries: list[tuple[int, int, int, int]] = []
    for _tipo, giorno, orario in use:
        entries.extend(expand_rule(year, giorno, orario))
    return sorted(set(entries))


def extract_comune_options(html: str) -> dict[str, int]:
    """name lower -> taxonomy id from facet links."""
    out: dict[str, int] = {}
    for m in re.finditer(
        r'data-drupal-facet-item-value="(\d+)"[^>]*>[\s\S]{0,200}?'
        r'<span class="facet-item__value">\s*Comune\s+di\s+([^<]+)',
        html,
        re.I,
    ):
        label = re.sub(r"\s+", " ", m.group(2)).strip().lower()
        out[label] = int(m.group(1))
    return out


def extract_streets(html: str) -> list[str]:
    streets = sorted(
        set(
            urllib.parse.unquote(s.replace("+", " "))
            for s in re.findall(r"vie_piazze_localita(?:%3A|:)([^\"&<]+)", html)
        )
    )
    return streets


def scrape_comune(
    comune_tid: int,
    cache_dir: Path,
    force: bool = False,
) -> tuple[dict[str, list[tuple[str, str, str]]], dict[str, set[str]]]:
    comune_cache = cache_dir / f"comune_{comune_tid}.html"
    if force and comune_cache.exists():
        comune_cache.unlink()
    html = fetch(f"{SEARCH}?f%5B0%5D=comune%3A{comune_tid}", comune_cache)
    schedules = parse_zone_schedules(html)
    streets = extract_streets(html)
    street_zones: dict[str, set[str]] = {}
    for i, street in enumerate(streets):
        safe = re.sub(r"[^\w.-]+", "_", street)[:80]
        scache = cache_dir / f"street_{comune_tid}_{safe}.html"
        if force and scache.exists():
            scache.unlink()
        q = urllib.parse.quote(street)
        url = f"{SEARCH}?f%5B0%5D=comune%3A{comune_tid}&f%5B1%5D=vie_piazze_localita%3A{q}"
        shtml = fetch(url, scache)
        zones = {
            r[0].strip()
            for r in parse_tables(shtml)
            if r and r[0].strip().lower() != "zona" and r[0].strip()
        }
        street_zones[street] = zones
        if (i + 1) % 25 == 0 or i + 1 == len(streets):
            print(f"  streets {i+1}/{len(streets)}")
    return schedules, street_zones


def escilo_calendars(index_path: Path, comune_id: str) -> dict[str, list[str]]:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    comune = next(c for c in data["comuni"] if c["id"] == comune_id)
    by_cal: dict[str, list[str]] = defaultdict(list)
    for v in comune.get("vie") or []:
        by_cal[v["calendar"]].append(v["name"])
    return dict(by_cal)


def lookup_codes(street: str, street_zones: dict[str, set[str]]) -> set[str]:
    n = norm_street(street)
    if not n:
        return set()
    # exact
    for k, zones in street_zones.items():
        if norm_street(k) == n:
            return set(zones)
    # last-token match (len>3)
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


def select_codes(
    votes: Counter[str],
    schedules: dict[str, list[tuple[str, str, str]]],
) -> set[str]:
    if not votes:
        return set()
    # Keep only codes that exist in scraped schedules.
    usable = Counter({k: v for k, v in votes.items() if k in schedules})
    if not usable:
        return set()
    top_votes = usable.most_common(1)[0][1]
    # Among codes with a meaningful share of street matches, prefer
    # higher-specificity schedules (meccanizzato / nth-week / month lists).
    threshold = max(2, int(0.5 * top_votes))
    candidates = [(c, n) for c, n in usable.items() if n >= threshold]
    if not candidates:
        candidates = list(usable.items())
    # If the vote leader is a vague weekly manual, prefer specific meccanizzato
    # codes that still have a few street hits.
    leader = max(candidates, key=lambda kv: kv[1])[0]
    if zone_specificity(leader, schedules) <= 1:
        specific = [
            (c, n)
            for c, n in usable.items()
            if zone_specificity(c, schedules) >= 7 and n >= 2
        ]
        if specific:
            candidates = specific
    candidates.sort(
        key=lambda kv: (zone_specificity(kv[0], schedules), kv[1]),
        reverse=True,
    )
    selected = {candidates[0][0]}
    # Optional second code: high votes and similar specificity.
    for c, n in candidates[1:]:
        if n < max(2, int(0.8 * candidates[0][1])):
            continue
        if abs(zone_specificity(c, schedules) - zone_specificity(candidates[0][0], schedules)) > 2:
            continue
        # Avoid pairing two dense weekly manuals (near-daily union).
        if zone_specificity(c, schedules) <= 1 and zone_specificity(candidates[0][0], schedules) <= 1:
            continue
        selected.add(c)
        break
    return selected


def zone_label_from_file(path: Path, comune_name: str, slug: str) -> str:
    first = path.read_text(encoding="utf-8").splitlines()[0]
    zm = re.search(r"(Zona\s+[^(]+)", first, re.I)
    if zm:
        return zm.group(1).strip()
    label = first.split("(")[0].replace("//", "").strip()
    label = re.sub(rf"^{re.escape(comune_name)}\s+", "", label)
    return label or slug


def merge_comune(
    *,
    comune_id: str,
    comune_name: str,
    year: int,
    outdir: Path,
    schedules: dict[str, list[tuple[str, str, str]]],
    street_zones: dict[str, set[str]],
    dry_run: bool,
    min_matched: int = 2,
) -> tuple[int, int]:
    by_cal = escilo_calendars(outdir / "index.json", comune_id)
    merged = skipped = 0
    for cal_path, streets in sorted(by_cal.items()):
        slug = cal_path.replace("calendars/", "")
        path = outdir / f"{slug}-{year}.h"
        if not path.exists():
            print(f"  skip missing {path.name}")
            skipped += 1
            continue
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
        selected = select_codes(votes, schedules)
        spa: list[tuple[int, int, int, int]] = []
        for code in selected:
            spa.extend(dates_for_zone(code, schedules, year))
        spa = sorted({e for e in spa if e[0] == year})
        if len(spa) < 4:
            print(f"  skip {slug}: too few spa days {len(spa)} codes={sorted(selected)}")
            skipped += 1
            continue
        # Guard: near-daily spa usually means bad weekly expansion on multi-code union.
        if len(spa) > 120 and len(selected) > 1:
            # Retry with the single best code.
            best = next(iter(select_codes(votes, schedules)))
            # Prefer the vote leader among selected
            best = max(selected, key=lambda c: (zone_specificity(c, schedules), votes[c]))
            selected = {best}
            spa = sorted({e for e in dates_for_zone(best, schedules, year) if e[0] == year})
        if len(spa) > 120:
            print(
                f"  skip {slug}: spa too dense ({len(spa)}) codes={sorted(selected)} "
                f"votes={dict(votes.most_common(5))}"
            )
            skipped += 1
            continue
        existing = load_entries(path)
        before = sum(1 for e in existing if e[3] == BIN_SPA)
        new_entries = merge_spa(existing, spa)
        after = sum(1 for e in new_entries if e[3] == BIN_SPA)
        print(
            f"  merge {path.name}: matched={matched}/{len(streets)} "
            f"codes={sorted(selected)} votes={dict(votes.most_common(3))} "
            f"spa {before}->{after}"
        )
        if not dry_run:
            write_year_file(
                out_path=path,
                comune_name=comune_name,
                zone_label=zone_label_from_file(path, comune_name, slug),
                provider="Covar14",
                addresses=[],
                year=year,
                entries=new_entries,
            )
        merged += 1
    return merged, skipped


def resolve_comune_tid(
    name: str, options: dict[str, int], aliases: dict[str, str] | None = None
) -> int | None:
    key = name.lower().strip()
    if aliases and key in aliases:
        key = aliases[key]
    if key in options:
        return options[key]
    # fuzzy: strip diacritics-ish
    for k, tid in options.items():
        if k.startswith(key) or key.startswith(k):
            return tid
    return None


def update_sources(
    sources_path: Path,
    comune_ids: list[str],
    dry_run: bool,
) -> None:
    data = json.loads(sources_path.read_text(encoding="utf-8"))
    note = (
        "Spazzamento Covar14 (search-calendario-spazzamento) mergiato come bin "
        "Spazzamento nelle zone esistenti."
    )
    url = SEARCH
    for cid in comune_ids:
        comune = next(c for c in data["comuni"] if c["id"] == cid)
        notes = list(comune.get("notes") or [])
        if note not in notes:
            notes.append(note)
        comune["notes"] = notes
        pdfs = list(comune.get("pdfs") or [])
        if not any(p.get("url") == url and p.get("label", "").startswith("Spazzamento") for p in pdfs):
            pdfs.append({"year": 2026, "label": "Spazzamento (ricerca via)", "url": url})
        comune["pdfs"] = pdfs
    if not dry_run:
        sources_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"sources.json updated for: {', '.join(comune_ids)}")


def covar_comuni_from_sources(sources_path: Path) -> list[dict]:
    data = json.loads(sources_path.read_text(encoding="utf-8"))
    return [c for c in data["comuni"] if c.get("provider") == "Covar14"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--comune", action="append", help="Escilo comune id (repeatable)")
    ap.add_argument("--all", action="store_true", help="All Covar14 comuni")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force-refresh", action="store_true")
    ap.add_argument(
        "--from-summary",
        action="store_true",
        help="Reuse tmp_calendars/covar_spa_cache/<id>/summary.json (no HTTP)",
    )
    ap.add_argument(
        "--cache-dir",
        type=Path,
        default=ROOT / "tmp_calendars" / "covar_spa_cache",
    )
    args = ap.parse_args()

    outdir = ROOT / "docs" / "calendars"
    sources = outdir / "sources.json"
    covar = covar_comuni_from_sources(sources)
    if args.all:
        targets = covar
    elif args.comune:
        wanted = set(args.comune)
        targets = [c for c in covar if c["id"] in wanted]
        missing = wanted - {c["id"] for c in targets}
        if missing:
            print("unknown Covar14 ids:", ", ".join(sorted(missing)))
            return 1
    else:
        targets = [c for c in covar if c["id"] == "candiolo"]

    # Bootstrap options from any comune page (Candiolo=97 known)
    boot = fetch(
        f"{SEARCH}?f%5B0%5D=comune%3A97",
        args.cache_dir / "comune_97.html",
        sleep_s=0.05,
    )
    options = extract_comune_options(boot)
    if not options:
        # Verified against facet HTML on search-calendario-spazzamento (2026).
        options = {
            "beinasco": 12,
            "moncalieri": 92,
            "nichelino": 91,
            "orbassano": 90,
            "carignano": 96,
            "rivalta di torino": 85,
            "villastellone": 83,
            "trofarello": 84,
            "piobesi torinese": 87,
            "la loggia": 94,
            "bruino": 98,
            "vinovo": 82,
            "piossasco": 86,
            "virle piemonte": 81,
            "castagnole piemonte": 95,
            "lombriasco": 93,
            "osasio": 89,
            "pancalieri": 88,
            "candiolo": 97,
        }
        print("warning: facet options empty, using fallback map")
    else:
        print(f"facet comuni: {len(options)}")
        for k, v in sorted(options.items(), key=lambda x: x[1]):
            print(f"  {v}: {k}")

    aliases = {
        "rivalta": "rivalta di torino",
        "castagnole": "castagnole piemonte",
        "virle": "virle piemonte",
        "piobesi": "piobesi torinese",
        "la-loggia": "la loggia",
    }

    done_ids: list[str] = []
    for comune in targets:
        cid = comune["id"]
        name = comune["name"]
        tid = resolve_comune_tid(name, options, aliases)
        if tid is None:
            print(f"SKIP {name}: no taxonomy id")
            continue
        print(f"\n=== {name} (tid={tid}) ===")
        summary_path = args.cache_dir / cid / "summary.json"
        if args.from_summary and summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            schedules = {
                z: [(r["tipo"], r["giorno"], r["orario"]) for r in rules]
                for z, rules in summary["zones"].items()
            }
            street_zones = {
                k: set(v) for k, v in summary["street_zones"].items()
            }
            print(
                f"  from summary zones={len(schedules)} streets={len(street_zones)} "
                f"year={args.year}"
            )
        else:
            schedules, street_zones = scrape_comune(
                tid, args.cache_dir / cid, force=args.force_refresh
            )
            print(
                f"  schedules zones={len(schedules)} streets={len(street_zones)} "
                f"year={args.year}"
            )
            # persist scrape summary
            summary = {
                "comune": name,
                "tid": tid,
                "zones": {
                    z: [{"tipo": a, "giorno": b, "orario": c} for a, b, c in rules]
                    for z, rules in schedules.items()
                },
                "street_zones": {k: sorted(v) for k, v in street_zones.items()},
            }
            out_sum = args.cache_dir / cid / "summary.json"
            out_sum.parent.mkdir(parents=True, exist_ok=True)
            out_sum.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        merged, skipped = merge_comune(
            comune_id=cid,
            comune_name=name,
            year=args.year,
            outdir=outdir,
            schedules=schedules,
            street_zones=street_zones,
            dry_run=args.dry_run,
        )
        print(f"  done merged={merged} skipped={skipped}")
        if merged:
            done_ids.append(cid)

    if done_ids:
        update_sources(sources, done_ids, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
