"""Generate SEO landing pages, sitemap, robots.txt and llms.txt from calendar indexes."""
from __future__ import annotations

import html
import json
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
INDEX_JSON = DOCS / "calendars" / "index.json"
SOURCES_LITE = DOCS / "calendars" / "sources-lite.json"
COMUNI_DIR = DOCS / "comuni"
SITE = "https://escilo.it"
# Shared styles live in docs/assets/css/ (linked, not inlined).
SEO_CSS_VER = "18"
SEO_CSS_HREF = (
    "../assets/css/tokens.css",
    f"../assets/css/chrome.css?v={SEO_CSS_VER}",
    f"../assets/css/seo.css?v={SEO_CSS_VER}",
)


def esc(s: object) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


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


def page_shell(
    *,
    title: str,
    description: str,
    canonical: str,
    body: str,
    json_ld: dict | list | None = None,
) -> str:
    ld = ""
    if json_ld is not None:
        ld = (
            '<script type="application/ld+json">\n'
            + json.dumps(json_ld, ensure_ascii=False, indent=2)
            + "\n</script>\n"
        )
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="#1f5c42" media="(prefers-color-scheme: light)" />
  <meta name="theme-color" content="#0f1612" media="(prefers-color-scheme: dark)" />
  <title>{esc(title)}</title>
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
  <link rel="icon" type="image/png" sizes="192x192" href="../icon-192.png" />
  <link rel="apple-touch-icon" sizes="512x512" href="../icon-512.png" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="{SEO_CSS_HREF[0]}" />
  <link rel="stylesheet" href="{SEO_CSS_HREF[1]}" />
  <link rel="stylesheet" href="{SEO_CSS_HREF[2]}" />
  {ld}</head>
<body>
{body}
</body>
</html>
"""


def write_comune_page(comune: dict, source: dict | None) -> None:
    cid = comune["id"]
    name = comune["name"]
    vie = comune.get("vie") or []
    provider = (source or {}).get("provider") or ""
    source_page = (source or {}).get("sourcePage") or ""
    title = f"Calendario raccolta differenziata {name} — Escilo"
    description = (
        f"Calendario ritiri rifiuti a {name} (provincia di Torino): "
        f"scopri cosa esporre domani per zona con Escilo."
    )
    canonical = f"{SITE}/comuni/{cid}.html"
    app_url = f"{SITE}/?comune={cid}"

    zones_html = "\n".join(
        f"<li>{esc(v.get('name') or '')}</li>" for v in sorted(vie, key=lambda x: str(x.get("name") or "").casefold())
    )
    if not zones_html:
        zones_html = "<li>Zone in aggiornamento</li>"

    fonte_html = ""
    if provider or source_page:
        link = (
            f'<a class="ext-link" href="{esc(source_page)}" target="_blank" rel="noopener noreferrer">'
            f"pagina ufficiale"
            f'<span class="visually-hidden"> (si apre in una nuova scheda)</span></a>'
            if source_page
            else "fonte ufficiale del gestore"
        )
        fonte_html = (
            f'<p class="note">Gestore: <strong>{esc(provider or "—")}</strong>'
            f" · dati da {link}. Escilo non è affiliato al gestore.</p>"
        )

    json_ld = [
        {
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
                    "addressRegion": "Piemonte",
                    "addressCountry": "IT",
                },
            },
        },
    ]

    body = f"""  <div class="page">
    <header class="topbar">
      <a class="back" href="../">← Home</a>
    </header>
    <section class="intro">
      <h1>Calendario raccolta differenziata — {esc(name)}</h1>
      <p>
        Ritiri rifiuti a {esc(name)} (provincia di Torino): carta, organico,
        indifferenziata, plastica, verde e vetro. Escilo ti ricorda cosa esporre domani.
      </p>
    </section>
    <div class="card">
      <h2 class="box-title">Zone e vie disponibili</h2>
      <ul class="zones">
{zones_html}
      </ul>
      <a class="cta" href="{esc(app_url)}">Apri il calendario di {esc(name)}</a>
    </div>
    {fonte_html}
    <p class="meta">
      Puoi installare Escilo come app e attivare le notifiche sul telefono.
      Verifica sempre eventuali variazioni sul sito del gestore.
    </p>
    <p class="footer">
      <a href="../">Home</a>
      <span class="sep">&middot;</span>
      <a href="./">Comuni</a>
      <span class="sep">&middot;</span>
      <a href="../fonti.html">Fonti</a>
    </p>
  </div>"""

    (COMUNI_DIR / f"{cid}.html").write_text(
        page_shell(
            title=title,
            description=description,
            canonical=canonical,
            body=body,
            json_ld=json_ld,
        ),
        encoding="utf-8",
    )


def write_comuni_index(comuni: list[dict]) -> None:
    title = "Comuni — calendario raccolta differenziata Escilo"
    description = (
        "Elenco dei comuni della provincia di Torino con calendario ritiri rifiuti su Escilo."
    )
    canonical = f"{SITE}/comuni/"
    items = "\n".join(
        f'<li><a href="{esc(c["id"])}.html">{esc(c["name"])}</a></li>'
        for c in sorted(comuni, key=lambda x: str(x.get("name") or "").casefold())
    )
    json_ld = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": title,
        "url": canonical,
        "description": description,
        "inLanguage": "it-IT",
        "isPartOf": {"@type": "WebSite", "name": "Escilo", "url": f"{SITE}/"},
        "numberOfItems": len(comuni),
    }
    body = f"""  <div class="page">
    <header class="topbar">
      <a class="back" href="../">← Home</a>
    </header>
    <section class="intro">
      <h1>Comuni con calendario differenziata</h1>
      <p>
        {len(comuni)} comuni della provincia di Torino: apri la pagina del tuo comune
        per vedere le zone e avviare il calendario ritiri.
      </p>
      <p class="meta">{len(comuni)} comuni supportati</p>
    </section>
    <ul class="comuni-grid">
{items}
    </ul>
    <p class="footer">
      <a href="../">Home</a>
      <span class="sep">&middot;</span>
      <a href="../fonti.html">Fonti</a>
    </p>
  </div>"""
    html_out = page_shell(
        title=title,
        description=description,
        canonical=canonical,
        body=body,
        json_ld=json_ld,
    )
    (COMUNI_DIR / "index.html").write_text(html_out, encoding="utf-8")


def write_sitemap(comuni: list[dict], today: str) -> None:
    urls = [
        ("/", "1.0"),
        ("/fonti.html", "0.6"),
        ("/stats.html", "0.6"),
        ("/comuni/", "0.8"),
    ]
    for c in comuni:
        urls.append((f"/comuni/{c['id']}.html", "0.7"))

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


def write_llms(comuni: list[dict], sources: dict[str, dict]) -> None:
    llms = f"""# Escilo

> Calendario della raccolta differenziata per i comuni della provincia di Torino (Italia).
> Mostra cosa esporre domani per zona (carta, organico, indifferenziata, plastica, verde, vetro),
> con PWA e notifiche. I dati derivano da fonti ufficiali dei gestori; Escilo non è affiliato a essi.

Site: {SITE}/

## Pagine principali

- [Home / app calendario]({SITE}/): scegli comune e via
- [Elenco comuni]({SITE}/comuni/): landing SEO per ogni comune
- [Fonti]({SITE}/fonti.html): gestori e link ufficiali
- [Statistiche ISPRA]({SITE}/stats.html): raccolta differenziata e confronti nazionali per il comune scelto
- [Catalogo completo per agent]({SITE}/llms-full.txt)

## Dati machine-readable

- [Indice zone e calendari]({SITE}/calendars/index.json)
- [Fonti lite (provider + URL)]({SITE}/calendars/sources-lite.json)
- [KPI ISPRA precalcolati (comuni Escilo)]({SITE}/data/ispr/comuni-by-id.json)
- [Baseline nazionali ISPRA]({SITE}/data/ispr/baselines-it.json)
- [Sitemap]({SITE}/sitemap.xml)

## Note per gli agent

- Preferisci citare la landing del comune (`/comuni/{{id}}.html`) e la fonte ufficiale del gestore.
- Non inventare giorni di ritiro: i calendari operativi sono file `.h` sotto `/calendars/` e l’app li interpreta in base a comune/via.
- Lingua del prodotto: italiano.
"""
    (DOCS / "llms.txt").write_text(llms, encoding="utf-8")

    lines = [
        "# Escilo — catalogo comuni",
        f"# Generato per agent AI. Site: {SITE}/",
        "# Formato: name | id | provider | landing | app",
        "",
    ]
    for c in sorted(comuni, key=lambda x: str(x.get("name") or "").casefold()):
        cid = c["id"]
        src = sources.get(cid) or {}
        provider = (src.get("provider") or "").replace("|", "/")
        lines.append(
            f"{c['name']} | {cid} | {provider} | {SITE}/comuni/{cid}.html | {SITE}/?comune={cid}"
        )
    lines.append("")
    (DOCS / "llms-full.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    index = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    comuni = [c for c in (index.get("comuni") or []) if c.get("id") and c.get("name")]
    sources = load_sources_map()
    today = date.today().isoformat()

    if COMUNI_DIR.exists():
        shutil.rmtree(COMUNI_DIR)
    COMUNI_DIR.mkdir(parents=True)

    write_comuni_index(comuni)
    for c in comuni:
        write_comune_page(c, sources.get(c["id"]))

    write_sitemap(comuni, today)
    write_robots()
    write_llms(comuni, sources)

    print(f"wrote {len(comuni)} comuni pages + sitemap/robots/llms under docs/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
