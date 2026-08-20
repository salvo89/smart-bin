#!/usr/bin/env python3
"""Join ISPRA KPIs with ISTAT boundaries for the drill-down map.

Writes:
    docs/data/map/macro.geojson      Nord / Centro / Sud
    docs/data/map/regioni.geojson    20 regioni
    docs/data/map/province.geojson   107 province
    docs/data/map/comuni/{slug}.json per-region municipalities
    docs/data/map/meta.json

Run after ISPRA rebuild or when boundaries update:
    py -3 tools/build_map_data.py

Optional caches under tmp/geo/ skip re-download.
"""

from __future__ import annotations

import json
import math
import re
import sys
import unicodedata
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISPR_C_DIR = ROOT / "docs" / "data" / "ispr" / "c"
OUT_DIR = ROOT / "docs" / "data" / "map"
CACHE_DIR = ROOT / "tmp" / "geo"

MUNI_URL = (
    "https://raw.githubusercontent.com/guglielmo/geojson-italy/master/"
    "topojson/limits_IT_municipalities.topo.json"
)
REG_URL = (
    "https://raw.githubusercontent.com/guglielmo/geojson-italy/master/"
    "topojson/limits_IT_regions.topo.json"
)
PROV_URL = (
    "https://raw.githubusercontent.com/guglielmo/geojson-italy/master/"
    "topojson/limits_IT_provinces.topo.json"
)
MUNI_CACHE = CACHE_DIR / "limits_IT_municipalities.topo.json"
REG_CACHE = CACHE_DIR / "limits_IT_regions.topo.json"
PROV_CACHE = CACHE_DIR / "limits_IT_provinces.topo.json"

# ISTAT ripartizioni, isole nel Sud.
MACRO_BY_SLUG = {
    "piemonte": "nord",
    "valle-d-aosta": "nord",
    "liguria": "nord",
    "lombardia": "nord",
    "trentino-alto-adige": "nord",
    "veneto": "nord",
    "friuli-venezia-giulia": "nord",
    "emilia-romagna": "nord",
    "toscana": "centro",
    "umbria": "centro",
    "marche": "centro",
    "lazio": "centro",
    "abruzzo": "sud",
    "molise": "sud",
    "campania": "sud",
    "puglia": "sud",
    "basilicata": "sud",
    "calabria": "sud",
    "sicilia": "sud",
    "sardegna": "sud",
}
MACRO_LABEL = {"nord": "Nord", "centro": "Centro", "sud": "Sud"}
MACRO_ORDER = ("nord", "centro", "sud")


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace("/", " ")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if s.startswith("trentino"):
        return "trentino-alto-adige"
    if s.startswith("valle-d-aosta") or s.startswith("valle-daosta"):
        return "valle-d-aosta"
    return s


def topo_istat(props: dict) -> str:
    reg = (props.get("reg_istat_code") or "").strip()
    com = (props.get("com_istat_code") or "").strip()
    return f"{reg}{com}"


def load_ispr_by_istat() -> dict[str, dict]:
    by_istat: dict[str, dict] = {}
    for path in sorted(ISPR_C_DIR.glob("*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        istat = (rec.get("istat") or "").strip()
        if not istat:
            continue
        by_istat[istat] = rec
    return by_istat


def compact_comune(rec: dict | None, fallback_name: str, istat: str, reg_slug: str) -> dict:
    if not rec or rec.get("rd_pct") is None:
        return {"istat": istat, "n": fallback_name, "rs": reg_slug}
    out = {
        "id": rec.get("id"),
        "istat": istat,
        "n": rec.get("name") or fallback_name,
        "reg": rec.get("regione"),
        "rs": reg_slug,
        "prov": rec.get("provincia"),
        "pop": rec.get("pop"),
        "rd": rec.get("rd_pct"),
        "co": rec.get("costo_tot_ab"),
        "kru": rec.get("kg_ru_ab"),
        "kin": rec.get("kg_ind_ab"),
        "drd": rec.get("delta_rd_22_24"),
    }
    return {k: v for k, v in out.items() if v is not None}


def ensure_cached(url: str, dest: Path) -> dict:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not dest.is_file():
        print(f"downloading {url} ...")
        req = urllib.request.Request(url, headers={"User-Agent": "Escilo-build/1.0"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read()
        dest.write_bytes(raw)
        print(f"cached {len(raw) // 1024} KiB -> {dest.relative_to(ROOT)}")
    return json.loads(dest.read_text(encoding="utf-8"))


def _transform_point(topology: dict, x: float, y: float) -> list[float]:
    tr = topology.get("transform")
    if not tr:
        return [x, y]
    scale = tr["scale"]
    translate = tr["translate"]
    return [translate[0] + scale[0] * x, translate[1] + scale[1] * y]


def _decode_arc(topology: dict, index: int) -> list[list[float]]:
    arcs = topology["arcs"]
    arc = arcs[index] if index >= 0 else arcs[~index]
    x = y = 0.0
    coords: list[list[float]] = []
    for dx, dy in arc:
        x += dx
        y += dy
        coords.append(_transform_point(topology, x, y))
    if index < 0:
        coords.reverse()
    return coords


def _ring(topology: dict, arc_ids: list[int]) -> list[list[float]]:
    coords: list[list[float]] = []
    for arc_id in arc_ids:
        arc_coords = _decode_arc(topology, arc_id)
        if coords and coords[-1] == arc_coords[0]:
            coords.extend(arc_coords[1:])
        else:
            coords.extend(arc_coords)
    return coords


def _geometry_to_geojson(topology: dict, geom: dict) -> dict:
    gtype = geom["type"]
    if gtype == "Polygon":
        return {
            "type": "Polygon",
            "coordinates": [_ring(topology, arc_ids) for arc_ids in geom["arcs"]],
        }
    if gtype == "MultiPolygon":
        return {
            "type": "MultiPolygon",
            "coordinates": [
                [_ring(topology, arc_ids) for arc_ids in polygon] for polygon in geom["arcs"]
            ],
        }
    raise ValueError(f"unsupported topo geometry type: {gtype}")


def topo_object_to_feature_collection(topology: dict, obj: dict) -> dict:
    features = []
    for geom in obj.get("geometries") or []:
        features.append(
            {
                "type": "Feature",
                "properties": geom.get("properties") or {},
                "geometry": _geometry_to_geojson(topology, geom),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def round_coords(obj, nd: int = 4):
    if isinstance(obj, list):
        if obj and isinstance(obj[0], (int, float)):
            return [round(float(x), nd) for x in obj]
        return [round_coords(x, nd) for x in obj]
    if isinstance(obj, dict):
        if "coordinates" in obj:
            obj["coordinates"] = round_coords(obj["coordinates"], nd)
        elif "geometry" in obj:
            round_coords(obj["geometry"], nd)
        elif "features" in obj:
            for f in obj["features"]:
                round_coords(f, nd)
    return obj


def as_multipolygon(geom: dict) -> dict:
    if geom["type"] == "Polygon":
        return {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}
    if geom["type"] == "MultiPolygon":
        return geom
    raise ValueError(geom["type"])


def dissolve(features: list[dict]) -> dict:
    """Union region polygons so only the macro outline remains."""
    from shapely.geometry import MultiPolygon, Polygon, mapping, shape
    from shapely.ops import unary_union

    geoms = []
    for f in features:
        g = shape(f["geometry"])
        if g.is_empty:
            continue
        if not g.is_valid:
            g = g.buffer(0)
        geoms.append(g)
    merged = unary_union(geoms)
    if merged.is_empty:
        return {"type": "MultiPolygon", "coordinates": []}
    # Weld slivers between adjacent regions (~300 m).
    merged = merged.buffer(0.003).buffer(-0.003)
    merged = merged.simplify(0.004, preserve_topology=True)
    if merged.geom_type == "Polygon":
        merged = MultiPolygon([merged])
    elif merged.geom_type != "MultiPolygon":
        polys = [g for g in getattr(merged, "geoms", []) if isinstance(g, Polygon)]
        merged = MultiPolygon(polys)
    geo = mapping(merged)
    round_coords(geo, 4)
    return geo


def weighted_mean(rows: list[dict], field: str) -> float | None:
    num = 0.0
    den = 0.0
    for r in rows:
        v = r.get(field)
        pop = r.get("pop") or 0
        if v is None or pop <= 0:
            continue
        num += float(v) * pop
        den += pop
    if den <= 0:
        return None
    return round(num / den, 2)


def aggregate(rows: list[dict]) -> dict:
    pop = sum((r.get("pop") or 0) for r in rows)
    n_rd = sum(1 for r in rows if r.get("rd") is not None)
    out = {
        "pop": pop or None,
        "nc": len(rows),
        "nrd": n_rd,
        "rd": weighted_mean(rows, "rd"),
        "co": weighted_mean(rows, "co"),
        "kru": weighted_mean(rows, "kru"),
        "kin": weighted_mean(rows, "kin"),
        "drd": weighted_mean(rows, "drd"),
    }
    return {k: v for k, v in out.items() if v is not None}


def ring_area_m2(ring: list) -> float:
    """Spherical polygon area (m²) from lon/lat ring — good enough for choropleths."""
    if not ring or len(ring) < 3:
        return 0.0
    area = 0.0
    for i in range(len(ring) - 1):
        lon1 = math.radians(ring[i][0])
        lat1 = math.radians(ring[i][1])
        lon2 = math.radians(ring[i + 1][0])
        lat2 = math.radians(ring[i + 1][1])
        area += (lon2 - lon1) * (2.0 + math.sin(lat1) + math.sin(lat2))
    return abs(area * (6378137.0**2) / 2.0)


def feature_km2(geom: dict | None) -> float:
    if not geom:
        return 0.0
    gtype = geom.get("type")
    coords = geom.get("coordinates") or []
    polys = [coords] if gtype == "Polygon" else coords
    total = 0.0
    for poly in polys:
        if not poly:
            continue
        total += ring_area_m2(poly[0])
        for hole in poly[1:]:
            total -= ring_area_m2(hole)
    return total / 1e6


def attach_density(props: dict, geom: dict | None) -> dict:
    km2 = round(feature_km2(geom), 1)
    if km2 > 0:
        props["km2"] = km2
    pop = props.get("pop")
    if pop and km2 > 0:
        props["dens"] = round(float(pop) / km2, 1)
    return props


def dump_geojson(path: Path, features: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": features},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def main() -> int:
    if not ISPR_C_DIR.is_dir():
        print("missing ISPRA comune dir:", ISPR_C_DIR, file=sys.stderr)
        return 1

    ispr = load_ispr_by_istat()
    if not ispr:
        print("no ISPRA records in", ISPR_C_DIR, file=sys.stderr)
        return 1

    muni_topo = ensure_cached(MUNI_URL, MUNI_CACHE)
    reg_topo = ensure_cached(REG_URL, REG_CACHE)
    prov_topo = ensure_cached(PROV_URL, PROV_CACHE)

    muni_key = "comuni" if "comuni" in muni_topo["objects"] else next(iter(muni_topo["objects"]))
    reg_key = "regions" if "regions" in reg_topo["objects"] else next(iter(reg_topo["objects"]))
    prov_key = "provinces" if "provinces" in prov_topo["objects"] else next(iter(prov_topo["objects"]))

    by_prov_code: dict[str, list[dict]] = {}
    for geom in muni_topo["objects"][muni_key]["geometries"]:
        props = geom.get("properties") or {}
        istat = topo_istat(props)
        rec = ispr.get(istat)
        geo_name = props.get("name") or (rec or {}).get("name") or ""
        ispr_reg = (rec or {}).get("regione") or props.get("reg_name") or ""
        compact = compact_comune(rec, geo_name, istat, slugify(ispr_reg))
        geom["properties"] = compact
        pcode = str(props.get("prov_istat_code") or "").strip()
        if pcode:
            by_prov_code.setdefault(pcode.zfill(3), []).append(compact)

    comuni_fc = topo_object_to_feature_collection(muni_topo, muni_topo["objects"][muni_key])
    round_coords(comuni_fc, 4)

    by_reg: dict[str, list[dict]] = {}
    matched = 0
    with_rd = 0
    for f in comuni_fc["features"]:
        p = f["properties"]
        rs = p.get("rs") or "sconosciuta"
        by_reg.setdefault(rs, []).append(f)
        if p.get("id"):
            matched += 1
        if p.get("rd") is not None:
            with_rd += 1

    all_rows = [f["properties"] for f in comuni_fc["features"]]
    italy = aggregate(all_rows)
    # Italy surface/density filled after macros are dissolved (sum of macro km2).

    reg_fc = topo_object_to_feature_collection(reg_topo, reg_topo["objects"][reg_key])
    round_coords(reg_fc, 4)

    region_features: list[dict] = []
    region_by_slug: dict[str, dict] = {}
    for f in reg_fc["features"]:
        raw_name = f["properties"].get("reg_name") or f["properties"].get("name") or ""
        rs = slugify(raw_name)
        macro = MACRO_BY_SLUG.get(rs)
        if not macro:
            print(f"skip unknown region slug {rs!r} ({raw_name})", file=sys.stderr)
            continue
        rows = [g["properties"] for g in by_reg.get(rs, [])]
        label = MACRO_LABEL[macro]
        # Prefer ISPRA display name when available.
        name = rows[0].get("reg") if rows else raw_name
        props = {
            "id": rs,
            "n": name,
            "macro": macro,
            "mn": label,
            **aggregate(rows),
        }
        attach_density(props, f["geometry"])
        feat = {"type": "Feature", "properties": props, "geometry": f["geometry"]}
        region_features.append(feat)
        region_by_slug[rs] = feat

    prov_fc = topo_object_to_feature_collection(prov_topo, prov_topo["objects"][prov_key])
    round_coords(prov_fc, 4)

    province_features: list[dict] = []
    for f in prov_fc["features"]:
        raw_name = f["properties"].get("prov_name") or f["properties"].get("name") or ""
        pcode = str(f["properties"].get("prov_istat_code") or "").strip().zfill(3)
        rows = by_prov_code.get(pcode) or []
        if not rows:
            print(f"skip unknown province {raw_name!r} ({pcode})", file=sys.stderr)
            continue
        rs = rows[0].get("rs") or slugify(f["properties"].get("reg_name") or "")
        region = region_by_slug.get(rs)
        macro = (region["properties"]["macro"] if region else MACRO_BY_SLUG.get(rs)) or ""
        name = rows[0].get("prov") or raw_name
        rn = (region["properties"]["n"] if region else rows[0].get("reg")) or ""
        props = {
            "id": slugify(name),
            "n": name,
            "rs": rs,
            "rn": rn,
            "macro": macro,
            "mn": MACRO_LABEL.get(macro, ""),
            **aggregate(rows),
        }
        attach_density(props, f["geometry"])
        province_features.append({"type": "Feature", "properties": props, "geometry": f["geometry"]})

    macro_features: list[dict] = []
    for mid in MACRO_ORDER:
        members = [f for f in region_features if f["properties"]["macro"] == mid]
        rows = [g["properties"] for rs, feats in by_reg.items() if MACRO_BY_SLUG.get(rs) == mid for g in feats]
        geom = dissolve(members)
        props = {
            "id": mid,
            "n": MACRO_LABEL[mid],
            "macro": mid,
            **aggregate(rows),
            "nr": len(members),
        }
        attach_density(props, geom)
        macro_features.append({"type": "Feature", "properties": props, "geometry": geom})

    italy_km2 = round(sum((f["properties"].get("km2") or 0) for f in macro_features), 1)
    if italy.get("pop") and italy_km2 > 0:
        italy["km2"] = italy_km2
        italy["dens"] = round(float(italy["pop"]) / italy_km2, 1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    comuni_dir = OUT_DIR / "comuni"
    if comuni_dir.exists():
        for old in comuni_dir.glob("*.json"):
            old.unlink()
    else:
        comuni_dir.mkdir()

    for rs, feats in by_reg.items():
        dump_geojson(comuni_dir / f"{rs}.json", feats)

    dump_geojson(OUT_DIR / "macro.geojson", macro_features)
    dump_geojson(OUT_DIR / "regioni.geojson", region_features)
    dump_geojson(OUT_DIR / "province.geojson", province_features)

    for leftover in ("comuni.geojson", "comuni.topo.json"):
        p = OUT_DIR / leftover
        if p.is_file():
            p.unlink()

    meta = {
        "generatedAt": date.today().isoformat(),
        "sourceBoundaries": "guglielmo/geojson-italy (CC-BY, ISTAT)",
        "sourceKpi": "ISPRA Catasto rifiuti",
        "italy": italy,
        "macros": [
            {k: f["properties"][k] for k in f["properties"] if k != "macro"}
            for f in macro_features
        ],
        "regions": [
            {
                "id": f["properties"]["id"],
                "n": f["properties"]["n"],
                "macro": f["properties"]["macro"],
                "file": f"comuni/{f['properties']['id']}.json",
            }
            for f in region_features
        ],
        "matchedIspr": matched,
        "withRdPct": with_rd,
        "provinceCount": len(province_features),
        "layers": [
            {"key": "rd", "label": "Raccolta differenziata", "unit": "%"},
            {"key": "co", "label": "Costo gestione", "unit": "€/ab·anno"},
            {"key": "kru", "label": "Rifiuto urbano", "unit": "kg/ab·anno"},
            {"key": "kin", "label": "Indifferenziato", "unit": "kg/ab·anno"},
            {"key": "drd", "label": "Andamento rispetto a 3 anni fa", "unit": "%"},
            {
                "key": "pop",
                "label": "Popolazione",
                "unit": "ab/km²",
                "note": "bolle = abitanti, colore = densità",
            },
        ],
    }
    (OUT_DIR / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    macro_kb = (OUT_DIR / "macro.geojson").stat().st_size // 1024
    reg_kb = (OUT_DIR / "regioni.geojson").stat().st_size // 1024
    prov_kb = (OUT_DIR / "province.geojson").stat().st_size // 1024
    print(
        f"wrote macro {macro_kb} KiB, regioni {reg_kb} KiB, province {prov_kb} KiB "
        f"({len(province_features)}), {len(by_reg)} region files, {with_rd} comuni with RD%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
