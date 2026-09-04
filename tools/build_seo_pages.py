"""Generate SEO landing pages, sitemap, robots.txt and llms.txt.

Hub /comuni/ → regioni → province → comune.
Calendar comuni keep /comuni/{id}.html; other Italian comuni get ISPRA landings.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
INDEX_JSON = DOCS / "calendars" / "index.json"
SOURCES_LITE = DOCS / "calendars" / "sources-lite.json"
ISPR_DIR = DOCS / "data" / "ispr"
DIRECTORY_JSON = ISPR_DIR / "directory.json"
ISPR_C_DIR = ISPR_DIR / "c"
COMUNI_DIR = DOCS / "comuni"
REGIONI_DIR = COMUNI_DIR / "regioni"
PROVINCE_DIR = COMUNI_DIR / "province"
SITE = "https://escilo.it"
CONTACT_EMAIL = "salvatore.bonventre.ai@gmail.com"
CHROME_CSS_VER = "31"
SEO_CSS_VER = "27"
NAV_JS_VER = "4"

COVER_TONES = 6
SEARCH_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">'
    '<circle cx="11" cy="11" r="7"/>'
    '<path d="M20 20l-3.2-3.2" stroke-linecap="round"/>'
    "</svg>"
)


def esc(s: object) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace("/", " ")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if s.startswith("trentino"):
        return "trentino-alto-adige"
    if s.startswith("valle-d-aosta") or s.startswith("valle-daosta"):
        return "valle-d-aosta"
    return s or "na"


def it_key(s: object) -> str:
    return str(s or "").casefold()


def it_count(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def letter_of(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    for ch in s:
        if ch.isalpha():
            return ch.upper()
    return "#"


def cal_badge_html() -> str:
    return '<span class="badge">Calendario Escilo</span>'


def comuni_search_html(*, directory: str, comune_base: str, input_id: str = "qComune") -> str:
    return f"""    <form class="comuni-search" role="search" data-comuni-search data-directory="{esc(directory)}" data-comune-base="{esc(comune_base)}">
      <label class="visually-hidden" for="{esc(input_id)}">Cerca un comune</label>
      <div class="search-pill">
        {SEARCH_ICON}
        <input id="{esc(input_id)}" type="search" data-comuni-q placeholder="Cerca un comune…" autocomplete="off" spellcheck="false" />
      </div>
      <ul class="geo-results" data-comuni-results hidden></ul>
    </form>
"""


def cover_item_html(
    *,
    href: str,
    name: str,
    meta: str,
    tone: int = 0,
) -> str:
    return (
        "<li>"
        f'<a class="cover tone-{tone % COVER_TONES}" href="{esc(href)}">'
        f'<span class="cover-name">{esc(name)}</span>'
        f'<span class="cover-meta">{esc(meta)}</span>'
        "</a></li>"
    )


def fmt_pct(val: object) -> str:
    if val is None:
        return ""
    try:
        n = float(val)
    except (TypeError, ValueError):
        return ""
    if n != n:
        return ""
    return f"{n:.1f}".replace(".", ",") + "%"


def fmt_num(val: object, digits: int = 1) -> str:
    if val is None:
        return ""
    try:
        n = float(val)
    except (TypeError, ValueError):
        return ""
    if n != n:
        return ""
    txt = f"{n:.{digits}f}".replace(".", ",")
    if digits == 0:
        txt = f"{int(round(n)):,}".replace(",", ".")
    return txt


def propose_mailto(name: str) -> str:
    subj = quote(f"Escilo — proponi calendario {name}")
    return f"mailto:{CONTACT_EMAIL}?subject={subj}"


def load_sources_map() -> dict[str, dict]:
    if not SOURCES_LITE.exists():
        return {}
    data = json.loads(SOURCES_LITE.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for c in data.get("comuni") or []:
        cid = c.get("id")
        if cid:
            out[cid] = c
    return out


def load_calendar_map() -> dict[str, dict]:
    index = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for c in index.get("comuni") or []:
        cid = c.get("id")
        if cid and c.get("name"):
            out[cid] = c
    return out


def load_ispr(cid: str) -> dict | None:
    path = ISPR_C_DIR / f"{cid}.json"
    if not path.exists():
        return None
    rec = json.loads(path.read_text(encoding="utf-8"))
    return rec if isinstance(rec, dict) else None


def asset_prefix(depth: int) -> str:
    return "../" * depth


def page_shell(
    *,
    title: str,
    description: str,
    canonical: str,
    body: str,
    depth: int = 1,
    json_ld: dict | list | None = None,
    extra_js: bool = False,
    block_motion: str = "scale-fade",
    geo_covers: bool = False,
) -> str:
    prefix = asset_prefix(depth)
    ld = ""
    if json_ld is not None:
        ld = (
            '<script type="application/ld+json">\n'
            + json.dumps(json_ld, ensure_ascii=False, separators=(",", ":"))
            + "\n</script>\n"
        )
    js = ""
    if extra_js:
        js = (
            f'  <script type="module" src="{esc(prefix)}assets/js/comuni-nav.js?v={NAV_JS_VER}"></script>\n'
        )
    theme = (
        '  <meta name="theme-color" content="#1f5c42" media="(prefers-color-scheme: light)" />\n'
        '  <meta name="theme-color" content="#0f1612" media="(prefers-color-scheme: dark)" />\n'
    )
    body_cls = ' class="geo-covers"' if geo_covers else ""
    body_open = f'<body{body_cls} data-block-motion="{esc(block_motion)}">'
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=AW-18430762374"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());

    gtag('config', 'AW-18430762374');
  </script>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
{theme}  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}" />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="{esc(canonical)}" />
  <meta property="og:type" content="website" />
  <meta property="og:locale" content="it_IT" />
  <meta property="og:site_name" content="Escilo" />
  <meta property="og:title" content="{esc(title)}" />
  <meta property="og:description" content="{esc(description)}" />
  <meta property="og:url" content="{esc(canonical)}" />
  <meta property="og:image" content="{SITE}/icon-512.png" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="{esc(title)}" />
  <meta name="twitter:description" content="{esc(description)}" />
  <meta name="twitter:image" content="{SITE}/icon-512.png" />
  <link rel="icon" type="image/png" sizes="192x192" href="{esc(prefix)}icon-192.png" />
  <link rel="apple-touch-icon" sizes="512x512" href="{esc(prefix)}icon-512.png" />
  <link rel="stylesheet" href="{esc(prefix)}assets/css/tokens.css" />
  <link rel="stylesheet" href="{esc(prefix)}assets/css/chrome.css?v={CHROME_CSS_VER}" />
  <link rel="stylesheet" href="{esc(prefix)}assets/css/seo.css?v={SEO_CSS_VER}" />
  {ld}{js}</head>
{body_open}
{body}
</body>
</html>
"""


def footer_html(links: list[tuple[str, str]]) -> str:
    chunks: list[str] = []
    for i, (href, label) in enumerate(links):
        if i:
            chunks.append('<span class="sep">&middot;</span>')
        chunks.append(f'<a href="{esc(href)}">{esc(label)}</a>')
    return "    <p class=\"footer\">\n      " + "\n      ".join(chunks) + "\n    </p>"


def crumbs_html(items: list[tuple[str | None, str]]) -> str:
    parts: list[str] = []
    for i, (href, label) in enumerate(items):
        if i:
            parts.append('<span class="sep">/</span>')
        if href:
            parts.append(f'<a href="{esc(href)}">{esc(label)}</a>')
        else:
            parts.append(f"<span>{esc(label)}</span>")
    return '    <nav class="crumbs" aria-label="Percorso">' + "".join(parts) + "</nav>"


def breadcrumb_ld(items: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": name,
                "item": url,
            }
            for i, (url, name) in enumerate(items)
        ],
    }


def webpage_ld(*, title: str, canonical: str, description: str, name: str, regione: str) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": title,
        "url": canonical,
        "description": description,
        "inLanguage": "it-IT",
        "isPartOf": {"@type": "WebSite", "name": "Escilo", "url": f"{SITE}/"},
        "about": {
            "@type": "Place",
            "name": name,
            "address": {
                "@type": "PostalAddress",
                "addressLocality": name,
                "addressRegion": regione or "",
                "addressCountry": "IT",
            },
        },
    }


def ispr_kpis(rec: dict | None) -> list[tuple[str, str]]:
    if not rec:
        return []
    cells: list[tuple[str, str]] = []
    rd = fmt_pct(rec.get("rd_pct"))
    if rd:
        cells.append((rd, f"Differenziata {rec.get('year') or ''}".strip()))
    kg = fmt_num(rec.get("kg_ru_ab"), 1)
    if kg:
        cells.append((kg, "kg/ab rifiuti urbani"))
    kind = fmt_num(rec.get("kg_ind_ab"), 1)
    if kind:
        cells.append((kind, "kg/ab indifferenziato"))
    cost = fmt_num(rec.get("costo_tot_ab"), 2)
    if cost:
        cells.append((cost + " €", "costo/ab all'anno"))
    return cells


def ispr_card_html(rec: dict | None, *, name: str, cid: str, primary_cta: bool = False) -> str:
    if not rec or rec.get("rd_pct") is None:
        return ""
    kpis = ispr_kpis(rec)
    cells = "\n".join(
        f'<div class="kpi-cell"><div class="val">{esc(val)}</div>'
        f'<div class="lbl">{esc(lbl)}</div></div>'
        for val, lbl in kpis
    )
    year = rec.get("year") or "2024"
    stats_url = f"../stats.html?comune={quote(cid)}"
    cta_cls = "cta" if primary_cta else "cta secondary"
    return f"""    <div class="card">
      <h2 class="box-title">Raccolta differenziata {esc(year)}</h2>
      <div class="kpi-grid">
{cells}
      </div>
      <a class="{cta_cls}" href="{esc(stats_url)}">Vedi i dati completi di {esc(name)}</a>
    </div>"""


def comune_list_html(comuni: list[dict], *, href_fn) -> str:
    grouped: dict[str, list[dict]] = {}
    for c in sorted(comuni, key=lambda x: it_key(x["name"])):
        grouped.setdefault(letter_of(c["name"]), []).append(c)
    chunks: list[str] = []
    for letter, items in grouped.items():
        chunks.append('<section class="geo-group">')
        chunks.append(f'<div class="geo-letter" aria-hidden="true">{esc(letter)}</div>')
        chunks.append('<ul class="geo-comuni">')
        for c in items:
            badge = f" {cal_badge_html()}" if c.get("hasCalendar") else ""
            mark = letter_of(c["name"])
            chunks.append(
                "<li>"
                f'<a class="geo-row" href="{esc(href_fn(c))}">'
                f'<span class="geo-mark">{esc(mark)}</span>'
                f'<span class="geo-name">{esc(c["name"])}</span>'
                f"{badge}"
                "</a></li>"
            )
        chunks.append("</ul>")
        chunks.append("</section>")
    return "\n".join(chunks)


def write_comune_page(row: dict, cal: dict | None, source: dict | None, rec: dict | None) -> None:
    cid = row["id"]
    name = (cal or {}).get("name") or row["name"]
    regione = rec.get("regione") if rec else row.get("regione") or ""
    provincia = rec.get("provincia") if rec else row.get("provincia") or ""
    r_slug = slugify(regione)
    p_slug = slugify(provincia)
    has_cal = cal is not None
    canonical = f"{SITE}/comuni/{cid}.html"
    app_url = f"../?comune={quote(cid)}"
    crumbs = crumbs_html(
        [
            ("./", "Comuni"),
            (f"regioni/{r_slug}.html", regione or "Regione"),
            (f"province/{p_slug}.html", provincia or "Provincia"),
            (None, name),
        ]
    )
    crumbs_ld = breadcrumb_ld(
        [
            (f"{SITE}/", "Home"),
            (f"{SITE}/comuni/", "Comuni"),
            (f"{SITE}/comuni/regioni/{r_slug}.html", regione or "Regione"),
            (f"{SITE}/comuni/province/{p_slug}.html", provincia or "Provincia"),
            (canonical, name),
        ]
    )

    if has_cal and cal:
        provider = (source or {}).get("provider") or ""
        source_page = (source or {}).get("sourcePage") or ""
        rd = fmt_pct((rec or {}).get("rd_pct"))
        year = (rec or {}).get("year") or ""
        extra_desc = f" Differenziata {rd} nel {year} (ISPRA)." if rd else ""
        title = f"Calendario raccolta differenziata {name} — Escilo"
        description = (
            f"Calendario ritiri rifiuti a {name} ({provincia}): "
            f"scopri cosa esporre domani per zona con Escilo.{extra_desc}"
        )
        fonte_html = ""
        if provider or source_page:
            label = esc(provider or "—")
            if source_page:
                name_html = (
                    f'<a class="ext-link" href="{esc(source_page)}" target="_blank" rel="noopener noreferrer">'
                    f"<strong>{label}</strong>"
                    f'<span class="visually-hidden"> (si apre in una nuova scheda)</span></a>'
                )
            else:
                name_html = f"<strong>{label}</strong>"
            fonte_html = (
                f'<p class="note">Gestore: {name_html}. '
                f"Escilo non è affiliato al gestore.</p>"
            )
        json_ld = [
            webpage_ld(
                title=title,
                canonical=canonical,
                description=description,
                name=name,
                regione=regione,
            ),
            crumbs_ld,
        ]
        stats_card = ispr_card_html(rec, name=name, cid=cid)
        body = f"""  <div class="page">
    <header class="topbar">
      <a class="back" href="province/{esc(p_slug)}.html">← {esc(provincia or "Comuni")}</a>
    </header>
{crumbs}
    <section class="intro">
      <h1>Calendario raccolta differenziata — {esc(name)}</h1>
      <p>
        Ritiri rifiuti a {esc(name)} ({esc(provincia)}): carta, organico,
        indifferenziata, plastica, verde e vetro. Escilo ti ricorda cosa esporre domani.
      </p>
    </section>
    <div class="card">
      <h2 class="box-title">Calendario</h2>
      <a class="cta" href="{esc(app_url)}">Apri il calendario di {esc(name)}</a>
    </div>
{stats_card}
    {fonte_html}
{footer_html([("../", "Home"), ("./", "Comuni"), ("../fonti.html", "Fonti"), ("../privacy.html", "Privacy")])}
  </div>"""
    else:
        rd = fmt_pct((rec or {}).get("rd_pct"))
        year = (rec or {}).get("year") or "2024"
        title = (
            f"Raccolta differenziata {name} {year}: {rd} — Escilo"
            if rd
            else f"Raccolta differenziata a {name} — Escilo"
        )
        where_parts = []
        if provincia and it_key(provincia) != it_key(name):
            where_parts.append(provincia)
        if regione and it_key(regione) != it_key(provincia):
            where_parts.append(regione)
        where = ", ".join(where_parts)
        description = (
            f"Nel {year} a {name} la differenziata è al {rd}. "
            f"Confronto con Italia e {regione}, kg per abitante e costi di gestione. Statistiche sulla differenziata su Escilo."
            if rd
            else f"Statistiche sulla raccolta differenziata a {name} ({where}) su Escilo."
        )
        json_ld = [
            webpage_ld(
                title=title,
                canonical=canonical,
                description=description,
                name=name,
                regione=regione,
            ),
            crumbs_ld,
        ]
        lead_bits = []
        if rd:
            lead_bits.append(
                f"Nel {year} a {esc(name)} la raccolta differenziata è stata del {esc(rd)}."
            )
        else:
            lead_bits.append(
                f"Le statistiche sulla differenziata per {esc(name)} non sono disponibili in Escilo."
            )
        intro_p = "</p>\n      <p>".join(lead_bits)
        stats_card = ispr_card_html(rec, name=name, cid=cid, primary_cta=True)
        if not stats_card:
            stats_card = f"""    <div class="card">
      <h2 class="box-title">Statistiche</h2>
      <p>Apri Escilo per vedere se le statistiche sulla differenziata sono disponibili per {esc(name)}.</p>
      <a class="cta" href="{esc(app_url)}">Apri {esc(name)} su Escilo</a>
    </div>"""
        body = f"""  <div class="page">
    <header class="topbar">
      <a class="back" href="province/{esc(p_slug)}.html">← {esc(provincia or "Comuni")}</a>
    </header>
{crumbs}
    <section class="intro">
      <h1>Raccolta differenziata a {esc(name)}</h1>
      <p>{intro_p}</p>
    </section>
{stats_card}
    <p class="note">
      Per {esc(name)} non abbiamo ancora il calendario porta a porta.
      Puoi comunque consultare le statistiche sulla differenziata
      (fonte: Catasto rifiuti ISPRA).
      <a href="{esc(propose_mailto(name))}">Proponi il calendario</a>.
    </p>
{footer_html([("../", "Home"), ("./", "Comuni"), ("../fonti.html", "Fonti"), ("../privacy.html", "Privacy")])}
  </div>"""

    (COMUNI_DIR / f"{cid}.html").write_text(
        page_shell(
            title=title,
            description=description,
            canonical=canonical,
            body=body,
            depth=1,
            json_ld=json_ld,
        ),
        encoding="utf-8",
    )


def write_hub(directory: list[dict], regions: dict[str, dict]) -> None:
    n = len(directory)
    n_cal = sum(1 for c in directory if c.get("hasCalendar"))
    title = "Comuni italiani — calendari e differenziata — Escilo"
    description = (
        f"{n} comuni italiani su Escilo: calendario porta a porta in provincia di Torino "
        f"({n_cal} comuni) e statistiche sulla raccolta differenziata ovunque."
    )
    canonical = f"{SITE}/comuni/"
    region_items = []
    ordered = sorted(regions, key=it_key)
    for i, rname in enumerate(ordered):
        block = regions[rname]
        n_c = sum(len(p["comuni"]) for p in block["provinces"].values())
        n_p = len(block["provinces"])
        n_cal_r = sum(
            1 for p in block["provinces"].values() for c in p["comuni"] if c.get("hasCalendar")
        )
        meta = f"{it_count(n_c, 'comune', 'comuni')} · {it_count(n_p, 'provincia', 'province')}"
        if n_cal_r:
            meta += f" · {it_count(n_cal_r, 'calendario Escilo', 'calendari Escilo')}"
        region_items.append(
            cover_item_html(
                href=f"regioni/{block['slug']}.html",
                name=rname,
                meta=meta,
                tone=i,
            )
        )
    json_ld = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": title,
        "url": canonical,
        "description": description,
        "inLanguage": "it-IT",
        "isPartOf": {"@type": "WebSite", "name": "Escilo", "url": f"{SITE}/"},
        "numberOfItems": n,
    }
    body = f"""  <div class="page">
    <header class="topbar">
      <a class="back" href="../">← Home</a>
    </header>
    <p class="geo-kicker">Italia</p>
    <h1 class="geo-title">Comuni italiani</h1>
    <p class="geo-lead">
      {n} comuni: calendario porta a porta in provincia di Torino
      ({n_cal} comuni) e statistiche sulla differenziata in tutta Italia.
    </p>
{comuni_search_html(directory="../data/ispr/directory.json", comune_base="")}    <div data-comuni-browse>
      <ul class="cover-list">
{chr(10).join(region_items)}
      </ul>
    </div>
{footer_html([("../", "Home"), ("../fonti.html", "Fonti"), ("../privacy.html", "Privacy")])}
  </div>"""
    (COMUNI_DIR / "index.html").write_text(
        page_shell(
            title=title,
            description=description,
            canonical=canonical,
            body=body,
            depth=1,
            json_ld=json_ld,
            extra_js=True,
            geo_covers=True,
        ),
        encoding="utf-8",
    )


def write_region_page(rname: str, block: dict) -> None:
    slug = block["slug"]
    provinces = block["provinces"]
    n_c = sum(len(p["comuni"]) for p in provinces.values())
    n_cal = sum(1 for p in provinces.values() for c in p["comuni"] if c.get("hasCalendar"))
    title = f"Differenziata in {rname} — comuni e statistiche — Escilo"
    description = (
        f"{n_c} comuni in {rname}: statistiche sulla raccolta differenziata"
        + (f" e calendario Escilo in {n_cal} comuni." if n_cal else ".")
    )
    canonical = f"{SITE}/comuni/regioni/{slug}.html"
    prov_items = []
    for i, pname in enumerate(sorted(provinces, key=it_key)):
        p = provinces[pname]
        n = len(p["comuni"])
        n_pcal = sum(1 for c in p["comuni"] if c.get("hasCalendar"))
        meta = it_count(n, "comune", "comuni")
        if n_pcal:
            meta += f" · {it_count(n_pcal, 'calendario Escilo', 'calendari Escilo')}"
        prov_items.append(
            cover_item_html(
                href=f"../province/{p['slug']}.html",
                name=pname,
                meta=meta,
                tone=i,
            )
        )
    json_ld = [
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": title,
            "url": canonical,
            "description": description,
            "inLanguage": "it-IT",
            "numberOfItems": n_c,
            "isPartOf": {"@type": "WebSite", "name": "Escilo", "url": f"{SITE}/"},
        },
        breadcrumb_ld(
            [
                (f"{SITE}/", "Home"),
                (f"{SITE}/comuni/", "Comuni"),
                (canonical, rname),
            ]
        ),
    ]
    cal_note = f" Di questi, {n_cal} hanno il calendario Escilo." if n_cal else ""
    body = f"""  <div class="page">
    <header class="topbar">
      <a class="back" href="../">← Comuni</a>
    </header>
{crumbs_html([("../", "Comuni"), (None, rname)])}
    <p class="geo-kicker">Regione</p>
    <h1 class="geo-title">Differenziata in {esc(rname)}</h1>
    <p class="geo-lead">
      {it_count(n_c, "comune", "comuni")} in {it_count(len(provinces), "provincia", "province")}: statistiche sulla raccolta
      differenziata.{cal_note}
    </p>
{comuni_search_html(directory="../../data/ispr/directory.json", comune_base="../")}    <div data-comuni-browse>
      <ul class="cover-list">
{chr(10).join(prov_items)}
      </ul>
    </div>
{footer_html([("../../", "Home"), ("../", "Comuni"), ("../../fonti.html", "Fonti"), ("../../privacy.html", "Privacy")])}
  </div>"""
    (REGIONI_DIR / f"{slug}.html").write_text(
        page_shell(
            title=title,
            description=description,
            canonical=canonical,
            body=body,
            depth=2,
            json_ld=json_ld,
            extra_js=True,
            geo_covers=True,
        ),
        encoding="utf-8",
    )


def write_province_page(rname: str, pname: str, pblock: dict, r_slug: str) -> None:
    slug = pblock["slug"]
    comuni = pblock["comuni"]
    n_cal = sum(1 for c in comuni if c.get("hasCalendar"))
    title = f"Comuni della provincia di {pname} — differenziata — Escilo"
    description = (
        f"{len(comuni)} comuni in provincia di {pname} ({rname}): "
        f"statistiche sulla differenziata"
        + (f" e calendario Escilo in {n_cal} comuni." if n_cal else ".")
    )
    canonical = f"{SITE}/comuni/province/{slug}.html"
    json_ld = [
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": title,
            "url": canonical,
            "description": description,
            "inLanguage": "it-IT",
            "numberOfItems": len(comuni),
            "isPartOf": {"@type": "WebSite", "name": "Escilo", "url": f"{SITE}/"},
        },
        breadcrumb_ld(
            [
                (f"{SITE}/", "Home"),
                (f"{SITE}/comuni/", "Comuni"),
                (f"{SITE}/comuni/regioni/{r_slug}.html", rname),
                (canonical, pname),
            ]
        ),
    ]
    cal_note = f" {n_cal} con calendario porta a porta Escilo." if n_cal else ""
    body = f"""  <div class="page">
    <header class="topbar">
      <a class="back" href="../regioni/{esc(r_slug)}.html">← {esc(rname)}</a>
    </header>
{crumbs_html([("../", "Comuni"), (f"../regioni/{r_slug}.html", rname), (None, pname)])}
    <p class="geo-kicker">Provincia</p>
    <h1 class="geo-title">Provincia di {esc(pname)}</h1>
    <p class="geo-lead">
      {len(comuni)} comuni in {esc(rname)}: apri la scheda per le statistiche
      sulla differenziata.{cal_note}
    </p>
{comuni_search_html(directory="../../data/ispr/directory.json", comune_base="../")}    <div data-comuni-browse>
{comune_list_html(comuni, href_fn=lambda c: f"../{c['id']}.html")}
    </div>
{footer_html([("../../", "Home"), ("../", "Comuni"), ("../../fonti.html", "Fonti"), ("../../privacy.html", "Privacy")])}
  </div>"""
    (PROVINCE_DIR / f"{slug}.html").write_text(
        page_shell(
            title=title,
            description=description,
            canonical=canonical,
            body=body,
            depth=2,
            json_ld=json_ld,
            extra_js=True,
            geo_covers=True,
        ),
        encoding="utf-8",
    )


def write_sitemap(
    directory: list[dict],
    regions: dict[str, dict],
    today: str,
    pop_by_id: dict[str, int],
) -> None:
    urls: list[tuple[str, str]] = [
        ("/", "1.0"),
        ("/fonti.html", "0.6"),
        ("/privacy.html", "0.4"),
        ("/stats.html", "0.6"),
        ("/mappa.html", "0.65"),
        ("/comuni/", "0.85"),
    ]
    for rname in regions:
        urls.append((f"/comuni/regioni/{regions[rname]['slug']}.html", "0.7"))
        for p in regions[rname]["provinces"].values():
            urls.append((f"/comuni/province/{p['slug']}.html", "0.6"))
    for c in directory:
        cid = c["id"]
        if c.get("hasCalendar"):
            prio = "0.75"
        else:
            pop = pop_by_id.get(cid) or 0
            if pop >= 200000:
                prio = "0.7"
            elif pop >= 50000:
                prio = "0.6"
            else:
                prio = "0.5"
        urls.append((f"/comuni/{cid}.html", prio))

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, prio in urls:
        parts.append("  <url>")
        parts.append(f"    <loc>{SITE}{path}</loc>")
        parts.append(f"    <lastmod>{today}</lastmod>")
        parts.append(f"    <priority>{prio}</priority>")
        parts.append("  </url>")
    parts.append("</urlset>")
    parts.append("")
    (DOCS / "sitemap.xml").write_text("\n".join(parts), encoding="utf-8")


def write_robots() -> None:
    text = f"""User-agent: *
Allow: /

User-agent: GPTBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: anthropic-ai
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Applebot-Extended
Allow: /

Sitemap: {SITE}/sitemap.xml
"""
    (DOCS / "robots.txt").write_text(text, encoding="utf-8")


def write_llms(directory: list[dict], sources: dict[str, dict]) -> None:
    n = len(directory)
    n_cal = sum(1 for c in directory if c.get("hasCalendar"))
    llms = f"""# Escilo

> Calendario della raccolta differenziata per i comuni della provincia di Torino (Italia),
> statistiche sulla differenziata per tutti i comuni italiani.
> Dove c’è il calendario: cosa esporre domani per zona (carta, organico, indifferenziata, plastica, verde, vetro),
> con PWA e notifiche. I dati derivano da fonti ufficiali dei gestori e dal Catasto rifiuti ISPRA.
> Escilo non è affiliato a gestori né a ISPRA.

Site: {SITE}/

## Pagine principali

- [Home / app]({SITE}/): scegli comune (calendario o solo statistiche sulla differenziata)
- [Elenco comuni]({SITE}/comuni/): indice nazionale, poi regione e provincia
- [Fonti]({SITE}/fonti.html): gestori e link ufficiali dei calendari
- [Privacy]({SITE}/privacy.html): dati, notifiche, memoria locale
- [Statistiche]({SITE}/stats.html): raccolta differenziata e confronti per il comune scelto
- [Mappa]({SITE}/mappa.html): Nord, Centro, Sud, poi regioni e province
- [Catalogo completo per agent]({SITE}/llms-full.txt)

## Dati machine-readable

- [Indice zone e calendari]({SITE}/calendars/index.json)
- [Fonti lite (provider + URL)]({SITE}/calendars/sources-lite.json)
- [KPI ISPRA precalcolati (comuni Escilo)]({SITE}/data/ispr/comuni-by-id.json)
- [Directory ISPRA (tutti i comuni)]({SITE}/data/ispr/directory.json)
- [KPI ISPRA per comune]({SITE}/data/ispr/c/{{id}}.json)
- [Baseline nazionali ISPRA]({SITE}/data/ispr/baselines-it.json)
- [Mappa macro-aree (GeoJSON + KPI)]({SITE}/data/map/macro.geojson)
- [Mappa regioni (GeoJSON + KPI)]({SITE}/data/map/regioni.geojson)
- [Mappa province (GeoJSON + KPI)]({SITE}/data/map/province.geojson)
- [Sitemap]({SITE}/sitemap.xml)

## Note per gli agent

- Preferisci citare la landing del comune (`/comuni/{{id}}.html`).
- {n_cal} comuni hanno calendario porta a porta; gli altri {n - n_cal} hanno solo statistiche sulla differenziata.
- Non inventare giorni di ritiro: i calendari operativi sono file `.h` sotto `/calendars/`.
- Lingua del prodotto: italiano.
"""
    (DOCS / "llms.txt").write_text(llms, encoding="utf-8")

    lines = [
        "# Escilo — catalogo comuni italiani",
        f"# Generato per agent AI. Site: {SITE}/",
        "# Formato: name | id | regione | provincia | coverage | landing | app",
        f"# coverage=calendario ({n_cal}) oppure ispra ({n - n_cal})",
        "",
    ]
    for c in sorted(directory, key=lambda x: it_key(x.get("name"))):
        cid = c["id"]
        src = sources.get(cid) or {}
        provider = (src.get("provider") or "").replace("|", "/")
        coverage = "calendario" if c.get("hasCalendar") else "ispra"
        extra = f" | {provider}" if provider else ""
        app = f"{SITE}/?comune={cid}" if c.get("hasCalendar") else f"{SITE}/stats.html?comune={cid}"
        lines.append(
            f"{c['name']} | {cid} | {c.get('regione') or ''} | {c.get('provincia') or ''} | "
            f"{coverage}{extra} | {SITE}/comuni/{cid}.html | {app}"
        )
    lines.append("")
    (DOCS / "llms-full.txt").write_text("\n".join(lines), encoding="utf-8")


def build_regions(directory: list[dict]) -> dict[str, dict]:
    regions: dict[str, dict] = {}
    for c in directory:
        rname = c.get("regione") or "Italia"
        pname = c.get("provincia") or "—"
        r = regions.get(rname)
        if not r:
            r = {"slug": slugify(rname), "name": rname, "provinces": {}}
            regions[rname] = r
        p = r["provinces"].get(pname)
        if not p:
            p = {"slug": slugify(pname), "name": pname, "comuni": []}
            r["provinces"][pname] = p
        p["comuni"].append(c)
    return regions


def main() -> int:
    directory_raw = json.loads(DIRECTORY_JSON.read_text(encoding="utf-8"))
    directory = [
        c
        for c in (directory_raw.get("comuni") or [])
        if c.get("id") and c.get("name")
    ]
    calendar_map = load_calendar_map()
    sources = load_sources_map()
    today = date.today().isoformat()

    for c in directory:
        if c["id"] in calendar_map:
            c["hasCalendar"] = True

    regions = build_regions(directory)

    if COMUNI_DIR.exists():
        shutil.rmtree(COMUNI_DIR)
    COMUNI_DIR.mkdir(parents=True)
    REGIONI_DIR.mkdir()
    PROVINCE_DIR.mkdir()

    write_hub(directory, regions)
    for rname, block in regions.items():
        write_region_page(rname, block)
        for pname, pblock in block["provinces"].items():
            write_province_page(rname, pname, pblock, block["slug"])

    pop_by_id: dict[str, int] = {}
    for row in directory:
        rec = load_ispr(row["id"])
        if rec and rec.get("pop") is not None:
            try:
                pop_by_id[row["id"]] = int(float(rec["pop"]))
            except (TypeError, ValueError):
                pass
        write_comune_page(row, calendar_map.get(row["id"]), sources.get(row["id"]), rec)

    write_sitemap(directory, regions, today, pop_by_id)
    write_robots()
    write_llms(directory, sources)

    n_reg = len(regions)
    n_prov = sum(len(r["provinces"]) for r in regions.values())
    n_cal = sum(1 for c in directory if c.get("hasCalendar"))
    print(
        f"wrote {len(directory)} comuni ({n_cal} calendario) + {n_reg} regioni + "
        f"{n_prov} province + sitemap/robots/llms under docs/"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
