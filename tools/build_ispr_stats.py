#!/usr/bin/env python3
"""Precompute ISPRA municipal waste KPIs for Escilo (national + geo benchmarks).

Downloads Catasto rifiuti comunale CSV for 2022–2024 (produzione/RD + costi
pro capite), expands ISPRA multi-comune aggregations (`Dato riferito a`),
computes Italy-wide, per-region and per-province percentiles / medians,
ISPRA population peer clusters (quantiles; aggregated comuni use summed
population), matches Escilo comuni, writes static JSON under docs/data/ispr/:

    - directory.json     lightweight picker list (all IT comuni)
    - c/{id}.json        full KPI record per comune
    - comuni-by-id.json  Escilo-matched subset (teaser / smoke compat)
    - baselines-it.json  national baselines (all regions/provinces)

Run yearly when ISPRA publishes a new year:
    py -3 tools/build_ispr_stats.py

Optional: place CSV files in tmp/ispra/ (rd_YYYY.csv, costi_pc_YYYY.csv)
to skip re-download during rebuilds.
"""

from __future__ import annotations

import csv
import io
import json
import statistics
import sys
import unicodedata
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
INDEX_JSON = DOCS / "calendars" / "index.json"
OUT_DIR = DOCS / "data" / "ispr"
CACHE_DIR = ROOT / "tmp" / "ispra"
YEARS = (2022, 2023, 2024)
LATEST_YEAR = YEARS[-1]
TARGET_RD = 65.0
POP_CLUSTER_K = 4
CSV_URL = (
    "https://www.catasto-rifiuti.isprambiente.it/get/getDettaglioComunale.csv.php?&aa={year}"
)
COST_CSV_URL = (
    "https://www.catasto-rifiuti.isprambiente.it/costi/getCostiComunaleproc.csv.php"
    "?costicomuneproc&aa={year}&regid=1&regid2=Italia&reg1=Italia&p=1"
)

# Escilo name → ISPRA Comune (Provincia Torino) when fuzzy match fails.
MANUAL_MAP: dict[str, str] = {
    "moncucco-torinese": "MONCUCCO TORINESE",
    "cirie": "CIRIE'",
    "cuorgne": "CUORGNE'",
    "leini": "LEINI'",
    "sant-ambrogio-di-torino": "SANT'AMBROGIO DI TORINO",
    "sant-antonino-di-susa": "SANT'ANTONINO DI SUSA",
    "san-mauro-torinese": "SAN MAURO TORINESE",
    "riva-presso-chieri": "RIVA PRESSO CHIERI",
    "val-di-chy": "VAL DI CHY",
}


def parse_num(s: object) -> float | None:
    if s is None:
        return None
    text = str(s).strip().replace("%", "").replace(" ", "").replace(".", "").replace(",", ".")
    if text in ("", "-"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def norm_name(s: str) -> str:
    s = (s or "").strip().upper()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    for ch in ("'", "`", "’", "-", ".", " "):
        s = s.replace(ch, "")
    return s


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").strip().lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    out: list[str] = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "'", "`", "’", "."):
            out.append("-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "comune"


def title_comune(s: str) -> str:
    """Display name from ISPRA uppercase labels."""
    small = {"di", "da", "del", "della", "dei", "delle", "degli", "e", "a", "al", "alla", "in", "sul", "sulla"}
    words = (s or "").strip().lower().replace("'", "'").split()
    out: list[str] = []
    for i, w in enumerate(words):
        if "'" in w:
            left, _, right = w.partition("'")
            piece = left + "'" + (right[:1].upper() + right[1:] if right else "")
            out.append(piece[:1].upper() + piece[1:] if i == 0 or left not in small else piece)
        elif i > 0 and w in small:
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:] if w else w)
    return " ".join(out)


def col(row: dict, *names: str) -> str | None:
    for name in names:
        if name in row:
            return row[name]
        for key in row:
            if key and key.strip() == name:
                return row[key]
    for name in names:
        for key in row:
            if key and name in key:
                return row[key]
    return None


def _read_csv_rows(raw: str) -> list[dict]:
    lines = raw.splitlines()
    header_i = next(i for i, line in enumerate(lines) if "IstatComune" in line)
    cleaned = [ln.lstrip("\t") for ln in lines[header_i:]]
    reader = csv.DictReader(io.StringIO("\n".join(cleaned)), delimiter=";")
    return list(reader)


def _fetch_text(url: str, retries: int = 3) -> str:
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=180) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            if "IstatComune" in raw:
                return raw
            last_err = RuntimeError("CSV senza header IstatComune")
        except Exception as exc:  # noqa: BLE001 — retry transient ISPRA failures
            last_err = exc
        if attempt < retries:
            print(f"  retry {attempt}/{retries - 1} …", flush=True)
    raise RuntimeError(f"download fallito: {last_err}") from last_err


def download_year(year: int, retries: int = 3) -> list[dict]:
    cache = CACHE_DIR / f"rd_{year}.csv"
    if cache.is_file() and cache.stat().st_size > 1000:
        print(f"cache RD {year} …", flush=True)
        raw = cache.read_bytes().decode("utf-8", errors="replace")
        if "IstatComune" not in raw:
            raw = cache.read_bytes().decode("latin-1", errors="replace")
        return _read_csv_rows(raw)

    url = CSV_URL.format(year=year)
    print(f"download RD {year} …", flush=True)
    raw = _fetch_text(url, retries=retries)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(raw, encoding="utf-8")
    return _read_csv_rows(raw)


def download_costs_year(year: int, retries: int = 3) -> dict[str, float]:
    """IstatComune → CTOTab (€/abitante·anno). Skip multi-comune aggregations."""
    cache = CACHE_DIR / f"costi_pc_{year}.csv"
    if cache.is_file() and cache.stat().st_size > 1000:
        print(f"cache costi {year} …", flush=True)
        raw = cache.read_bytes().decode("utf-8", errors="replace")
        if "IstatComune" not in raw:
            raw = cache.read_bytes().decode("latin-1", errors="replace")
    else:
        url = COST_CSV_URL.format(year=year)
        print(f"download costi {year} …", flush=True)
        raw = _fetch_text(url, retries=retries)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(raw, encoding="utf-8")

    out: dict[str, float] = {}
    for row in _read_csv_rows(raw):
        istat = (col(row, "IstatComune") or "").strip().lstrip("\t")
        if not istat:
            continue
        ncom = parse_num(col(row, "Numero di comuni"))
        if ncom is not None and ncom > 1:
            continue
        ctot = parse_num(col(row, "CTOTab"))
        if ctot is None:
            continue
        out[istat] = round(ctot, 2)
    return out


def merge_costs(by_istat: dict[str, dict], costs: dict[str, float]) -> None:
    for istat, m in by_istat.items():
        m["costo_tot_ab"] = costs.get(istat)


def parse_dato_riferito(raw: str | None) -> tuple[str, str | None]:
    """Classify ISPRA column F (`Dato riferito a`).

    Returns:
      ("comune", None) | ("agg", name) | ("vedi", name) | ("skip", raw)
    """
    text = (raw or "").strip()
    low = text.lower()
    if low == "comune":
        return "comune", None
    if low.startswith("aggregazione:"):
        return "agg", text.split(":", 1)[1].strip()
    if low.startswith("vedi aggregazione:"):
        return "vedi", text.split(":", 1)[1].strip()
    return "skip", text or None


def row_identity(row: dict) -> dict | None:
    pop = parse_num(col(row, "Popolazione"))
    if not pop or pop <= 0:
        return None
    istat = (col(row, "IstatComune") or "").strip().lstrip("\t")
    comune = (col(row, "Comune") or "").strip()
    if not istat or not comune:
        return None
    return {
        "istat": istat,
        "comune": comune,
        "regione": (col(row, "Regione") or "").strip(),
        "provincia": (col(row, "Provincia") or "").strip(),
        "pop": int(pop),
    }


def row_waste(row: dict) -> dict | None:
    """Waste totals + RD% from an ISPRA row (no per-capita yet)."""
    pct = parse_num(col(row, "Percentuale RD (%)"))
    ru = parse_num(col(row, "Totale RU (t)"))
    rd = parse_num(col(row, "Totale RD (t)"))
    ind = parse_num(col(row, "Indifferenziato (t)"))
    umida = parse_num(col(row, "Frazione umida(1) (t)"))
    verde = parse_num(col(row, "Verde (t)"))
    carta = parse_num(col(row, " Carta e cartone (t)", "Carta e cartone (t)"))
    plast = parse_num(col(row, "Plastica (t)"))
    vetro = parse_num(col(row, "Vetro (t)"))
    if pct is None or ru is None:
        return None

    def share(part: float | None) -> float | None:
        if part is None or not rd:
            return None
        return round(part / rd * 100, 2)

    return {
        "rd_pct": round(pct, 2),
        "ru_t": ru,
        "rd_t": rd,
        "ind_t": ind,
        "mix_rd_pct": {
            "umida": share(umida),
            "carta": share(carta),
            "plastica": share(plast),
            "verde": share(verde),
            "vetro": share(vetro),
        },
    }


def metrics_from_identity_waste(
    identity: dict,
    waste: dict,
    *,
    pop_for_kg: int,
    aggregation: dict | None = None,
) -> dict:
    """Build a comune metric record; kg/ab use `pop_for_kg` (sum for aggregations)."""
    pop_kg = pop_for_kg if pop_for_kg > 0 else identity["pop"]
    ru = waste["ru_t"]
    rd = waste["rd_t"]
    ind = waste["ind_t"]
    out = {
        "istat": identity["istat"],
        "comune": identity["comune"],
        "regione": identity["regione"],
        "provincia": identity["provincia"],
        "pop": identity["pop"],
        "rd_pct": waste["rd_pct"],
        "kg_ru_ab": round(ru * 1000 / pop_kg, 1),
        "kg_ind_ab": round(ind * 1000 / pop_kg, 1) if ind is not None else None,
        "kg_rd_ab": round(rd * 1000 / pop_kg, 1) if rd is not None else None,
        "mix_rd_pct": waste["mix_rd_pct"],
    }
    if aggregation:
        out["aggregation"] = aggregation
    return out


def row_metrics(row: dict) -> dict | None:
    """Standalone Comune row → metrics (own population for kg/ab)."""
    identity = row_identity(row)
    waste = row_waste(row)
    if not identity or not waste:
        return None
    return metrics_from_identity_waste(identity, waste, pop_for_kg=identity["pop"])


def metrics_from_year_rows(rows: list[dict]) -> dict[str, dict]:
    """Parse one ISPRA year CSV into istat → metrics.

    - `Dato riferito a = Comune`: own waste data.
    - `Aggregazione: X` + matching `Vedi aggregazione: X`: shared waste from the
      Aggregazione row; kg/ab and pop-cluster use the summed population of all
      members (including the Aggregazione comune).
    """
    comuni_rows: list[dict] = []
    groups: dict[str, dict] = {}

    for row in rows:
        kind, agg_name = parse_dato_riferito(col(row, "Dato riferito a"))
        if kind == "comune":
            comuni_rows.append(row)
            continue
        if kind not in ("agg", "vedi") or not agg_name:
            continue
        key = norm_name(agg_name)
        g = groups.setdefault(
            key, {"name": agg_name, "agg_row": None, "member_rows": []}
        )
        g["member_rows"].append(row)
        if kind == "agg":
            g["name"] = agg_name
            g["agg_row"] = row

    out: dict[str, dict] = {}
    for row in comuni_rows:
        m = row_metrics(row)
        if m:
            out[m["istat"]] = m

    for key, g in groups.items():
        agg_row = g["agg_row"]
        if not agg_row:
            print(
                f"  WARN aggregazione senza riga dati: {g['name']}",
                flush=True,
            )
            continue
        waste = row_waste(agg_row)
        if not waste:
            print(
                f"  WARN aggregazione senza RD/RU: {g['name']}",
                flush=True,
            )
            continue

        members: list[dict] = []
        for row in g["member_rows"]:
            identity = row_identity(row)
            if identity:
                members.append(identity)
        if not members:
            print(
                f"  WARN aggregazione senza comuni validi: {g['name']}",
                flush=True,
            )
            continue

        # Dedupe by istat (Aggregazione row is also listed as member).
        by_istat_mem: dict[str, dict] = {}
        for identity in members:
            by_istat_mem[identity["istat"]] = identity
        members = list(by_istat_mem.values())
        sum_pop = sum(m["pop"] for m in members)
        aggregation = {
            "name": g["name"],
            "n": len(members),
            "pop": sum_pop,
        }
        for identity in members:
            m = metrics_from_identity_waste(
                identity, waste, pop_for_kg=sum_pop, aggregation=aggregation
            )
            out[m["istat"]] = m

    return out


def stats_units_from_metrics(by_istat: dict[str, dict]) -> list[dict]:
    """One statistical unit per Comune, or per multi-comune aggregation.

    Multi-comune aggregations count once (with summed population) so national
    medians / pop-cluster bands are not skewed by duplicated RD%.
    """
    seen_agg: set[str] = set()
    units: list[dict] = []
    for m in by_istat.values():
        agg = m.get("aggregation")
        if agg and int(agg.get("n") or 0) >= 2:
            key = norm_name(str(agg.get("name") or ""))
            if key in seen_agg:
                continue
            seen_agg.add(key)
            unit = dict(m)
            unit["pop"] = int(agg["pop"])
            units.append(unit)
        else:
            units.append(m)
    return units


def cluster_pop_for(rec: dict) -> int | None:
    """Population used for ISPRA pop-cluster assignment."""
    agg = rec.get("aggregation")
    if agg and agg.get("pop") and int(agg.get("n") or 0) >= 2:
        return int(agg["pop"])
    pop = rec.get("pop")
    return int(pop) if pop is not None else None


def percentile_rank(sorted_vals: list[float], value: float) -> float:
    """% of national values strictly below `value` (0–100)."""
    if not sorted_vals:
        return 0.0
    below = sum(1 for v in sorted_vals if v < value)
    return round(100.0 * below / len(sorted_vals), 1)


def dist_summary(vals: list[float]) -> dict:
    vals = [v for v in vals if v is not None]
    vals_s = sorted(vals)
    n = len(vals_s)
    return {
        "n": n,
        "mean": round(statistics.mean(vals_s), 2),
        "median": round(statistics.median(vals_s), 2),
        "p10": round(vals_s[max(0, int(0.10 * (n - 1)))], 2),
        "p90": round(vals_s[min(n - 1, int(0.90 * (n - 1)))], 2),
    }


def pick_hook(rd: float, rd_pctile: float) -> dict:
    gap = round(rd - TARGET_RD, 1)
    if rd_pctile >= 90:
        return {
            "key": "top_pctile",
            "text": f"Tra i migliori in Italia (meglio del {rd_pctile:.0f}%)",
        }
    if rd < TARGET_RD:
        return {
            "key": "below_target",
            "text": (
                f"A -{abs(gap):.1f} punti percentuali "
                f"dall'obiettivo nazionale del 65%"
            ),
        }
    return {
        "key": "target_met",
        "text": f"Obiettivo 65% raggiunto · {gap:+.1f} punti percentuali",
    }


def match_escilo(
    comuni: list[dict],
    by_year: dict[int, dict[str, dict]],
) -> tuple[dict[str, dict], list[str]]:
    # Index latest-year rows by normalized name (Torino first, then any).
    latest = by_year[LATEST_YEAR]
    by_norm_to: dict[str, dict] = {}
    by_norm_any: dict[str, dict] = {}
    for m in latest.values():
        key = norm_name(m["comune"])
        by_norm_any.setdefault(key, m)
        if m["provincia"] == "Torino":
            by_norm_to.setdefault(key, m)

    out: dict[str, dict] = {}
    missing: list[str] = []

    for c in comuni:
        cid = c["id"]
        name = c["name"]
        hit = None
        if cid in MANUAL_MAP:
            want = norm_name(MANUAL_MAP[cid])
            hit = by_norm_to.get(want) or by_norm_any.get(want)
        if not hit:
            key = norm_name(name)
            hit = by_norm_to.get(key) or by_norm_any.get(key)
        if not hit:
            # Partial: escilo name contained in ISPRA or vice versa (Torino only).
            for k, m in by_norm_to.items():
                if key in k or k in key:
                    hit = m
                    break
        if not hit:
            missing.append(f"{cid} ({name})")
            continue

        istat = hit["istat"]
        series: dict[str, float] = {}
        for y in YEARS:
            ym = by_year[y].get(istat)
            if ym:
                series[str(y)] = ym["rd_pct"]

        latest_m = by_year[LATEST_YEAR][istat]
        # Recompute pctiles against full national distributions (passed later).
        rec = {
            "_istat": istat,
            "id": cid,
            "name": name,
            "isprName": latest_m["comune"],
            "istat": istat,
            "provincia": latest_m["provincia"],
            "regione": latest_m["regione"],
            "pop": latest_m["pop"],
            "year": LATEST_YEAR,
            "rd_pct": latest_m["rd_pct"],
            "kg_ru_ab": latest_m["kg_ru_ab"],
            "kg_ind_ab": latest_m["kg_ind_ab"],
            "costo_tot_ab": latest_m.get("costo_tot_ab"),
            "mix_rd_pct": latest_m["mix_rd_pct"],
            "series_rd": series,
        }
        if latest_m.get("aggregation"):
            rec["aggregation"] = latest_m["aggregation"]
        out[cid] = rec

    return out, missing


def area_baselines(metrics: list[dict], key: str) -> dict[str, dict]:
    """Median RD / kg / costo baselines grouped by `key` (e.g. regione, provincia)."""
    by_area: dict[str, list[dict]] = {}
    for m in metrics:
        name = (m.get(key) or "").strip()
        if not name:
            continue
        by_area.setdefault(name, []).append(m)

    out: dict[str, dict] = {}
    for name, rows in sorted(by_area.items()):
        rd_vals = [r["rd_pct"] for r in rows]
        kg_vals = [r["kg_ru_ab"] for r in rows]
        ind_vals = [r["kg_ind_ab"] for r in rows if r["kg_ind_ab"] is not None]
        cost_vals = [
            r["costo_tot_ab"] for r in rows if r.get("costo_tot_ab") is not None
        ]
        out[name] = {
            "rd_pct_median": dist_summary(rd_vals)["median"],
            "rd_pct_n": len(rd_vals),
            "kg_ru_ab_median": dist_summary(kg_vals)["median"],
            "kg_ind_ab_median": dist_summary(ind_vals)["median"] if ind_vals else None,
            "costo_tot_ab_median": (
                dist_summary(cost_vals)["median"] if cost_vals else None
            ),
            "costo_tot_ab_n": len(cost_vals),
        }
    return out


def region_baselines(metrics: list[dict]) -> dict[str, dict]:
    """Median RD / kg baselines for each Regione present in the latest-year rows."""
    return area_baselines(metrics, "regione")


def province_baselines(metrics: list[dict]) -> dict[str, dict]:
    """Median RD / kg baselines for each Provincia present in the latest-year rows."""
    return area_baselines(metrics, "provincia")


def fmt_pop_bound(n: int) -> str:
    """Short Italian population bound for cluster labels."""
    n = int(n)
    if n < 500:
        return f"{n:,}".replace(",", ".")
    if n < 1000:
        rounded = int(round(n / 50.0) * 50)
        if rounded >= 1000:
            return "1.000"
        return f"{rounded:,}".replace(",", ".")
    if n < 10000:
        # e.g. 1030 → 1.000 ; 2335 → 2.300
        rounded = int(round(n / 100.0) * 100)
        return f"{rounded:,}".replace(",", ".")
    rounded = int(round(n / 1000.0) * 1000)
    return f"{rounded:,}".replace(",", ".")


def quantile_interior_edges(sorted_vals: list[int], k: int) -> list[int]:
    """Return k-1 interior quantile edges (nearest-rank), non-decreasing."""
    if not sorted_vals or k < 2:
        return []
    n = len(sorted_vals)
    edges: list[int] = []
    for i in range(1, k):
        idx = int(round(i * (n - 1) / k))
        edges.append(int(sorted_vals[idx]))
    # Ensure strictly increasing where possible by bumping duplicates.
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = edges[i - 1] + 1
    return edges


def pop_cluster_label(index: int, k: int, lo: int, hi: int | None) -> str:
    if index == 0 and hi is not None:
        return f"fino a ~{fmt_pop_bound(hi)} ab."
    if index == k - 1:
        return f"oltre ~{fmt_pop_bound(lo)} ab."
    if hi is None:
        return f"oltre ~{fmt_pop_bound(lo)} ab."
    return f"~{fmt_pop_bound(lo)}-{fmt_pop_bound(hi)} ab."


def build_pop_clusters(
    italy_metrics: list[dict],
    k: int = POP_CLUSTER_K,
) -> list[dict]:
    """ISPRA-Italy quantile pop bands + RD medians inside each band."""
    pops = sorted(
        int(m["pop"]) for m in italy_metrics if m.get("pop") is not None
    )
    if len(pops) < k:
        return []
    edges = quantile_interior_edges(pops, k)
    if len(edges) != k - 1:
        return []

    clusters: list[dict] = []
    for i in range(k):
        if i == 0:
            lo, hi = 0, edges[0]
            label = pop_cluster_label(i, k, 0, edges[0])
        elif i == k - 1:
            lo, hi = edges[-1] + 1, None
            label = pop_cluster_label(i, k, edges[-1], None)
        else:
            lo, hi = edges[i - 1] + 1, edges[i]
            label = pop_cluster_label(i, k, edges[i - 1], edges[i])
        clusters.append(
            {
                "id": f"p{i}",
                "lo": lo,
                "hi": hi,
                "label": label,
            }
        )

    def cluster_index(pop: int) -> int:
        for i, c in enumerate(clusters):
            hi = c["hi"]
            if hi is None:
                if pop >= c["lo"]:
                    return i
            elif c["lo"] <= pop <= hi:
                return i
        return len(clusters) - 1

    for c in clusters:
        c["_rd"] = []
        c["_cost"] = []

    for m in italy_metrics:
        pop = m.get("pop")
        rd = m.get("rd_pct")
        if pop is None or rd is None:
            continue
        idx = cluster_index(int(pop))
        clusters[idx]["_rd"].append(float(rd))
        cost = m.get("costo_tot_ab")
        if cost is not None:
            clusters[idx]["_cost"].append(float(cost))

    out: list[dict] = []
    for i, c in enumerate(clusters):
        rd_vals = c.pop("_rd")
        cost_vals = c.pop("_cost")
        summary = dist_summary(rd_vals) if rd_vals else {"median": None, "n": 0}
        cost_summary = (
            dist_summary(cost_vals) if cost_vals else {"median": None, "n": 0}
        )
        out.append(
            {
                "id": c["id"],
                "lo": c["lo"],
                "hi": c["hi"],
                "label": c["label"],
                "ordinal": i + 1,
                "rd_pct_median": summary["median"],
                "rd_pct_n": summary["n"],
                "costo_tot_ab_median": cost_summary["median"],
                "costo_tot_ab_n": cost_summary["n"],
            }
        )
    return out


def assign_pop_clusters(records: dict[str, dict], clusters: list[dict]) -> None:
    """Attach pop_cluster_id and vs-median-pop deltas on each record."""
    if not clusters:
        return
    by_id = {c["id"]: c for c in clusters}

    def find_id(pop: int) -> str | None:
        for c in clusters:
            hi = c["hi"]
            if hi is None:
                if pop >= c["lo"]:
                    return c["id"]
            elif c["lo"] <= pop <= hi:
                return c["id"]
        return clusters[-1]["id"]

    for rec in records.values():
        pop = cluster_pop_for(rec)
        if pop is None:
            rec["pop_cluster_id"] = None
            rec["rd_vs_median_pop"] = None
            rec["costo_vs_median_pop"] = None
            continue
        cid = find_id(int(pop))
        rec["pop_cluster_id"] = cid
        peer = by_id.get(cid) or {}
        med = peer.get("rd_pct_median")
        rd = rec.get("rd_pct")
        rec["rd_vs_median_pop"] = (
            round(float(rd) - float(med), 2) if med is not None and rd is not None else None
        )
        cost = rec.get("costo_tot_ab")
        med_cost = peer.get("costo_tot_ab_median")
        rec["costo_vs_median_pop"] = (
            round(float(cost) - float(med_cost), 1)
            if cost is not None and med_cost is not None
            else None
        )


def attach_national_ranks(
    records: dict[str, dict],
    by_year: dict[int, dict[str, dict]],
    sorted_rd: list[float],
    sorted_kg: list[float],
    sorted_ind: list[float],
    baselines: dict,
    by_regione: dict[str, dict],
) -> None:
    med_kg = baselines["years"][str(LATEST_YEAR)]["kg_ru_ab"]["median"]
    med_ind = baselines["years"][str(LATEST_YEAR)]["kg_ind_ab"]["median"]
    med_rd = baselines["years"][str(LATEST_YEAR)]["rd_pct"]["median"]
    cost_block = baselines["years"][str(LATEST_YEAR)].get("costo_tot_ab") or {}
    med_cost = cost_block.get("median")

    for rec in records.values():
        istat = rec.pop("_istat")
        m = by_year[LATEST_YEAR][istat]
        rd = m["rd_pct"]
        kg = m["kg_ru_ab"]
        ind = m["kg_ind_ab"]
        cost = m.get("costo_tot_ab")
        reg = (m.get("regione") or "").strip()
        reg_base = by_regione.get(reg) or {}

        rd_pctile = percentile_rank(sorted_rd, rd)
        kg_pctile = percentile_rank(sorted_kg, kg)
        # Lower indiff is better: "better than X%" = share of comuni with higher indiff.
        if ind is not None:
            worse_or_eq = sum(1 for v in sorted_ind if v > ind)
            ind_better_pctile = round(100.0 * worse_or_eq / len(sorted_ind), 1)
            ind_vs_median = round(ind - med_ind, 1)
        else:
            ind_better_pctile = None
            ind_vs_median = None

        med_kg_reg = reg_base.get("kg_ru_ab_median")
        med_ind_reg = reg_base.get("kg_ind_ab_median")
        med_rd_reg = reg_base.get("rd_pct_median")
        med_cost_reg = reg_base.get("costo_tot_ab_median")

        series = rec["series_rd"]
        delta = None
        if "2022" in series and "2024" in series:
            delta = round(series["2024"] - series["2022"], 2)

        hook = pick_hook(rd, rd_pctile)

        rec.update(
            {
                "rd_pctile_it": rd_pctile,
                "gap_65": round(rd - TARGET_RD, 2),
                "rd_vs_median_it": round(rd - med_rd, 2),
                "rd_vs_median_reg": (
                    round(rd - med_rd_reg, 2) if med_rd_reg is not None else None
                ),
                "kg_ru_pctile_it": kg_pctile,
                "kg_ru_vs_median_it": round(kg - med_kg, 1),
                "kg_ru_vs_median_reg": (
                    round(kg - med_kg_reg, 1) if med_kg_reg is not None else None
                ),
                "kg_ind_better_pctile_it": ind_better_pctile,
                "kg_ind_vs_median_it": ind_vs_median,
                "kg_ind_vs_median_reg": (
                    round(ind - med_ind_reg, 1)
                    if ind is not None and med_ind_reg is not None
                    else None
                ),
                "costo_tot_ab": cost,
                "costo_vs_median_it": (
                    round(float(cost) - float(med_cost), 1)
                    if cost is not None and med_cost is not None
                    else None
                ),
                "costo_vs_median_reg": (
                    round(float(cost) - float(med_cost_reg), 1)
                    if cost is not None and med_cost_reg is not None
                    else None
                ),
                "delta_rd_22_24": delta,
                "hook": hook,
            }
        )


def build_record_for_istat(
    istat: str,
    display_id: str,
    display_name: str,
    by_year: dict[int, dict[str, dict]],
) -> dict | None:
    latest_m = by_year[LATEST_YEAR].get(istat)
    if not latest_m:
        return None
    series: dict[str, float] = {}
    for y in YEARS:
        ym = by_year[y].get(istat)
        if ym:
            series[str(y)] = ym["rd_pct"]
    rec = {
        "_istat": istat,
        "id": display_id,
        "name": display_name,
        "isprName": latest_m["comune"],
        "istat": istat,
        "provincia": latest_m["provincia"],
        "regione": latest_m["regione"],
        "pop": latest_m["pop"],
        "year": LATEST_YEAR,
        "rd_pct": latest_m["rd_pct"],
        "kg_ru_ab": latest_m["kg_ru_ab"],
        "kg_ind_ab": latest_m["kg_ind_ab"],
        "costo_tot_ab": latest_m.get("costo_tot_ab"),
        "mix_rd_pct": latest_m["mix_rd_pct"],
        "series_rd": series,
        "hasCalendar": False,
    }
    if latest_m.get("aggregation"):
        rec["aggregation"] = latest_m["aggregation"]
    return rec


def assign_ids(
    latest_metrics: list[dict],
    escilo_by_istat: dict[str, dict],
) -> dict[str, dict]:
    """Map istat → provisional {id, name, hasCalendar} before full records."""
    used_ids: set[str] = set()
    out: dict[str, dict] = {}

    for istat, ec in escilo_by_istat.items():
        cid = ec["id"]
        used_ids.add(cid)
        out[istat] = {
            "id": cid,
            "name": ec["name"],
            "hasCalendar": True,
        }

    # Group remaining by base slug to detect collisions.
    pending: list[dict] = []
    for m in latest_metrics:
        istat = m["istat"]
        if istat in out:
            continue
        pending.append(m)

    slug_counts: dict[str, int] = {}
    for m in pending:
        base = slugify(m["comune"])
        slug_counts[base] = slug_counts.get(base, 0) + 1

    for m in pending:
        istat = m["istat"]
        base = slugify(m["comune"])
        if slug_counts[base] > 1:
            cid = f"{base}-{slugify(m['provincia'])}"
        else:
            cid = base
        if cid in used_ids:
            cid = f"{cid}-{istat[-4:]}"
        used_ids.add(cid)
        out[istat] = {
            "id": cid,
            "name": title_comune(m["comune"]),
            "hasCalendar": False,
        }
    return out


def main() -> int:
    index = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    comuni = [c for c in (index.get("comuni") or []) if c.get("id") and c.get("name")]
    if not comuni:
        print("no comuni in index.json", file=sys.stderr)
        return 1

    by_year: dict[int, dict[str, dict]] = {}
    baselines_years: dict[str, dict] = {}

    for year in YEARS:
        rows = download_year(year)
        by_istat = metrics_from_year_rows(rows)
        costs = download_costs_year(year)
        merge_costs(by_istat, costs)
        by_year[year] = by_istat
        units = stats_units_from_metrics(by_istat)

        rd_vals = [m["rd_pct"] for m in units]
        kg_vals = [m["kg_ru_ab"] for m in units]
        ind_vals = [m["kg_ind_ab"] for m in units if m["kg_ind_ab"] is not None]
        cost_vals = [
            m["costo_tot_ab"] for m in units if m.get("costo_tot_ab") is not None
        ]
        year_block = {
            "rd_pct": dist_summary(rd_vals),
            "kg_ru_ab": dist_summary(kg_vals),
            "kg_ind_ab": dist_summary(ind_vals),
            "share_ge_65": round(
                100.0 * sum(1 for v in rd_vals if v >= TARGET_RD) / len(rd_vals), 1
            ),
        }
        if cost_vals:
            year_block["costo_tot_ab"] = dist_summary(cost_vals)
        baselines_years[str(year)] = year_block
        agg_n = sum(
            1
            for m in by_istat.values()
            if m.get("aggregation") and int(m["aggregation"].get("n") or 0) >= 2
        )
        print(
            f"  {year}: {len(by_istat)} comuni in app "
            f"({len(units)} unita' statistiche, {agg_n} in aggregazione, "
            f"{len(cost_vals)} con costo)",
            flush=True,
        )

    latest_metrics = list(by_year[LATEST_YEAR].values())
    latest_units = stats_units_from_metrics(by_year[LATEST_YEAR])
    sorted_rd = sorted(m["rd_pct"] for m in latest_units)
    sorted_kg = sorted(m["kg_ru_ab"] for m in latest_units)
    sorted_ind = sorted(
        m["kg_ind_ab"] for m in latest_units if m["kg_ind_ab"] is not None
    )
    by_regione = region_baselines(latest_units)
    by_provincia = province_baselines(latest_units)

    baselines = {
        "generatedAt": date.today().isoformat(),
        "source": "ISPRA Catasto nazionale rifiuti — dettaglio comunale",
        "sourceUrl": "https://www.catasto-rifiuti.isprambiente.it/",
        "costsSourceUrl": (
            "https://www.catasto-rifiuti.isprambiente.it/index.php?pg=downloadcosticomune"
        ),
        "latestYear": LATEST_YEAR,
        "yearsAvailable": list(YEARS),
        "targetRdPct": TARGET_RD,
        "targetNote": (
            "Obiettivo minimo di raccolta differenziata ex art. 205 D.Lgs. 152/2006 "
            "(65% entro il 31/12/2012)."
        ),
        "costNote": (
            "Costo totale di gestione dei servizi di igiene urbana (CTOTab), "
            "euro per abitante anno. Non è la bolletta TARI individuale."
        ),
        "years": baselines_years,
        "by_regione": by_regione,
        "by_provincia": by_provincia,
    }

    escilo_matched, missing = match_escilo(comuni, by_year)
    if missing:
        print("UNMATCHED:", ", ".join(missing), file=sys.stderr)
        return 1

    escilo_by_istat = {rec["_istat"]: {"id": rec["id"], "name": rec["name"]} for rec in escilo_matched.values()}
    id_map = assign_ids(latest_metrics, escilo_by_istat)

    all_records: dict[str, dict] = {}
    for istat, meta in id_map.items():
        # Prefer Escilo stub (keeps Escilo display name) then fill from ISPRA.
        if istat in escilo_by_istat and meta["id"] in escilo_matched:
            rec = escilo_matched[meta["id"]]
            rec["hasCalendar"] = True
        else:
            built = build_record_for_istat(istat, meta["id"], meta["name"], by_year)
            if not built:
                continue
            rec = built
            rec["hasCalendar"] = bool(meta["hasCalendar"])
        all_records[meta["id"]] = rec

    attach_national_ranks(
        all_records, by_year, sorted_rd, sorted_kg, sorted_ind, baselines, by_regione
    )

    pop_clusters = build_pop_clusters(latest_units, POP_CLUSTER_K)
    assign_pop_clusters(all_records, pop_clusters)
    baselines["pop_clusters"] = pop_clusters

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    c_dir = OUT_DIR / "c"
    if c_dir.exists():
        for old in c_dir.glob("*.json"):
            old.unlink()
    else:
        c_dir.mkdir(parents=True, exist_ok=True)

    directory = []
    for cid, rec in sorted(all_records.items(), key=lambda kv: (kv[1]["name"], kv[0])):
        directory.append(
            {
                "id": cid,
                "name": rec["name"],
                "provincia": rec.get("provincia") or "",
                "regione": rec.get("regione") or "",
                "istat": rec.get("istat") or "",
                "hasCalendar": bool(rec.get("hasCalendar")),
            }
        )
        # Per-comune file without hasCalendar (stats payload shape).
        file_rec = {k: v for k, v in rec.items() if k != "hasCalendar"}
        (c_dir / f"{cid}.json").write_text(
            json.dumps(file_rec, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    (OUT_DIR / "directory.json").write_text(
        json.dumps(
            {
                "generatedAt": date.today().isoformat(),
                "latestYear": LATEST_YEAR,
                "count": len(directory),
                "comuni": directory,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )

    (OUT_DIR / "baselines-it.json").write_text(
        json.dumps(baselines, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    escilo = {cid: {k: v for k, v in rec.items() if k != "hasCalendar"} for cid, rec in all_records.items() if rec.get("hasCalendar")}
    latest_cost = baselines_years[str(LATEST_YEAR)].get("costo_tot_ab") or {}
    payload = {
        "generatedAt": date.today().isoformat(),
        "source": baselines["source"],
        "sourceUrl": baselines["sourceUrl"],
        "latestYear": LATEST_YEAR,
        "yearsAvailable": list(YEARS),
        "targetRdPct": TARGET_RD,
        "baselines": {
            "rd_pct_median": baselines_years[str(LATEST_YEAR)]["rd_pct"]["median"],
            "rd_pct_n": baselines_years[str(LATEST_YEAR)]["rd_pct"]["n"],
            "kg_ru_ab_median": baselines_years[str(LATEST_YEAR)]["kg_ru_ab"]["median"],
            "kg_ind_ab_median": baselines_years[str(LATEST_YEAR)]["kg_ind_ab"]["median"],
            "costo_tot_ab_median": latest_cost.get("median"),
            "costo_tot_ab_n": latest_cost.get("n"),
            "by_regione": by_regione,
            "by_provincia": by_provincia,
            "pop_clusters": pop_clusters,
        },
        "comuni": escilo,
    }
    (OUT_DIR / "comuni-by-id.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    cal_n = sum(1 for d in directory if d["hasCalendar"])
    print(
        f"wrote {len(directory)} comuni (calendar={cal_n}) -> {OUT_DIR} "
        f"(directory + c/*.json + comuni-by-id Escilo subset)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
