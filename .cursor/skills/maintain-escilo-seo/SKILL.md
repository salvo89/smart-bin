---
name: maintain-escilo-seo
description: >-
  Keeps Escilo high-value SEO and AI discovery in sync whenever the public web
  app or PWA changes. Use when editing docs/index.html, docs/fonti.html,
  docs/comuni/**, docs/sw.js, docs/manifest.webmanifest, docs/robots.txt,
  docs/sitemap.xml, docs/llms.txt, docs/llms-full.txt, tools/build_seo_pages.py,
  docs/calendars/index.json, docs/calendars/sources-lite.json, netlify.toml,
  or any user-facing web/PWA copy, meta, footers, deep-links, or comune list.
  Also use when adding/removing comuni or renaming zone labels that appear on
  landing pages.
---

# Maintain Escilo SEO (web + PWA)

Site canonico: `https://escilo.netlify.app/`  
Publish dir: `docs/` (Netlify). Landing SEO generate da `tools/build_seo_pages.py`.

## Quando applicare (obbligatorio)

Prima di chiudere qualsiasi lavoro che tocca la superficie pubblica, **segui questa skill** se hai modificato anche solo uno tra:

- Shell PWA / app: `docs/index.html`, `docs/sw.js`, `docs/manifest.webmanifest`
- Pagine statiche: `docs/fonti.html`, `docs/comuni/**`
- Generatore / discovery: `tools/build_seo_pages.py`, `docs/robots.txt`, `docs/sitemap.xml`, `docs/llms.txt`, `docs/llms-full.txt`
- Dati che alimentano le landing: `docs/calendars/index.json`, `docs/calendars/sources-lite.json`
- Build/headers: `netlify.toml` (publish, SEO headers, `build_seo_pages.py`)

Non saltare perché “era solo un fix UI”: meta, footer, comuni e crawl surface devono restare coerenti.

## Checklist pre-done

Copia e spunta mentalmente:

1. **Title / description / canonical / OG / Twitter / JSON-LD** su ogni HTML toccato (home, fonti, landing comuni) restano presenti e allineati al contenuto reale.
2. **Testo crawlable** (non solo JS): home ha blocco SEO statico; landing comuni restano HTML statico con H1, zone, CTA `/?comune={id}`.
3. **Deep-link** `?comune=` su `docs/index.html` ancora funziona se tocchi il zone-gate.
4. **Footer labels** unificate (stesso vocabolario ovunque):

| Label | Target |
|-------|--------|
| Home | `/` / `index.html` / `../` |
| Comuni | `/comuni/` |
| Fonti | `fonti.html` |
| Segnala | mailto contatto |
| Condividi | solo home (share) |

Ordine footer (ometti link alla pagina corrente):
- Home app: `Fonti · Comuni · Segnala · Condividi`
- Fonti: `Home · Comuni · Segnala`
- Indice comuni: `Home · Fonti`
- Singolo comune: `Home · Comuni · Fonti`

5. Se hai cambiato comuni/zone in `index.json` / `sources-lite.json`, template landing, CSS SEO, footer/meta del generatore → **rigenera**:

```bash
py -3 tools/build_seo_pages.py
```

(Netlify lo fa già in build; in locale rigenera se vuoi verificare i file sotto `docs/comuni/` o se committi l’output.)

6. Smoke SEO ancora verde:

```bash
npm run test:push
```

7. **Non** aggiungere le landing `/comuni/*` al precache di `docs/sw.js` (restano SEO, non shell PWA).

8. In fine risposta: elenca cosa SEO hai aggiornato + eventuali **azioni manuali utente** (sotto).

## Cosa NON fare

- Non inventare giorni di ritiro nelle landing: solo zone da `index.json` + link fonte da `sources-lite.json`.
- Non cambiare il dominio canonico senza aggiornare: meta/OG, `build_seo_pages.py` (`SITE`), `robots.txt` Sitemap, `llms*.txt`, smoke asserts.
- Non lasciare label footer divergenti (“Tutte le fonti”, “Fonti dati”, “Scrivici”, “Home Escilo”, …).

## Azioni manuali da chiedere all’utente

Dopo deploy che cambia URL pubblici, sitemap, o molte landing, **diglielo esplicitamente**:

1. Aprire [Google Search Console](https://search.google.com/search-console) → proprietà `https://escilo.netlify.app/`
2. Se nuovo sito / nuova sitemap: inviare `https://escilo.netlify.app/sitemap.xml`
3. Richiedere indicizzazione per: home, `/comuni/`, e 2–3 comuni campione toccati
4. Se dominio custom in futuro: aggiornare `SITE` nel generatore + meta canoniche + GSC sulla nuova proprietà
5. Opzionale agent AI: verificare che `https://escilo.netlify.app/llms.txt` sia raggiungibile post-deploy

**Verifica Search Console (file HTML):** non rimuovere `docs/google*.html` (es. `docs/googled19b3747a0a192a7.html`). Deve restare in publish root per mantenere la proprietà verificata.

Se la modifica è solo CSS/layout interno senza URL/copy SEO → di solito **nessuna** azione GSC; dirlo comunque in una riga.

## Dettaglio file / edge case

Vedi [reference.md](reference.md).
