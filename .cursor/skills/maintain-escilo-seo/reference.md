# Escilo SEO — reference

## Architettura

```
docs/calendars/index.json + sources-lite.json
        ↓
tools/build_seo_pages.py
        ↓
docs/comuni/*.html , docs/comuni/index.html
docs/sitemap.xml , docs/robots.txt
docs/llms.txt , docs/llms-full.txt
```

Build Netlify (`netlify.toml`): `npm install && python3 tools/build_seo_pages.py`.

## File e responsabilità

| Area | File | Note SEO |
|------|------|----------|
| App PWA | `docs/index.html` | meta, OG, JSON-LD WebApplication, blocco visually-hidden, footer, `?comune=` |
| Fonti | `docs/fonti.html` | meta, OG, JSON-LD WebPage, footer, intro link brevi |
| Landing | `docs/comuni/**` | **generate** — non editare a mano salvo emergenza; modifica il generatore |
| Generatore | `tools/build_seo_pages.py` | `SITE`, CSS `.page` 28rem allineato a fonti, template footer/meta |
| Discovery | `robots.txt`, `sitemap.xml`, `llms.txt`, `llms-full.txt` | generati dallo script |
| PWA shell | `docs/sw.js`, `manifest.webmanifest` | description manifest utile; no precache comuni |
| Headers | `netlify.toml` | Content-Type/cache per robots/sitemap/llms/comuni |
| Smoke | `netlify/functions/shared/smoke.test.mjs` | assert file SEO + needle in index/toml |

## Scenario → azione

| Cambio | Azione agent |
|--------|----------------|
| Nuovo comune in `index.json` | `validate_zone_calendars.py`; rigenera SEO; smoke; ricorda GSC se deploy ampio |
| Rinomina zona/via | `validate_zone_calendars.py`; rigenera landing di quel comune |
| Nuovo/aggiornato `.h` o batch import | `validate_zone_calendars.py` + `check_calendar_anomalies.py` |
| Cambio title/tagline brand | Aggiorna index + fonti + generatore (title/OG) + eventualmente manifest |
| Nuovo footer link | Aggiorna vocabolario in skill + tutte le superfici (index, fonti, generatore) |
| Dominio / SITE | `SITE` in `build_seo_pages.py` = `https://escilo.it`; meta canoniche + GSC su `.it`; 301 da `.netlify.app` / `.com` |
| Solo bug JS calendario | Verifica che meta/footer non siano stati toccati accidentalmente |

## Ranking (aspettative)

On-page forte ≠ ranking immediato. Landing + sitemap danno segnale; GSC + tempo + backlink contano. Non promettere posizioni SERP.
