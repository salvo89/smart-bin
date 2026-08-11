import { state } from "../state.js";
import { syncCalLegend } from "./calendar-model.js";

/** Base zona senza anno/estensione: calendars/candiolo-z2(.h|-2026.h) → calendars/candiolo-z2 */
export function normalizeCalendarBase(path) {
  if (!path) return path;
  return String(path)
    .replace(/-\d{4}\.h$/i, "")
    .replace(/\.h$/i, "");
}

/** Anno civile Europe/Rome (fallback se index.json non è ancora caricato). */
export function romeCalendarYear() {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Rome",
    year: "numeric",
  }).formatToParts(new Date());
  const y = Number((parts.find((p) => p.type === "year") || {}).value);
  return Number.isInteger(y) && y > 2000 ? y : new Date().getFullYear();
}

/** Al massimo due anni attivi da index.json (i più recenti); altrimenti anno Rome + next. */
export function activeYears() {
  const raw =
    state.zonesIndex && Array.isArray(state.zonesIndex.years) ? state.zonesIndex.years : [];
  const years = [...new Set(raw.map(Number).filter((y) => y > 2000))].sort((a, b) => a - b);
  if (years.length) return years.slice(-2);
  const y = romeCalendarYear();
  return [y, y + 1];
}

/** Estrae entry {anno,mese,giorno,bin} da file calendario (solo dati). */
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
  if (!entries.length) throw new Error("Nessuna entry calendario");
  return entries;
}

export async function loadZonesIndex() {
  const res = await fetch("calendars/index.json", { cache: "no-cache" });
  if (!res.ok) throw new Error("HTTP " + res.status + " caricando calendars/index.json");
  state.zonesIndex = await res.json();
  if (!state.zonesIndex || !Array.isArray(state.zonesIndex.comuni)) {
    throw new Error("index.json non valido");
  }
  if (!Array.isArray(state.zonesIndex.years) || !state.zonesIndex.years.length) {
    throw new Error("index.json: manca years[] (max 2 anni attivi)");
  }
}

/** Carica index.json solo quando serve il gate zona (non al boot se la zona è già salvata). */
export function ensureZonesIndex() {
  if (state.zonesIndex) return Promise.resolve();
  if (!state.zonesIndexPromise) {
    state.zonesIndexPromise = loadZonesIndex().catch((err) => {
      state.zonesIndexPromise = null;
      throw err;
    });
  }
  return state.zonesIndexPromise;
}

export async function loadSourcesLite() {
  const res = await fetch("calendars/sources-lite.json");
  if (!res.ok) return;
  const data = await res.json();
  if (!data || !Array.isArray(data.comuni)) return;
  /** @type {Record<string, { id: string, provider: string, sourcePage: string }>} */
  const map = Object.create(null);
  for (const c of data.comuni) {
    if (!c || !c.id) continue;
    map[c.id] = {
      id: c.id,
      provider: String(c.provider || ""),
      sourcePage: String(c.sourcePage || ""),
    };
  }
  state.sourcesLite = map;
}

/** Footer “Fonte”: carica sources-lite solo dopo la scelta zona. */
export function ensureSourcesLite() {
  if (state.sourcesLite) return Promise.resolve();
  if (!state.sourcesLitePromise) {
    state.sourcesLitePromise = loadSourcesLite()
      .catch((err) => {
        console.error(err);
        state.sourcesLite = Object.create(null);
      })
      .then(() => {
        if (!state.sourcesLite) state.sourcesLite = Object.create(null);
      });
  }
  return state.sourcesLitePromise;
}

export function sourceForComune(comuneId) {
  if (!state.sourcesLite || !comuneId) return null;
  return state.sourcesLite[comuneId] || null;
}

/** Carica fino a 2 file anno (`base-YYYY.h`) e unisce le entry. */
export async function loadCalendarEntries(calendarBase) {
  const base = normalizeCalendarBase(calendarBase);
  const years = activeYears();
  const merged = [];
  let loaded = 0;
  for (const year of years) {
    const path = base + "-" + year + ".h";
    const res = await fetch(path, { cache: "no-cache" });
    if (!res.ok) continue;
    const text = await res.text();
    merged.push(...parseCalendarEntries(text));
    loaded += 1;
  }
  if (!loaded) {
    throw new Error("Nessun calendario anno per " + base);
  }
  merged.sort((a, b) => {
    if (a[0] !== b[0]) return a[0] - b[0];
    if (a[1] !== b[1]) return a[1] - b[1];
    if (a[2] !== b[2]) return a[2] - b[2];
    return a[3] - b[3];
  });
  state.calendarEntries = merged;
  syncCalLegend();
}

export function formatFooterSourceHtml(src) {
  if (!src) return "";
  const href = src.sourcePage ? String(src.sourcePage) : "";
  const label = href
    ? 'Fonte: <a class="ext-link" href="' +
      href +
      '" target="_blank" rel="noopener noreferrer">' +
      src.provider +
      '<span class="visually-hidden"> (si apre in una nuova scheda)</span></a>'
    : "Fonte: " + src.provider;
  return label + '<span class="sep">&middot;</span>';
}

export function updateFooterSources(src) {
  const html = formatFooterSourceHtml(src);
  for (const el of document.querySelectorAll(".footer-source")) {
    if (html) {
      el.innerHTML = html;
      el.hidden = false;
    } else {
      el.innerHTML = "";
      el.hidden = true;
    }
  }
}

export async function refreshFooterSources() {
  if (!state.zoneChoice) {
    updateFooterSources(null);
    return;
  }
  await ensureSourcesLite();
  if (!state.zoneChoice) return;
  updateFooterSources(sourceForComune(state.zoneChoice.comuneId));
}

/** Chiede al SW di tenere in cache solo indici + calendari della zona attiva. */
export function precacheSelectedZone(calendarBase) {
  if (!("serviceWorker" in navigator)) return;
  const base = normalizeCalendarBase(calendarBase);
  if (!base) return;
  const urls = ["calendars/index.json"];
  for (const year of activeYears()) {
    urls.push(base + "-" + year + ".h");
  }
  const post = (sw) => {
    if (sw) sw.postMessage({ type: "cache-zone", urls });
  };
  if (navigator.serviceWorker.controller) {
    post(navigator.serviceWorker.controller);
    return;
  }
  navigator.serviceWorker.ready
    .then((reg) => post(reg.active))
    .catch((err) => console.error(err));
}
