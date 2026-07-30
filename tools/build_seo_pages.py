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
SITE = "https://escilo.netlify.app"

SHARED_CSS = """
:root {
  color-scheme: light;
  --bg: #eef6f1;
  --bg-top: #d8f0e2;
  --bg-bottom: #f4f7f5;
  --surface: #ffffff;
  --ink: #142018;
  --muted: #5a7266;
  --muted-2: #6a8074;
  --line: #d5e2da;
  --accent: #1f5c42;
  --accent-soft: #e4f3eb;
  --row-bg: #f7fbf8;
  --safe: 1rem;
  --font: "Outfit", "Segoe UI", system-ui, sans-serif;
  --display: "Fraunces", Georgia, serif;
}
@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --bg: #101814;
    --bg-top: #152019;
    --bg-bottom: #0c1210;
    --surface: #1a2420;
    --ink: #e6f0ea;
    --muted: #8fa396;
    --muted-2: #7a9084;
    --line: #2c3b33;
    --accent: #3d9a6e;
    --accent-soft: #1c3228;
    --row-bg: #151e1a;
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  min-height: 100dvh;
  font-family: var(--font);
  color: var(--ink);
  line-height: 1.45;
  background: linear-gradient(180deg, var(--bg-top) 0%, var(--bg) 28%, var(--bg-bottom) 100%);
}
a {
  color: var(--accent);
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.page {
  max-width: 28rem;
  margin: 0 auto;
  padding: 0.75rem var(--safe) 2.5rem;
  padding-top: max(0.75rem, env(safe-area-inset-top));
}
.topbar { margin-bottom: 1rem; }
.back {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.85rem;
  font-weight: 650;
  color: var(--accent);
  text-decoration: none;
}
.back:hover { text-decoration: underline; }
.crumbs {
  margin: 0 0 0.85rem;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--muted);
}
.crumbs a {
  color: var(--muted);
  font-weight: 600;
  text-decoration: none;
}
.crumbs a:hover { text-decoration: underline; }
.intro {
  margin: 0 0 1.25rem;
  padding: 1.1rem 1.05rem 1.05rem;
  border-radius: 1.25rem;
  background: linear-gradient(145deg, #1f5c42 0%, #2a7a58 48%, #1a4a36 100%);
  color: #f3faf6;
  box-shadow: 0 12px 28px rgba(26, 74, 54, 0.22);
}
.intro h1 {
  margin: 0 0 0.45rem;
  font-family: var(--display);
  font-size: 1.45rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.15;
}
.intro p {
  margin: 0;
  font-size: 0.88rem;
  opacity: 0.88;
}
.intro .meta {
  margin-top: 0.7rem;
  font-size: 0.72rem;
  opacity: 0.7;
  font-weight: 600;
}
.intro a {
  color: #f3faf6;
  font-weight: 650;
}
.note {
  margin: 0 0 1.15rem;
  padding: 0.75rem 0.85rem;
  border-radius: 0.85rem;
  background: var(--accent-soft);
  color: var(--ink);
  font-size: 0.78rem;
  line-height: 1.4;
}
.card {
  margin: 0 0 0.85rem;
  border-radius: 1.1rem;
  background: var(--surface);
  border: 1px solid var(--line);
  padding: 0.95rem 1rem 1rem;
}
.card h2 {
  margin: 0 0 0.65rem;
  font-size: 1.02rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.cta {
  display: block;
  width: 100%;
  margin: 0.85rem 0 0;
  padding: 0.85rem 1rem;
  border-radius: 0.95rem;
  background: var(--accent);
  color: #fff !important;
  text-align: center;
  text-decoration: none;
  font-weight: 700;
  font-size: 0.95rem;
}
.cta:hover { filter: brightness(1.05); }
ul.zones {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
ul.zones li {
  padding: 0.45rem 0.55rem;
  border-radius: 0.65rem;
  background: var(--row-bg);
  font-size: 0.86rem;
  font-weight: 600;
}
.comuni-grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.comuni-grid a {
  display: block;
  padding: 0.45rem 0.55rem;
  border-radius: 0.65rem;
  background: var(--row-bg);
  border: none;
  text-decoration: none;
  color: var(--ink);
  font-size: 0.86rem;
  font-weight: 600;
}
.comuni-grid a:hover { background: var(--accent-soft); }
.meta {
  margin: 0 0 0.85rem;
  color: var(--muted);
  font-size: 0.78rem;
  line-height: 1.4;
}
.footer {
  margin: 1.5rem 0 0;
  text-align: center;
  font-size: 0.72rem;
  color: var(--muted-2);
  line-height: 1.4;
}
.footer a {
  color: var(--accent);
  font-weight: 650;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.footer .sep {
  padding: 0 0.22rem;
  color: var(--accent);
  font-weight: 700;
}
"""


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
  <style>{SHARED_CSS}</style>
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
            f'<a href="{esc(source_page)}" target="_blank" rel="noopener noreferrer">pagina ufficiale</a>'
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
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Escilo", "item": f"{SITE}/"},
                {"@type": "ListItem", "position": 2, "name": "Comuni", "item": f"{SITE}/comuni/"},
                {"@type": "ListItem", "position": 3, "name": name, "item": canonical},
            ],
        },
    ]

    body = f"""  <div class="page">
    <header class="topbar">
      <a class="back" href="../">← Calendario</a>
    </header>
    <p class="crumbs"><a href="../">Home</a> · <a href="./">Comuni</a> · {esc(name)}</p>
    <section class="intro">
      <h1>Calendario raccolta differenziata — {esc(name)}</h1>
      <p>
        Ritiri rifiuti a {esc(name)} (provincia di Torino): carta, organico,
        indifferenziata, plastica, verde e vetro. Escilo ti ricorda cosa esporre domani.
      </p>
    </section>
    <div class="card">
      <h2>Zone e vie disponibili</h2>
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
      <a class="back" href="../">← Calendario</a>
    </header>
    <p class="crumbs"><a href="../">Home</a> · Comuni</p>
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
- [Catalogo completo per agent]({SITE}/llms-full.txt)

## Dati machine-readable

- [Indice zone e calendari]({SITE}/calendars/index.json)
- [Fonti lite (provider + URL)]({SITE}/calendars/sources-lite.json)
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
