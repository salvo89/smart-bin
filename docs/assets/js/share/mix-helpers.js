/** Shared mix fraction labels and copy helpers (stats page + share cards). */

export const MIX_LABELS = [
  { key: "umida", label: "Organico / umido", short: "Organico", cls: "mix-o", color: "#5a8f3a" },
  { key: "carta", label: "Carta e cartone", short: "Carta", cls: "mix-c", color: "#3d6eb5" },
  { key: "plastica", label: "Plastica", short: "Plastica", cls: "mix-p", color: "#c9a227" },
  { key: "verde", label: "Verde", short: "Verde", cls: "mix-v", color: "#2f8f6b" },
  { key: "vetro", label: "Vetro", short: "Vetro", cls: "mix-g", color: "#5b8f9a" },
];

export const MIX_IT_MEDIANS = {
  umida: 27.09,
  carta: 16.01,
  plastica: 9.34,
  verde: 9.34,
  vetro: 13.75,
};

export const MIX_EMOJI = {
  umida: "🍎",
  carta: "📦",
  plastica: "♻️",
  verde: "🌿",
  vetro: "🍾",
  altro: "📋",
};

export const MIX_ALTRO = {
  key: "altro",
  label: "Altro",
  short: "Altro",
  cls: "mix-x",
  color: "#8a9a90",
  emoji: "📋",
};

/** Colori legenda calendario (--tag-* in tokens.css) + inchiostro come .cal-cell .tag-* */
export const MIX_CAL_COLORS = {
  umida: { color: "#755c49", ink: "#fff4ec" },
  carta: { color: "#0e518d", ink: "#f4f8ff" },
  plastica: { color: "#f3e03b", ink: "#1a222c" },
  verde: { color: "#d1bc8a", ink: "#2a2418" },
  vetro: { color: "#28713e", ink: "#f2faf4" },
  altro: { color: "#a88bc8", ink: "#0a0e12" },
};

function fmtPct(n, digits) {
  if (n == null || Number.isNaN(n)) return "—";
  return (
    Number(n).toLocaleString("it-IT", {
      minimumFractionDigits: digits == null ? 1 : digits,
      maximumFractionDigits: digits == null ? 1 : digits,
    }) + "%"
  );
}

export function mixSuDieci(v) {
  return Math.max(1, Math.min(10, Math.round(Number(v) / 10)));
}

export function mixHeroCopy(top) {
  const short = (top.short || top.label).toLowerCase();
  const tenths = mixSuDieci(top.v);
  if (top.v >= 38) return "Quasi la metà del differenziato è " + short;
  if (tenths >= 4) return tenths + " sacchi su 10 sono " + short;
  if (tenths >= 2) {
    const denom = Math.max(2, Math.round(10 / tenths));
    return "1 rifiuto su " + denom + " è " + short;
  }
  return (top.short || top.label) + " è la frazione principale";
}

export function mixHeroSub(top) {
  const tenths = mixSuDieci(top.v);
  if (top.v >= 38) return tenths + " su 10 · " + fmtPct(top.v, 1);
  return fmtPct(top.v, 1) + " del totale differenziato";
}

/** @param {Record<string, number|null|undefined>|null|undefined} mix */
export function parseMixItems(mix) {
  const items = MIX_LABELS.map((item) => {
    const v = mix && mix[item.key];
    if (v == null) return null;
    return { ...item, v: Number(v), w: Math.max(0, Math.min(100, Number(v))) };
  })
    .filter(Boolean)
    .sort((a, b) => b.v - a.v);

  if (!items.length) return [];

  const sum = items.reduce((acc, item) => acc + item.v, 0);
  const rest = Math.max(0, 100 - sum);
  if (rest >= 0.5) {
    items.push({ ...MIX_ALTRO, v: rest, w: Math.min(100, rest) });
  }
  return items;
}
