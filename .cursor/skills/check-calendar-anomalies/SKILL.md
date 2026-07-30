---
name: check-calendar-anomalies
description: >-
  Validates Smart Bin calendar .h files for anomalous entry counts after add/edit.
  Use whenever adding, generating, regenerating, or modifying any
  docs/calendars/*.h calendar data file (or batch PDF→.h conversion).
  Runs tools/check_calendar_anomalies.py and reports broken/critical/alert findings.
---

# Check calendar .h anomalies

## When to run

**Always** run this skill before finishing work that:

- Adds a new `docs/calendars/*-YYYY.h` file
- Edits an existing calendar `.h` (manual or via `tools/*_pdf_to_h.py` / batch scripts)
- Regenerates calendars from PDF/HTML sources

Do not skip even if the conversion “looked fine”.

## Steps

1. Identify touched calendar files under `docs/calendars/` (and their year, e.g. 2026).
2. Run the checker from repo root:

```bash
py tools/check_calendar_anomalies.py --year YYYY
```

For only the files just changed:

```bash
py tools/check_calendar_anomalies.py --year YYYY path/to/file-a-2026.h path/to/file-b-2026.h
```

JSON report (for canvases / tooling):

```bash
py tools/check_calendar_anomalies.py --year YYYY --json
```

3. Interpret severities:

| Severity | Meaning | Action |
|----------|---------|--------|
| `broken` | &lt;10 entries | Must fix before done — extraction failed |
| `critical` | &lt;50 entries (and not sparse-Indiff design) | Must investigate / fix or document why |
| `alert` | IQR low outlier | Review vs source PDF; fix if incomplete |
| `high` | IQR high outlier | Usually OK (dense schedule); spot-check |
| `ok` | Normal, or sparse Indifferenziato-only (20–60 entries, bin 2 only, ≥10 months) | No action |

Exit code: `--fail-on critical` (default) → exit 1 if broken/critical present.

4. If **broken** or **critical** on a file you just wrote:
   - Re-open the source PDF/HTML
   - Prefer the provider converter (`tools/acsel_pdf_to_h.py`, `covar14_pdf_to_h.py`, etc.)
   - ACSEL single-page flyers with weekday columns = solo Indifferenziato porta a porta (isole for other bins) — expect ~26 (biweekly) or ~52 (weekly) entries of bin 2 only; the checker treats that as `ok`
   - Re-run the checker after the fix

5. Summarize to the user: counts by severity + list of non-ok files (path, entries, reason).

## Notes

- Typical full door-to-door year ≈ **200–300** entries (median ~223 for 2026).
- Covar14 PDFs often start in March → ~10 months is normal if entry count is still high.
- `villastellone-z3` Covar14 PDF has missing event text vs z1/z2 — remains critical until source is fixed or re-extracted.
