import { $ } from "../shared/dom.js";
import { state } from "../state.js";

// 0–5: cassonetti firmware / UNI. Indici >=6: solo PWA (legenda + calendario).
export const BIN_BADGE_SHORT = ["Car", "Org", "Ind", "Pla", "Ver", "Vet", "Spa"];
export const BIN_FULL = {
  C: { code: "Car", name: "Carta", icon: "📄", sw: "sw-c", legend: "Carta" },
  O: { code: "Org", name: "Organico", icon: "🍂", sw: "sw-o", legend: "Organico" },
  I: { code: "Ind", name: "Indifferenziata", icon: "🗑", sw: "sw-i", legend: "Indiff." },
  P: { code: "Pla", name: "Plastica", icon: "♻", sw: "sw-p", legend: "Plastica" },
  V: { code: "Ver", name: "Verde", icon: "🌿", sw: "sw-v", legend: "Verde" },
  G: { code: "Vet", name: "Vetro", icon: "🫙", sw: "sw-g", legend: "Vetro" },
  S: { code: "Spa", name: "Spazzamento", icon: "🧹", sw: "sw-s", legend: "Spazzamento" },
};
export const DOW_IT = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"];
export const DOW_FULL = [
  "Lunedì",
  "Martedì",
  "Mercoledì",
  "Giovedì",
  "Venerdì",
  "Sabato",
  "Domenica",
];
export const MONTH_IT = [
  "Gennaio",
  "Febbraio",
  "Marzo",
  "Aprile",
  "Maggio",
  "Giugno",
  "Luglio",
  "Agosto",
  "Settembre",
  "Ottobre",
  "Novembre",
  "Dicembre",
];
export const BIN_INDEX_INITIAL = ["C", "O", "I", "P", "V", "G", "S"];
export const BIN_LEGEND_CORE = ["C", "O", "I", "P", "V", "G"];

export function ymdKey(y, m, d) {
  return y + "-" + String(m).padStart(2, "0") + "-" + String(d).padStart(2, "0");
}

export function weekdayMondayFirst(y, m, d) {
  const js = new Date(y, m - 1, d).getDay();
  return js === 0 ? 6 : js - 1;
}

export function formatDateIt(y, m, d) {
  const wd = weekdayMondayFirst(y, m, d);
  return DOW_FULL[wd] + " " + d + " " + MONTH_IT[m - 1];
}

export function initialsToItems(initials) {
  if (!initials || typeof initials !== "string") return [];
  return initials
    .split(".")
    .filter(Boolean)
    .map((p) => {
      const ch = p.charAt(0);
      return BIN_FULL[ch] || { code: "Ris", name: "Rifiuto", icon: "•", sw: "sw-x", ch };
    });
}

export function daysInMonth(y, m) {
  return new Date(y, m, 0).getDate();
}

export function binInitialFromIndex(binIndex) {
  return BIN_INDEX_INITIAL[binIndex] || "?";
}

export function collectBinsForYmd(y, m, d) {
  const out = [];
  for (let i = 0; i < state.calendarEntries.length; i++) {
    const e = state.calendarEntries[i];
    if (e[0] === y && e[1] === m && e[2] === d) {
      const bin = e[3];
      if (bin >= 0 && bin < BIN_INDEX_INITIAL.length) out.push(bin);
    }
  }
  return out;
}

export function dayInfo(y, m, d) {
  const bins = collectBinsForYmd(y, m, d);
  const initials = bins.map(binInitialFromIndex).join(".");
  return { initials, bins };
}

export function cacheMonth(y, m) {
  const D = daysInMonth(y, m);
  const out = new Array(D + 1);
  for (let d = 1; d <= D; d++) {
    const info = dayInfo(y, m, d);
    out[d] = info;
    state.dayCache.set(ymdKey(y, m, d), {
      initials: info.initials,
    });
  }
  return out;
}

export function tagClassForInitial(ch) {
  switch (ch) {
    case "C":
      return "tag-c";
    case "O":
      return "tag-o";
    case "I":
      return "tag-i";
    case "P":
      return "tag-p";
    case "V":
      return "tag-v";
    case "G":
      return "tag-g";
    case "S":
      return "tag-s";
    default:
      return "tag-x";
  }
}

export function badgeLabelFromInitial(ch) {
  return (BIN_FULL[ch] && BIN_FULL[ch].code) || "Ris";
}

/** Legenda: core differenziata sempre; tipi extra PWA (es. Spazzamento) solo se nel calendario. */
export function syncCalLegend() {
  const root = $("calLegend");
  if (!root) return;
  const present = new Set();
  for (let i = 0; i < state.calendarEntries.length; i++) {
    const bin = state.calendarEntries[i][3];
    if (bin >= 0 && bin < BIN_INDEX_INITIAL.length) {
      present.add(BIN_INDEX_INITIAL[bin]);
    }
  }
  const order = BIN_LEGEND_CORE.slice();
  BIN_INDEX_INITIAL.forEach((ch) => {
    if (BIN_LEGEND_CORE.indexOf(ch) === -1 && present.has(ch)) order.push(ch);
  });
  root.innerHTML = "";
  order.forEach((ch) => {
    const meta = BIN_FULL[ch];
    if (!meta) return;
    const span = document.createElement("span");
    span.innerHTML =
      '<i class="' +
      tagClassForInitial(ch) +
      '" aria-hidden="true"></i><span class="name">' +
      (meta.legend || meta.name) +
      "</span>";
    root.appendChild(span);
  });
}

export function createBadgeSpan(label, initialForColor, titleExtra) {
  const span = document.createElement("span");
  span.className = "tag " + tagClassForInitial(initialForColor);
  span.textContent = label;
  span.title = titleExtra ? titleExtra + " · " + label : label;
  return span;
}

export function badgesFromInitialsString(initials) {
  if (!initials || typeof initials !== "string") return null;
  const parts = initials.split(".").filter(Boolean);
  if (parts.length === 0) return null;
  return parts.map((p) => {
    const ch = p.charAt(0);
    return createBadgeSpan(badgeLabelFromInitial(ch), ch, p.length > 1 ? p : "");
  });
}

export function buildDowHeader() {
  const head = $("calGridHead");
  head.innerHTML = "";
  DOW_IT.forEach((name) => {
    const el = document.createElement("div");
    el.className = "cal-dow";
    el.textContent = name.charAt(0);
    head.appendChild(el);
  });
}

export function rollingWeekStart(ref) {
  return new Date(ref.getFullYear(), ref.getMonth(), ref.getDate());
}

export function dowShort(d) {
  const js = d.getDay();
  return DOW_IT[js === 0 ? 6 : js - 1];
}

export function ymdKeyFromDate(d) {
  return ymdKey(d.getFullYear(), d.getMonth() + 1, d.getDate());
}

export function isKeyInRollingWeek(key, start) {
  for (let i = 0; i < 7; i++) {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
    if (ymdKeyFromDate(d) === key) return true;
  }
  return false;
}

export function monthAbbrev(d) {
  return MONTH_IT[d.getMonth()].slice(0, 3);
}

export function monthHasData(y, m) {
  for (let i = 0; i < state.calendarEntries.length; i++) {
    const e = state.calendarEntries[i];
    if (e[0] === y && e[1] === m) return true;
  }
  return false;
}

/** Cache months covered by the rolling week (render is left to callers / loadMonth). */
export function ensureWeekMonthsCached() {
  const today = new Date();
  const start = rollingWeekStart(today);
  const months = new Set();
  for (let i = 0; i < 7; i++) {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
    months.add(d.getFullYear() + "-" + (d.getMonth() + 1));
  }
  for (const key of months) {
    const [y, m] = key.split("-").map(Number);
    cacheMonth(y, m);
  }
}

export function parseYmd(ymd) {
  if (!ymd || !/^\d{4}-\d{2}-\d{2}$/.test(ymd)) return null;
  const [y, m, d] = ymd.split("-").map(Number);
  if (!y || m < 1 || m > 12 || d < 1 || d > 31) return null;
  return { year: y, month: m, day: d };
}
