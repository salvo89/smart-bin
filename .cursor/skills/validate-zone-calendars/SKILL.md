---
name: validate-zone-calendars
description: >-
  Ensures every comune/via in docs/calendars/index.json loads a real calendar
  (same path as app "Mostra calendario"). Use whenever adding/editing calendar
  .h files, updating index.json, comuni/zone/vie lists, batch PDF→.h imports,
  or sources that feed the index. Runs tools/validate_zone_calendars.py; must
  pass before finishing.
---

# Validate zone calendars (Mostra calendario)

Ogni volta che viene aggiornato un calendario, l'indice dei comuni o l'elenco delle vie, vanno eseguiti questi test per accertarsi che l'app continui a funzionare.

## When (obbligatorio)

Run **before** closing work that touches any of:

- `docs/calendars/*.h` (add / edit / regenerate)
- `docs/calendars/index.json` (comuni, zone, vie, calendar paths)
- Batch importers: `tools/batch_*.py`, `tools/*_pdf_to_h.py`, merge scripts that rewrite index
- `docs/calendars/sources.json` when it drives a re-import into index

Do not skip if “only one zone” changed: orphans and bad labels regress silently in the zone gate.

## Steps

1. From repo root:

```bash
py -3 tools/validate_zone_calendars.py
```

JSON (CI / tooling):

```bash
py -3 tools/validate_zone_calendars.py --json
```

Or: `npm run test:zones`

2. Exit **0** required. Exit **1** = some via would show “Impossibile caricare il calendario” / empty data.

3. On failure, fix then re-run:

| Symptom | Typical fix |
|---------|-------------|
| `Nessun calendario anno per …` | Point `vie[].calendar` at an existing base, or add `base-YYYY.h` for active years |
| Phantom `Zona unica` / `-z1` | Remove index entry if no file; comuni multi-zona must not invent z1 |
| Label `Zona Xpdf` / `*pdf` calendar | Strip `.pdf` from zone labels/slugs; prefer URL `zona-X` token |
| `Nessuna entry` | Re-extract `.h`; also run `check-calendar-anomalies` |
| Comune senza `vie` | Add at least one via with a working calendar |

4. Active years = last **2** entries in `index.json` `years[]` (same as `docs/index.html` `activeYears()`). A calendar needs ≥1 parseable `.h` among those years.

5. After index/vie fixes that change landing zone lists → follow `maintain-escilo-seo` (`build_seo_pages.py`).

6. Tell the user: `vieOk` / `vieFail` / `calendarsFail` + list of failed calendars if any.

## Related

- Entry-count quality: `.cursor/skills/check-calendar-anomalies/SKILL.md`
- SEO landings after index changes: `.cursor/skills/maintain-escilo-seo/SKILL.md`
