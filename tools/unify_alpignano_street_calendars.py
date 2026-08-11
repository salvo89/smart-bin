# -*- coding: utf-8 -*-
"""Unify Alpignano street calendars: raccolta (Junker area) + spazzamento CIDIU.

Writes docs/calendars/alpignano-z*-plus-spa-*-YYYY.h and retargets index.json
vie so selecting a street shows one calendar with bins 0–2 and 6.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.covar14_pdf_to_h import write_year_file  # noqa: E402
from tools.merge_cidiu_spazzamento import (  # noqa: E402
    BIN_SPA,
    fold,
    load_entries,
    merge_spa,
    parse_calendar_page,
    parse_street_options,
    resolve_schedule_keys,
    slugify,
)

YEAR = 2026
OUTDIR = ROOT / "docs" / "calendars"
CACHE = ROOT / "tmp_calendars" / "cidiu_spa"
JUNKER_CACHE = ROOT / "tmp_calendars" / "junker_alpignano.html"

AREA_TO_RACCOLTA = {
    68893: "calendars/alpignano-znord",
    68894: "calendars/alpignano-zsudsopraferrovia",  # Junker "Zona Sud"
    68903: "calendars/alpignano-zsudsottoferrovia",
}

ZONE_LABEL = {
    "calendars/alpignano-znord": "Zona Nord",
    "calendars/alpignano-zsudsopraferrovia": "Zona Sud (sopra ferrovia)",
    "calendars/alpignano-zsudsottoferrovia": "Zona Sud (sotto ferrovia)",
}


def normalize_street(s: str) -> str:
    s = fold(s)
    s = s.replace("I°", "1").replace("1°", "1")
    s = re.sub(r"^IA\s+", "VIA ", s)  # Junker typo
    s = re.sub(r"\bDA CIVICO\b.*$", "", s)
    s = re.sub(r"\bTRATTO\b.*$", "", s)
    s = re.sub(r"\s+\d+\s*$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def street_tokens(s: str) -> set[str]:
    stop = {
        "VIA",
        "VIALE",
        "CORSO",
        "PIAZZA",
        "PIAZZALE",
        "STRADA",
        "DI",
        "DEL",
        "DELLA",
        "DEI",
        "E",
        "DA",
        "A",
        "AL",
        "LA",
        "IL",
        "PER",
        "CIVICO",
    }
    return {t for t in normalize_street(s).split() if t not in stop and len(t) > 1}


def best_junker_match(cidiu_street: str, junker_rows: list[dict]) -> dict | None:
    ns = normalize_street(cidiu_street)
    for j in junker_rows:
        jn = normalize_street(j["NOME"])
        if ns == jn or ns in jn or jn in ns:
            return j
    ta = street_tokens(cidiu_street)
    best = None
    best_score = 0
    for j in junker_rows:
        tb = street_tokens(j["NOME"])
        inter = ta & tb
        if not inter:
            continue
        score = len(inter) * 10 + (5 if any(len(x) >= 5 for x in inter) else 0)
        if fold(cidiu_street).split()[:1] == fold(j["NOME"]).split()[:1]:
            score += 3
        if score > best_score:
            best_score = score
            best = j
    return best if best_score >= 10 else None


def spa_side(zona: str) -> str | None:
    pf = fold(zona)
    if "NORD" in pf:
        return "NORD"
    if "SUD" in pf:
        return "SUD"
    return None


def main() -> int:
    junker = json.loads(
        re.search(
            r"var zone = (\[.*?\]);",
            JUNKER_CACHE.read_text(encoding="utf-8"),
            flags=re.S,
        ).group(1)
    )
    page = (CACHE / "alpignano.html").read_text(encoding="utf-8")
    cal = (CACHE / "cal_alpignano.html").read_text(encoding="utf-8")
    schedules = parse_calendar_page(cal, YEAR)
    streets = parse_street_options(page)

    # Aggregate CIDIU rows by street display name
    by_street: dict[str, dict] = {}
    stats: Counter[str] = Counter()

    for row in streets:
        street = row["street"]
        keys = resolve_schedule_keys(
            "alpignano", row["zona"], row.get("settimana"), schedules
        )
        if not keys:
            stats["no_spa"] += 1
            continue
        spa_entries = [d for k in keys for d in schedules[k]]
        side = spa_side(row["zona"])
        j = best_junker_match(street, junker)
        if j:
            racc = AREA_TO_RACCOLTA.get(j["areaId"])
            stats["junker_hit"] += 1
        else:
            racc = None
            stats["junker_miss"] += 1

        if side == "NORD":
            racc = "calendars/alpignano-znord"
        elif side == "SUD":
            if racc not in (
                "calendars/alpignano-zsudsopraferrovia",
                "calendars/alpignano-zsudsottoferrovia",
            ):
                racc = "calendars/alpignano-zsudsopraferrovia"
                stats["sud_default_sopra"] += 1

        if not racc:
            stats["no_racc"] += 1
            continue

        slot = by_street.setdefault(
            street, {"racc": racc, "spa": [], "spa_keys": set(), "sides": set()}
        )
        # Prefer more specific Sud mapping if we later get sotto
        if (
            slot["racc"] == "calendars/alpignano-zsudsopraferrovia"
            and racc == "calendars/alpignano-zsudsottoferrovia"
        ):
            slot["racc"] = racc
        slot["spa"].extend(spa_entries)
        slot["spa_keys"].update(keys)
        if side:
            slot["sides"].add(side)

    composite_cache: dict[tuple[str, str], str] = {}
    street_out: dict[str, str] = {}

    for street, info in sorted(by_street.items(), key=lambda x: x[0].lower()):
        racc = info["racc"]
        spa_entries = sorted(set(info["spa"]))
        keys_sorted = sorted(info["spa_keys"])
        spa_slug = slugify("+".join(keys_sorted)) if len(keys_sorted) > 1 else slugify(
            keys_sorted[0]
        )
        spa_path = f"calendars/alpignano-spa-{spa_slug}"
        cache_key = (racc, spa_path, tuple(spa_entries))
        # simplify cache key to racc+spa_slug of actual entries
        cache_key2 = (racc, spa_slug, len(spa_entries), spa_entries[0], spa_entries[-1])
        if cache_key2 not in composite_cache:
            racc_slug = racc.replace("calendars/", "")
            out_base = f"calendars/{racc_slug}-plus-spa-{spa_slug}"
            hpath = OUTDIR / f"{racc_slug}-plus-spa-{spa_slug}-{YEAR}.h"
            existing = load_entries(OUTDIR / f"{racc_slug}-{YEAR}.h")
            merged = merge_spa(existing, spa_entries)
            write_year_file(
                out_path=hpath,
                comune_name="Alpignano",
                zone_label=f"{ZONE_LABEL[racc]} + Spazzamento",
                provider="CIDIU",
                addresses=[],
                year=YEAR,
                entries=merged,
            )
            spa_n = sum(1 for e in merged if e[3] == BIN_SPA)
            print(f"write {hpath.name} total={len(merged)} spa={spa_n}")
            composite_cache[cache_key2] = out_base
        street_out[street] = composite_cache[cache_key2]
        stats["mapped"] += 1

    index_path = OUTDIR / "index.json"
    data = json.loads(index_path.read_text(encoding="utf-8"))
    comune = next(c for c in data["comuni"] if c["id"] == "alpignano")
    comune["vie"] = [
        {"name": "Zona Nord", "calendar": "calendars/alpignano-znord"},
        {
            "name": "Zona Sud (sopra ferrovia)",
            "calendar": "calendars/alpignano-zsudsopraferrovia",
        },
        {
            "name": "Zona Sud (sotto ferrovia)",
            "calendar": "calendars/alpignano-zsudsottoferrovia",
        },
    ] + [
        {"name": name, "calendar": cal}
        for name, cal in sorted(street_out.items(), key=lambda x: x[0].lower())
    ]
    index_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    sources_path = OUTDIR / "sources.json"
    sources = json.loads(sources_path.read_text(encoding="utf-8"))
    sc = next(c for c in sources["comuni"] if c["id"] == "alpignano")
    note = (
        "Vie unificate: raccolta porta a porta (Junker areaId→zona) + spazzamento "
        "meccanizzato CIDIU nella stessa selezione via (calendari *-plus-spa-*)."
    )
    notes = list(sc.get("notes") or [])
    if note not in notes:
        notes.append(note)
    sc["notes"] = notes
    sources_path.write_text(
        json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # lite sources if present
    lite_path = OUTDIR / "sources-lite.json"
    if lite_path.exists():
        lite = json.loads(lite_path.read_text(encoding="utf-8"))
        for c in lite.get("comuni") or []:
            if c.get("id") == "alpignano":
                break

    print("STATS", dict(stats))
    print("composites", len(composite_cache), "streets", len(street_out))
    miss_streets = [
        row["street"]
        for row in streets
        if row["street"] not in street_out
        and resolve_schedule_keys(
            "alpignano", row["zona"], row.get("settimana"), schedules
        )
    ]
    print("unmapped unique", sorted(set(miss_streets))[:30])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
