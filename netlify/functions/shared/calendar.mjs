export const BIN_NAMES = [
  "Carta",
  "Organico",
  "Indifferenziata",
  "Plastica",
  "Verde",
  "Vetro",
];

/** Base zona senza anno/estensione. */
export function normalizeCalendarBase(path) {
  if (!path) return path;
  return String(path)
    .replace(/-\d{4}\.h$/i, "")
    .replace(/\.h$/i, "");
}

/** Estrae entry [anno, mese, giorno, bin] da file calendario. */
export function parseCalendarEntries(source) {
  const entries = [];
  const re = /\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(-?\d+)\s*\}/g;
  let m;
  while ((m = re.exec(source)) !== null) {
    entries.push([
      Number(m[1]),
      Number(m[2]),
      Number(m[3]),
      Number(m[4]),
    ]);
  }
  return entries;
}

/** Parti di data Europe/Rome (YYYY-MM-DD + hour 0–23). */
export function romeParts(date = new Date()) {
  const fmt = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Rome",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    hourCycle: "h23",
  });
  const map = {};
  for (const part of fmt.formatToParts(date)) {
    if (part.type !== "literal") map[part.type] = part.value;
  }
  return {
    year: Number(map.year),
    month: Number(map.month),
    day: Number(map.day),
    hour: Number(map.hour),
    dateKey: `${map.year}-${map.month}-${map.day}`,
  };
}

/** Giorno successivo in calendario civile (non DST-sensitive). */
export function nextDay(year, month, day) {
  const dt = new Date(Date.UTC(year, month - 1, day + 1));
  return {
    year: dt.getUTCFullYear(),
    month: dt.getUTCMonth() + 1,
    day: dt.getUTCDate(),
  };
}

/**
 * Bin indices (0–5) per una data, da entry già caricate.
 * @param {Array<[number, number, number, number]>} entries
 */
export function binsForDate(entries, year, month, day) {
  const set = new Set();
  for (const [y, m, d, bin] of entries) {
    if (y === year && m === month && d === day && bin >= 0 && bin < BIN_NAMES.length) {
      set.add(bin);
    }
  }
  return [...set].sort((a, b) => a - b);
}

export function formatBinsLabel(binIndexes) {
  return binIndexes.map((i) => BIN_NAMES[i]).join(", ");
}

/**
 * Anni da index.json (max 2 più recenti), fallback anno Rome + next.
 * @param {{ years?: number[] } | null} index
 */
export function activeYears(index, romeYear) {
  const raw = index && Array.isArray(index.years) ? index.years : [];
  const years = [...new Set(raw.map(Number).filter((y) => y > 2000))].sort((a, b) => a - b);
  if (years.length) return years.slice(-2);
  return [romeYear, romeYear + 1];
}

/**
 * Carica e unisce i file .h per una base calendario.
 * @param {(path: string) => Promise<string | null>} fetchText
 */
export async function loadCalendarEntries(fetchText, calendarBase, years) {
  const base = normalizeCalendarBase(calendarBase);
  const merged = [];
  let loaded = 0;
  for (const year of years) {
    const path = `${base}-${year}.h`;
    const text = await fetchText(path);
    if (!text) continue;
    merged.push(...parseCalendarEntries(text));
    loaded += 1;
  }
  if (!loaded) return null;
  merged.sort((a, b) => {
    if (a[0] !== b[0]) return a[0] - b[0];
    if (a[1] !== b[1]) return a[1] - b[1];
    if (a[2] !== b[2]) return a[2] - b[2];
    return a[3] - b[3];
  });
  return merged;
}
