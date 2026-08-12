/** Cassonetti «Quanto produciamo» (UI + share image). */

const BODY_PATH = "M20 67 C20 67 20 148 28 153 L72 153 C80 148 80 67 80 67 Z";

let prodBinSvgSeq = 0;

export const PROD_BIN_KINDS = {
  total: { label: "Totale", aria: "Rifiuti urbani totali" },
  ind: { label: "Indifferenziato", aria: "Solo indifferenziato" },
};

/** Hex (non CSS var) così l’SVG rasterizza anche in data-URL. */
const PROD_SCALE_COLORS = {
  com: { fill: "#1f5c42", text: "#ffffff" },
  it: { fill: "#142018", text: "#ffffff" },
  reg: { fill: "#3d6eb5", text: "#ffffff" },
};

const PROD_BIN_THEMES = {
  total: {
    gradL: "#5da032",
    gradM: "#7ec850",
    gradR: "#4f9228",
    rim: "#4a8a28",
    rimDark: "#3d7222",
    rimTop: "#356a1f",
    ribs: "#356a1f",
  },
  ind: {
    gradL: "#525860",
    gradM: "#727983",
    gradR: "#434850",
    rim: "#5a6169",
    rimDark: "#4a5058",
    rimTop: "#3d434a",
    ribs: "#3d434a",
  },
};

function fmtNum(n, digits) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return Number(n).toLocaleString("it-IT", {
    minimumFractionDigits: digits == null ? 0 : digits,
    maximumFractionDigits: digits == null ? 1 : digits,
  });
}

function binWheel(cx, cy) {
  return (
    '<g class="prod-bin-wheel">' +
    '<circle cx="' +
    cx +
    '" cy="' +
    cy +
    '" r="7.2" fill="#141414"/>' +
    '<circle cx="' +
    cx +
    '" cy="' +
    cy +
    '" r="5.2" fill="#252525"/>' +
    '<circle cx="' +
    cx +
    '" cy="' +
    cy +
    '" r="2.1" fill="#4a4a4a"/>' +
    "</g>"
  );
}

function bagDefs(uid) {
  return (
    '<radialGradient id="' +
    uid +
    'BagFill" cx="26%" cy="38%" r="68%">' +
    '<stop offset="0%" stop-color="#525252"/>' +
    '<stop offset="22%" stop-color="#222222"/>' +
    '<stop offset="55%" stop-color="#0c0c0c"/>' +
    '<stop offset="100%" stop-color="#010101"/>' +
    "</radialGradient>" +
    '<linearGradient id="' +
    uid +
    'BagShine" x1="0%" y1="0%" x2="100%" y2="80%">' +
    '<stop offset="0%" stop-color="rgba(255,255,255,0.72)"/>' +
    '<stop offset="35%" stop-color="rgba(255,255,255,0.12)"/>' +
    '<stop offset="100%" stop-color="rgba(255,255,255,0)"/>' +
    "</linearGradient>"
  );
}

function realisticSingleBag(uid) {
  return (
    '<g class="prod-bag">' +
    '<path d="M34 68 C30.5 65.5 29 61 29.5 56.5 C28.5 53 29.5 49.5 32 47 C34 44.8 36.5 44 39 45.2 C40.5 42.8 43 41.8 45.5 42.5 C47.2 41.2 49.5 40.8 51.5 41.5 C53.8 41 56.2 41.8 58.2 43.2 C60.8 42.2 63.2 43 65 45.2 C67.5 48 68.5 52 68 56.5 C68.8 61 66.5 65 62.5 68 C65 69.8 58 70.8 50 71 C42 70.8 35 69.5 34 68 Z" fill="url(#' +
    uid +
    'BagFill)"/>' +
    '<path d="M37 61 C39 55.5 43 52.5 50 52 C57 52.5 61 56 62 61 C59.5 64.5 52 65.5 45 64 C40 62.5 37 64 37 61 Z" fill="rgba(0,0,0,0.18)"/>' +
    '<path d="M41 48.5 C44 46 47.5 45.5 50.5 46 C53.5 45.5 56.5 46.5 58.5 48.5" fill="none" stroke="rgba(0,0,0,0.45)" stroke-width="0.55" stroke-linecap="round"/>' +
    '<path d="M35 58 C38 54 42 51.5 47 50.5 C52 51 56 54 58 58" fill="none" stroke="rgba(0,0,0,0.38)" stroke-width="0.5" stroke-linecap="round"/>' +
    '<path d="M65 57 C62 53 58 51 54 51 C50 50.5 46 52 43 55" fill="none" stroke="rgba(0,0,0,0.42)" stroke-width="0.48" stroke-linecap="round"/>' +
    '<path d="M38 52 L42 58 L46 54 L50 59 L54 53 L58 58 L62 52" fill="none" stroke="rgba(255,255,255,0.22)" stroke-width="0.42" stroke-linecap="round" stroke-linejoin="round"/>' +
    '<path d="M33 60 C36 56 40 54 44 55" fill="none" stroke="rgba(255,255,255,0.35)" stroke-width="0.38" stroke-linecap="round"/>' +
    '<path d="M67 59 C64 55 60 53 56 54" fill="none" stroke="rgba(255,255,255,0.28)" stroke-width="0.35" stroke-linecap="round"/>' +
    '<path d="M44 47 C46 50 48 53 50 55 C52 53 54 50 56 47" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="0.4" stroke-linecap="round"/>' +
    '<path d="M36 54 C38 50 41 48 44 49" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="0.32" stroke-linecap="round"/>' +
    '<path d="M64 53 C62 49 59 47.5 56 48.5" fill="none" stroke="rgba(255,255,255,0.32)" stroke-width="0.3" stroke-linecap="round"/>' +
    '<path d="M39 56 C41 53 43 51.5 45 52.5" fill="none" stroke="rgba(0,0,0,0.55)" stroke-width="0.35" stroke-linecap="round"/>' +
    '<path d="M61 55 C59 52 57 51 55 51.8" fill="none" stroke="rgba(0,0,0,0.5)" stroke-width="0.32" stroke-linecap="round"/>' +
    '<path d="M47 44 C48.5 46.5 49.5 49 50 51.5 C50.5 49 51.5 46.5 53 44" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="0.38" stroke-linecap="round"/>' +
    '<path d="M32 57 C34 54 36 52.5 38 53" fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="0.28" stroke-linecap="round"/>' +
    '<path d="M68 56 C66 53 64 52 62 52.5" fill="none" stroke="rgba(0,0,0,0.35)" stroke-width="0.28" stroke-linecap="round"/>' +
    '<path d="M40 45 C42 43.5 44 43 46 43.8" fill="none" stroke="rgba(255,255,255,0.45)" stroke-width="0.3" stroke-linecap="round"/>' +
    '<path d="M60 44.5 C58 43.2 56 42.8 54 43.5" fill="none" stroke="rgba(255,255,255,0.38)" stroke-width="0.28" stroke-linecap="round"/>' +
    '<path d="M37 44 C35.5 42.5 35 41.2 36 40.2 C37.2 40.8 38.2 42 39 43.5" fill="none" stroke="rgba(255,255,255,0.2)" stroke-width="0.35" stroke-linecap="round"/>' +
    '<path d="M38 43 C36.5 41.5 36.2 40 37.5 39.2 C38.5 40 39.5 41.5 40.5 42.8" fill="none" stroke="rgba(0,0,0,0.4)" stroke-width="0.32" stroke-linecap="round"/>' +
    '<path d="M42 42.5 C41 41 40.5 39.8 41.5 39 C42.5 39.8 43.5 41 44.2 42.2" fill="none" stroke="rgba(255,255,255,0.3)" stroke-width="0.28" stroke-linecap="round"/>' +
    '<ellipse cx="43" cy="52" rx="5.5" ry="4" fill="url(#' +
    uid +
    'BagShine)" opacity="0.75"/>' +
    '<ellipse cx="57" cy="54" rx="3.5" ry="2.5" fill="rgba(255,255,255,0.08)"/>' +
    '<path d="M52 42 C53.5 40.8 55 40.5 56.5 41.2 C55.8 42 54.5 42.5 53 42.8" fill="rgba(0,0,0,0.35)"/>' +
    '<path d="M36.5 41.5 C37.5 40.5 39 40 40.5 40.6 C39.5 41.5 38 42 36.8 42.5 Z" fill="#060606"/>' +
    '<path d="M39 41 C40 40.2 41.2 40 42.2 40.5 C41.2 41.2 40 41.5 39 41 Z" fill="#030303"/>' +
    '<ellipse cx="41" cy="40.2" rx="2.2" ry="1.7" fill="#020202"/>' +
    '<path d="M40 39.2 C40.5 38.2 41.2 37.8 41.8 38.2" fill="none" stroke="rgba(255,255,255,0.12)" stroke-width="0.35" stroke-linecap="round"/>' +
    "</g>"
  );
}

/**
 * @param {number} comune
 * @param {number} italia
 * @param {number|null|undefined} regione
 * @param {"total"|"ind"} kind
 */
export function prodBinMeasureSvg(comune, italia, regione, kind) {
  const theme = PROD_BIN_THEMES[kind === "ind" ? "ind" : "total"] || PROD_BIN_THEMES.total;
  prodBinSvgSeq += 1;
  const uid = "prodBin" + prodBinSvgSeq;
  const vals = [comune, italia];
  if (regione != null) vals.push(regione);
  const minVal = Math.min.apply(null, vals) * 0.9;
  const maxVal = Math.max.apply(null, vals) * 1.08;
  const span = maxVal - minVal || 1;
  const stripX = 50;
  const stripTop = 78;
  const stripBot = 128;

  function yPos(v) {
    return stripBot - ((v - minVal) / span) * (stripBot - stripTop);
  }

  const marks = [{ v: comune, kind: "com" }];
  marks.push({ v: italia, kind: "it" });
  if (regione != null) marks.push({ v: regione, kind: "reg" });
  marks.sort(function (a, b) {
    return a.v - b.v;
  });
  marks.forEach(function (m, i) {
    m.y = yPos(m.v);
    m.side = i % 2 === 0 ? "left" : "right";
  });
  for (let i = 1; i < marks.length; i += 1) {
    if (Math.abs(marks[i].y - marks[i - 1].y) < 13 && marks[i].side === marks[i - 1].side) {
      marks[i].side = marks[i - 1].side === "left" ? "right" : "left";
    }
  }

  function scaleMark(m) {
    const num = fmtNum(m.v, 0);
    const y = m.y;
    const left = m.side === "left";
    const pillW = 17;
    const pillH = 9.5;
    const gap = 4;
    const pillX = left ? stripX - gap - pillW : stripX + gap;
    const pillY = y - pillH / 2;
    const colors = PROD_SCALE_COLORS[m.kind] || PROD_SCALE_COLORS.it;
    const dot = colors.fill;
    const pillFill = colors.fill;
    const textFill = colors.text;
    const leaderX1 = left ? pillX + pillW : pillX;
    const leaderX2 = stripX;
    return (
      '<circle cx="' +
      stripX +
      '" cy="' +
      y +
      '" r="2.8" fill="' +
      dot +
      '" stroke="rgba(255,255,255,0.9)" stroke-width="1"/>' +
      '<line x1="' +
      leaderX1 +
      '" y1="' +
      y +
      '" x2="' +
      leaderX2 +
      '" y2="' +
      y +
      '" stroke="' +
      dot +
      '" stroke-width="0.6" opacity="0.55"/>' +
      '<rect x="' +
      pillX +
      '" y="' +
      pillY +
      '" width="' +
      pillW +
      '" height="' +
      pillH +
      '" rx="2.8" fill="' +
      pillFill +
      '" stroke="rgba(20,32,24,0.1)" stroke-width="0.4"/>' +
      '<text x="' +
      (pillX + pillW / 2) +
      '" y="' +
      (y + 2.8) +
      '" text-anchor="middle" fill="' +
      textFill +
      '" font-size="6.8" font-weight="800" font-family="system-ui,sans-serif">' +
      num +
      "</text>"
    );
  }

  let scaleMarks = "";
  marks.forEach(function (m) {
    scaleMarks += scaleMark(m);
  });

  return (
    '<svg class="prod-bin-svg" viewBox="0 34 100 127" preserveAspectRatio="xMidYMin meet" aria-hidden="true">' +
    "<defs>" +
    '<linearGradient id="' +
    uid +
    'Bin" x1="0%" y1="0%" x2="100%" y2="0%">' +
    '<stop offset="0%" stop-color="' +
    theme.gradL +
    '"/>' +
    '<stop offset="18%" stop-color="' +
    theme.gradM +
    '"/>' +
    '<stop offset="82%" stop-color="' +
    theme.gradM +
    '"/>' +
    '<stop offset="100%" stop-color="' +
    theme.gradR +
    '"/>' +
    "</linearGradient>" +
    '<linearGradient id="' +
    uid +
    'BinShade" x1="0%" y1="0%" x2="100%" y2="0%">' +
    '<stop offset="0%" stop-color="rgba(0,0,0,0.16)"/>' +
    '<stop offset="50%" stop-color="rgba(0,0,0,0)"/>' +
    '<stop offset="100%" stop-color="rgba(0,0,0,0.14)"/>' +
    "</linearGradient>" +
    bagDefs(uid) +
    "</defs>" +
    realisticSingleBag(uid) +
    '<path d="' +
    BODY_PATH +
    '" fill="url(#' +
    uid +
    'Bin)"/>' +
    '<path d="' +
    BODY_PATH +
    '" fill="url(#' +
    uid +
    'BinShade)"/>' +
    '<line x1="' +
    stripX +
    '" y1="' +
    stripTop +
    '" x2="' +
    stripX +
    '" y2="' +
    stripBot +
    '" stroke="rgba(255,255,255,0.72)" stroke-width="1.1" stroke-linecap="round"/>' +
    '<circle cx="' +
    stripX +
    '" cy="' +
    stripTop +
    '" r="1.1" fill="rgba(255,255,255,0.55)"/>' +
    '<circle cx="' +
    stripX +
    '" cy="' +
    stripBot +
    '" r="1.1" fill="rgba(255,255,255,0.55)"/>' +
    scaleMarks +
    '<ellipse cx="50" cy="67" rx="31" ry="4.2" fill="' +
    theme.rim +
    '"/>' +
    '<path d="M16 63 L84 63 L82 70 L18 70 Z" fill="' +
    theme.rimDark +
    '"/>' +
    '<rect x="18" y="59" width="64" height="5" rx="1.2" fill="' +
    theme.rimTop +
    '"/>' +
    '<g opacity="0.55">' +
    '<rect x="24" y="70" width="2" height="7" rx="0.8" fill="' +
    theme.ribs +
    '"/>' +
    '<rect x="32" y="70" width="2" height="7" rx="0.8" fill="' +
    theme.ribs +
    '"/>' +
    '<rect x="66" y="70" width="2" height="7" rx="0.8" fill="' +
    theme.ribs +
    '"/>' +
    '<rect x="74" y="70" width="2" height="7" rx="0.8" fill="' +
    theme.ribs +
    '"/>' +
    "</g>" +
    binWheel(27, 153) +
    binWheel(73, 153) +
    "</svg>"
  );
}

function pctVsOne(value, median, label) {
  if (value == null || median == null || median <= 0) return "";
  const pctVs = ((value - median) / median) * 100;
  const absPct = Math.round(Math.abs(pctVs));
  if (Math.abs(pctVs) < 2) return "in linea con " + label;
  if (pctVs > 0) return "+" + absPct + "% vs " + label;
  return "−" + absPct + "% vs " + label;
}

export function prodPctVsMediansHint(value, medianIt, medianReg, regName) {
  const it = pctVsOne(value, medianIt, "Italia");
  const reg = pctVsOne(value, medianReg, regName || "regione");
  const parts = [];
  if (it) parts.push(it);
  if (reg) parts.push(reg);
  if (!parts.length) return "";
  const joined = parts.join(" · ");
  return joined.charAt(0).toUpperCase() + joined.slice(1);
}

/**
 * @param {object} rec
 * @param {object} baselines
 * @returns {{ regione: string, bins: Array<{ kind: string, label: string, value: number, medianIt: number, medianReg: number|null, hint: string }> }}
 */
export function resolveProdBins(rec, baselines) {
  const b = baselines || {};
  const medRu = b.kg_ru_ab_median;
  const medInd = b.kg_ind_ab_median;
  const regione = ((rec && rec.regione) || "").trim();
  const regBase =
    (b.by_regione && regione && b.by_regione[regione]) || null;
  const medRuReg = regBase && regBase.kg_ru_ab_median;
  const medIndReg = regBase && regBase.kg_ind_ab_median;
  const ru = rec && rec.kg_ru_ab;
  const ind = rec && rec.kg_ind_ab;

  const bins = [];
  function push(kind, value, medianIt, medianReg) {
    if (value == null || medianIt == null) return;
    const meta = PROD_BIN_KINDS[kind] || PROD_BIN_KINDS.total;
    bins.push({
      kind: kind,
      label: meta.label,
      value: Number(value),
      medianIt: Number(medianIt),
      medianReg: medianReg != null ? Number(medianReg) : null,
      hint: prodPctVsMediansHint(value, medianIt, medianReg, regione),
    });
  }
  push("total", ru, medRu, medRuReg);
  push("ind", ind, medInd, medIndReg);
  return { regione: regione, bins: bins };
}

export function resetProdBinSvgSeq() {
  prodBinSvgSeq = 0;
}
