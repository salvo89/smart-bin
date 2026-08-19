import { initIosBar } from "./shared/ios-bar.js";

const LAYER_DEFS = {
  rd: {
    label: "Raccolta differenziata",
    unit: "%",
    digits: 1,
    fmt: (v) => fmtNum(v, 1) + "%",
    // Avoid near-white fills that vanish against map bg / light strokes.
    colors: ["#c0392b", "#e0b83a", "#2a7a58", "#1a4a36"],
    quantile: true,
  },
  co: {
    label: "Costo gestione",
    unit: "€/ab·anno",
    digits: 0,
    mapUnit: true,
    fmt: (v) => fmtNum(v, 0) + " €/ab·anno",
    // Was #e8f4ec — too close to map bg #eef3f0 and old region stroke.
    colors: ["#c5ddd0", "#7eb69a", "#2a7a58", "#1a4a36"],
    quantile: true,
  },
  kru: {
    label: "Rifiuto urbano",
    unit: "kg/ab·anno",
    digits: 0,
    mapUnit: true,
    fmt: (v) => fmtNum(v, 0) + " kg/ab·anno",
    colors: ["#c5ddd0", "#7eb69a", "#2a7a58", "#1a4a36"],
    quantile: true,
  },
  kin: {
    label: "Indifferenziato",
    unit: "kg/ab·anno",
    digits: 0,
    mapUnit: true,
    fmt: (v) => fmtNum(v, 0) + " kg/ab·anno",
    colors: ["#2a7a58", "#e0b83a", "#d4845a", "#a33"],
    quantile: true,
  },
  drd: {
    label: "Variazione RD 2022–2024",
    unit: "%",
    digits: 1,
    fmt: (v) => (v > 0 ? "+" : "") + fmtNum(v, 1) + "%",
    // Was #f0f0f0 — conflicted with light region borders and map bg.
    colors: ["#a33", "#cfd8d3", "#1f5c42"],
    quantile: true,
  },
  pop: {
    label: "Popolazione",
    unit: "abitanti/km²",
    digits: 0,
    mode: "bubbles",
    valueKey: "dens",
    sizeKey: "pop",
    fmt: (v) => fmtNum(v, 0) + " abitanti/km²",
    colors: ["#d9e6f2", "#7fa3c4", "#3a6a94", "#1c3d5c"],
    quantile: true,
  },
};

const LAYER_ORDER = ["rd", "co", "kru", "kin", "drd", "pop"];
const SWIPE_ARM_PX = 12;
const SWIPE_HORIZ_RATIO = 1.2;
const SLIDE_MS = 820;
const AUTOPLAY_MS = 4200;
const AUTOPLAY_KEY = "escilo-map-autoplay";
const PANEL_PILLS = [
  ["co", "Costo", (v) => fmtNum(v, 0) + " €"],
  ["kin", "Indifferenziato", (v) => fmtNum(v, 0) + " kg"],
  ["kru", "Rifiuto urbano", (v) => fmtNum(v, 0) + " kg"],
  ["drd", "Trend 2022–24", (v) => (v > 0 ? "+" : "") + fmtNum(v, 1) + "%"],
];

const HINT = {
  macro: "Clicca un’area per le regioni · scorri per cambiare indicatore.",
  region: "Clicca una regione per le province · scorri per cambiare indicatore.",
  focus: "Clicca una provincia per i dettagli · scorri per cambiare indicatore.",
};

const MACRO_LABEL = { nord: "Nord", centro: "Centro", sud: "Sud" };

const L = window.L;

let map;
let geoLayer;
let labelLayer;
let meta = null;
let macroGeo = null;
let regioniGeo = null;
let provinceGeo = null;
/** All provinces — fixed national palette (min/max) at every zoom. */
let scaleFeatures = [];
let activeLayer = "rd";
let view = { level: "macro", macro: null, region: null };
let currentFeatures = [];
let selectedFeature = null;
let colorFn = null;
let swipe = null;
let suppressClickUntil = 0;
let slideToken = 0;
let slideTimer = 0;
let autoplayTimer = 0;
let autoplayOn = true;
let sheetDrag = null;
let sheetSnapToken = 0;

function $(id) {
  return document.getElementById(id);
}

function fmtNum(n, digits) {
  if (n == null || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("it-IT", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function fmtPop(n) {
  if (n == null) return "—";
  return Number(n).toLocaleString("it-IT");
}

function fmtPopCompact(n) {
  if (n == null || Number.isNaN(n)) return "—";
  const v = Number(n);
  if (v >= 1e6) return fmtNum(v / 1e6, 1) + " M";
  if (v >= 1e4) return fmtNum(v / 1e3, 0) + " mila";
  return fmtPop(v);
}

function layerValue(props, key) {
  if (!props) return null;
  const def = LAYER_DEFS[key];
  const field = (def && def.valueKey) || key;
  const v = props[field];
  return v == null || Number.isNaN(Number(v)) ? null : Number(v);
}

function layerSizeValue(props, key) {
  if (!props) return null;
  const def = LAYER_DEFS[key];
  const field = (def && def.sizeKey) || null;
  if (!field) return null;
  const v = props[field];
  return v == null || Number.isNaN(Number(v)) ? null : Number(v);
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function quantileBreaks(vals, n) {
  if (!vals.length) return [];
  const breaks = [];
  for (let i = 1; i < n; i += 1) {
    const idx = Math.floor((vals.length * i) / n);
    breaks.push(vals[Math.min(idx, vals.length - 1)]);
  }
  return breaks;
}

function scaleValues(key) {
  return scaleFeatures
    .map((f) => layerValue(f.properties, key))
    .filter((v) => v != null)
    .sort((a, b) => a - b);
}

function makeColorFn(key) {
  const def = LAYER_DEFS[key];
  const vals = scaleValues(key);
  if (!vals.length) return () => "#b7c9be";

  const breaks = def.quantile ? quantileBreaks(vals, def.colors.length) : def.breaks;
  const colors = def.colors;

  return (value) => {
    if (value == null || Number.isNaN(value)) return "#b7c9be";
    if (def.diverging) {
      if (value < breaks[0]) return colors[0];
      if (value > breaks[breaks.length - 1]) return colors[colors.length - 1];
      return colors[1];
    }
    for (let i = breaks.length - 1; i >= 0; i -= 1) {
      if (value >= breaks[i]) return colors[Math.min(i + 1, colors.length - 1)];
    }
    return colors[0];
  };
}

function fillLuminance(hex) {
  const h = String(hex || "").replace("#", "");
  if (h.length !== 6) return 0.5;
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255;
}

/** Stroke that stays visible against the fill (and map bg) at every zoom. */
function strokeForFill(fill) {
  const lum = fillLuminance(fill);
  if (view.level === "macro") {
    // Dark greens in the palette (#1a4a36) must not share the old fixed dark stroke.
    return {
      color: lum > 0.42 ? "#142018" : "#f3faf6",
      weight: 2,
      opacity: 1,
    };
  }
  if (view.level === "focus") {
    return {
      color: lum > 0.42 ? "#1a4a36" : "#f3faf6",
      weight: 1.45,
      opacity: 1,
    };
  }
  // Regions: light fills (#e8f4ec, #f0f0f0) used to match the #eef3f0 separator.
  return {
    color: lum > 0.55 ? "#1a4a36" : "#f7fbf8",
    weight: 1.25,
    opacity: 1,
  };
}

function styleFeature(feature) {
  const p = feature.properties || {};
  const def = LAYER_DEFS[activeLayer];
  if (def && def.mode === "bubbles" && view.level !== "focus") {
    const stroke = strokeForFill("#d7e2db");
    return {
      fillColor: "#d7e2db",
      fillOpacity: 0.72,
      color: stroke.color,
      weight: stroke.weight,
      opacity: 0.85,
    };
  }
  const val = layerValue(p, activeLayer);
  const fill = colorFn(val);
  const stroke = strokeForFill(fill);
  return {
    fillColor: fill,
    fillOpacity: val == null ? 0.45 : 1,
    color: stroke.color,
    weight: stroke.weight,
    opacity: stroke.opacity,
  };
}

function inLabelHtml(p) {
  const def = LAYER_DEFS[activeLayer];
  if (def.mode === "bubbles") {
    const pop = layerSizeValue(p, activeLayer);
    const dens = layerValue(p, activeLayer);
    const fill = colorFn(dens);
    const lum = fillLuminance(fill);
    const color = lum > 0.55 ? "#142018" : "#ffffff";
    const shadow =
      lum > 0.55
        ? "0 0 6px rgba(255,255,255,0.85)"
        : "0 1px 2px rgba(20,40,30,0.55)";
    return `<div class="map-bubble-label" style="color:${color};text-shadow:${shadow}">${escapeHtml(
      pop == null ? "—" : fmtPopCompact(pop)
    )}</div>`;
  }
  const val = layerValue(p, activeLayer);
  const lum = fillLuminance(colorFn(val));
  const color = lum > 0.55 ? "#142018" : "#ffffff";
  const shadow =
    lum > 0.55
      ? "0 0 6px rgba(255,255,255,0.9), 0 1px 2px rgba(255,255,255,0.7)"
      : "0 1px 2px rgba(20,40,30,0.7), 0 0 8px rgba(20,40,30,0.45)";
  const style = `color:${color};text-shadow:${shadow}`;
  if (val == null) {
    return `<div class="map-inlabel" style="${style}">—</div>`;
  }
  if (def.mapUnit) {
    return `<div class="map-inlabel is-stack" style="${style}"><span class="map-inlabel-num">${escapeHtml(fmtNum(val, def.digits))}</span><span class="map-inlabel-unit">${escapeHtml(def.unit)}</span></div>`;
  }
  return `<div class="map-inlabel" style="${style}">${escapeHtml(def.fmt(val))}</div>`;
}

/** Geographic centroid of the largest outer ring (keeps Sud inland, not in the sea). */
function featureLabelLatLng(feature) {
  const geom = feature && feature.geometry;
  if (!geom || !geom.coordinates) return null;
  const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates;
  let bestA = -1;
  let best = null;
  for (const poly of polys) {
    const ring = poly && poly[0];
    if (!ring || ring.length < 3) continue;
    let a = 0;
    let cx = 0;
    let cy = 0;
    for (let i = 0; i < ring.length - 1; i += 1) {
      const x1 = ring[i][0];
      const y1 = ring[i][1];
      const x2 = ring[i + 1][0];
      const y2 = ring[i + 1][1];
      const f = x1 * y2 - x2 * y1;
      a += f;
      cx += (x1 + x2) * f;
      cy += (y1 + y2) * f;
    }
    const abs = Math.abs(a);
    if (abs > bestA && abs > 1e-8) {
      bestA = abs;
      best = [cy / (3 * a), cx / (3 * a)];
    }
  }
  return best ? L.latLng(best[0], best[1]) : null;
}

function tooltipHtml(p) {
  const def = LAYER_DEFS[activeLayer];
  let html = `<strong>${escapeHtml(p.n || "—")}</strong>`;
  if (def.mode === "bubbles") {
    const pop = layerSizeValue(p, activeLayer);
    const dens = layerValue(p, activeLayer);
    if (pop != null) html += `<br>${fmtPop(pop)} abitanti`;
    if (dens != null) html += `<br>${fmtNum(dens, 0)} abitanti/km²`;
  } else {
    const val = layerValue(p, activeLayer);
    if (val != null) html += `<br>${def.fmt(val)}`;
  }
  if (p.nc) html += `<br>${fmtPop(p.nc)} com.`;
  return html;
}

function blurMapFocus() {
  const el = document.activeElement;
  if (el && el !== document.body && typeof el.blur === "function") el.blur();
  const mapEl = $("map");
  if (mapEl && typeof mapEl.blur === "function") mapEl.blur();
}

function disablePathFocus(layer) {
  const el = layer && layer.getElement && layer.getElement();
  if (!el || !el.setAttribute) return;
  el.setAttribute("tabindex", "-1");
  if (el.tagName === "path" || el.tagName === "PATH") {
    el.setAttribute("focusable", "false");
  }
}

function bindFeature(feature, layer) {
  if (view.level === "region" || view.level === "focus") {
    layer.bindTooltip(tooltipHtml(feature.properties || {}), {
      sticky: true,
      direction: "top",
      className: "map-tip",
      opacity: 0.96,
    });
  }
  layer.on("add", () => disablePathFocus(layer));
  const handlers = {
    click: (e) => {
      disablePathFocus(e.target);
      const t = e.originalEvent && e.originalEvent.target;
      if (t && typeof t.blur === "function") t.blur();
      blurMapFocus();
      onFeatureClick(feature, layer);
    },
  };
  if (window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
    handlers.mouseover = (e) => {
      const stroke = strokeForFill(colorFn(layerValue(feature.properties || {}, activeLayer)));
      e.target.setStyle({
        weight: stroke.weight + (view.level === "region" ? 0.9 : 1),
        opacity: 1,
      });
      e.target.bringToFront();
    };
    handlers.mouseout = (e) => {
      geoLayer.resetStyle(e.target);
    };
  }
  layer.on(handlers);
}

function clearLabels() {
  if (labelLayer) {
    map.removeLayer(labelLayer);
    labelLayer = null;
  }
}

function maxPopForBubbles() {
  let max = 0;
  for (const f of currentFeatures) {
    const pop = f.properties && f.properties.pop;
    if (pop != null && pop > max) max = pop;
  }
  return max || 1;
}

function bubbleDiameterPx(pop) {
  const max = maxPopForBubbles();
  const t = Math.sqrt(Math.max(Number(pop) || 0, 0) / max);
  const compact = view.level === "region";
  const min = compact ? 22 : view.level === "focus" ? 56 : 36;
  const maxPx = compact ? 54 : view.level === "focus" ? 96 : 84;
  return Math.round(min + t * (maxPx - min));
}

function placeValueLabels() {
  clearLabels();
  if (view.level !== "macro" && view.level !== "region") {
    return;
  }
  labelLayer = L.layerGroup().addTo(map);
  const def = LAYER_DEFS[activeLayer];
  const bubbles = def && def.mode === "bubbles";
  const compact = view.level === "region";
  for (const f of currentFeatures) {
    const p = f.properties || {};
    const latlng = featureLabelLatLng(f);
    if (!latlng) continue;
    if (bubbles) {
      const pop = layerSizeValue(p, activeLayer);
      const dens = layerValue(p, activeLayer);
      if (pop == null) continue;
      const d = bubbleDiameterPx(pop);
      const fill = colorFn(dens);
      L.marker(latlng, {
        icon: L.divIcon({
          className: "map-bubble-wrap" + (compact ? " is-compact" : ""),
          html:
            `<div class="map-bubble" style="width:${d}px;height:${d}px;background:${fill};border-color:${
              fillLuminance(fill) > 0.55 ? "#1a4a36" : "#f7fbf8"
            }">${inLabelHtml(p)}</div>`,
          iconSize: [d, d],
          iconAnchor: [d / 2, d / 2],
        }),
        interactive: false,
        keyboard: false,
        zIndexOffset: 700,
      }).addTo(labelLayer);
      continue;
    }
    const stacked = !!def.mapUnit;
    const size = compact
      ? stacked
        ? [92, 34]
        : [76, 28]
      : stacked
        ? [108, 40]
        : [88, 32];
    L.marker(latlng, {
      icon: L.divIcon({
        className: "map-inlabel-wrap" + (compact ? " is-compact" : ""),
        html: inLabelHtml(p),
        iconSize: size,
        iconAnchor: [size[0] / 2, size[1] / 2],
      }),
      interactive: false,
      keyboard: false,
      zIndexOffset: 700,
    }).addTo(labelLayer);
  }
}

function vsParts(val, key) {
  const it = meta && meta.italy && meta.italy[key];
  if (val == null || it == null) return { text: "", tone: "eq" };
  const d = val - it;
  const betterUp = key === "rd" || key === "drd";
  const betterDown = key === "co" || key === "kru" || key === "kin";
  if (key === "pop") {
    if (Math.abs(d) < 1) return { text: "come l’Italia", tone: "eq" };
    const pct = (100 * d) / it;
    const sign = pct > 0 ? "+" : "−";
    return {
      text: sign + fmtNum(Math.abs(pct), 1) + "% vs Italia",
      tone: "neutral",
    };
  }
  if (Math.abs(d) < 0.05) return { text: "come l’Italia", tone: "eq" };
  let tone = "neutral";
  if (betterUp) tone = d > 0 ? "good" : "bad";
  else if (betterDown) tone = d < 0 ? "good" : "bad";
  const sign = d > 0 ? "+" : "−";
  const abs = Math.abs(d);
  let body =
    key === "rd" || key === "drd"
      ? sign + fmtNum(abs, 1) + "%"
      : key === "dens"
        ? sign + fmtNum(abs, 0) + " abitanti/km²"
        : key === "co"
          ? sign + fmtNum(abs, 0) + " €"
          : sign + fmtNum(abs, 0) + " kg";
  return { text: body + " vs Italia", tone };
}

function vsSpan(val, key) {
  if (key === "pop" || key === "dens" || key === "km2") return "";
  const vs = vsParts(val, key);
  if (!vs.text) return "";
  return `<span class="map-vs is-${vs.tone}">${escapeHtml(vs.text)}</span>`;
}

function rowValue(p, key) {
  if (key === "dens") return p.dens == null ? null : Number(p.dens);
  if (key === "pop") return p.pop == null ? null : Number(p.pop);
  if (key === "km2") return p.km2 == null ? null : Number(p.km2);
  return layerValue(p, key);
}

function provinceRank(id, key, better) {
  if (!id) return null;
  const feats = ((provinceGeo && provinceGeo.features) || [])
    .map((f) => {
      const props = f.properties || {};
      return { id: props.id, v: rowValue(props, key) };
    })
    .filter((x) => x.id && x.v != null);
  feats.sort((a, b) => (better === "down" ? a.v - b.v : b.v - a.v));
  const i = feats.findIndex((x) => x.id === id);
  if (i < 0) return null;
  return { rank: i + 1, total: feats.length };
}

function rdHeroCopy(rd, rank, total) {
  if (rd == null) return { punch: "Dato non disponibile.", sub: "" };
  const vs = vsParts(rd, "rd");
  const it = meta && meta.italy && meta.italy.rd;
  const place = rank != null && total ? rank + "ª su " + total : "";
  const sub = place ? place + (vs.text ? " · " + vs.text : "") : vs.text;
  if (rank === 1) {
    return {
      punch: "1ª in Italia. Il riferimento nazionale.",
      sub: vs.text.replace(" vs Italia", "") + " sopra la media italiana",
    };
  }
  if (rank != null && rank <= 10) {
    return { punch: rank + "ª in Italia. Tra le migliori.", sub };
  }
  if (it != null && rd >= it) {
    return { punch: "Sopra la media italiana.", sub };
  }
  if (rd >= 65) {
    return { punch: "Oltre il 65%. Un passo dalla media.", sub };
  }
  if (it != null && it - rd <= 4) {
    return { punch: "A un soffio dalla media. Ce la fai.", sub };
  }
  if (rd >= 50) {
    return { punch: "In corsa. Ogni punto conta.", sub };
  }
  return { punch: "C’è da recuperare. Si può fare.", sub };
}

function voteMarkup(p) {
  const rd = rowValue(p, "rd");
  const circ = 2 * Math.PI * 48;
  const t = rd == null ? 0 : Math.max(0, Math.min(100, rd)) / 100;
  const ranked = provinceRank(p.id, "rd", "up");
  const copy = rdHeroCopy(rd, ranked && ranked.rank, ranked && ranked.total);
  const rdInt = rd == null ? "—" : fmtNum(rd, 0);
  const rdAria = rd == null ? "non disponibile" : fmtNum(rd, 1) + " percento";
  const pills = PANEL_PILLS.map(([key, label, fmt]) => {
    const val = rowValue(p, key);
    const vs = vsSpan(val, key);
    return (
      `<div class="map-pill">` +
      `<span class="map-pill-k">${escapeHtml(label)}</span>` +
      `<span class="map-pill-v">${escapeHtml(val == null ? "—" : fmt(val))}</span>` +
      (vs ? `<span class="map-pill-d">${vs}</span>` : "") +
      `</div>`
    );
  }).join("");
  const facts = [];
  if (p.pop != null) facts.push(fmtPop(p.pop) + " abitanti");
  if (p.dens != null) facts.push(fmtNum(p.dens, 0) + " abitanti/km²");
  if (p.km2 != null) facts.push(fmtPop(Math.round(p.km2)) + " km²");
  return (
    `<div class="map-vote">` +
    `<div class="map-vote-hero">` +
    `<svg class="map-vote-ring" viewBox="0 0 120 120" role="img" aria-label="Raccolta differenziata ${escapeHtml(rdAria)}">` +
    `<circle class="map-vote-track" cx="60" cy="60" r="48" fill="none" stroke-width="10"/>` +
    `<circle class="map-vote-arc" cx="60" cy="60" r="48" fill="none" stroke-width="10" stroke-linecap="round" transform="rotate(-90 60 60)" stroke-dasharray="${circ.toFixed(2)}" stroke-dashoffset="${(circ * (1 - t)).toFixed(2)}"/>` +
    `<text class="map-vote-num" x="60" y="58" text-anchor="middle">${escapeHtml(rdInt)}</text>` +
    `<text class="map-vote-pct" x="60" y="74" text-anchor="middle">%</text>` +
    `</svg>` +
    `<div>` +
    `<p class="map-vote-k">Raccolta differenziata</p>` +
    `<p class="map-vote-punch">${escapeHtml(copy.punch)}</p>` +
    (copy.sub ? `<p class="map-vote-sub">${escapeHtml(copy.sub)}</p>` : "") +
    `</div>` +
    `</div>` +
    `<div class="map-pills">${pills}</div>` +
    (facts.length
      ? `<p class="map-vote-facts">${escapeHtml(facts.join(" · "))}</p>`
      : "") +
    `</div>`
  );
}

function panelMetaText(p) {
  if (p.nc == null) return "";
  const n = Number(p.nc);
  return fmtPop(n) + (n === 1 ? " comune" : " comuni");
}

function renderPanel() {
  if (!selectedFeature) {
    applyPanelChrome();
    return;
  }
  const p = selectedFeature.properties || {};
  $("panelName").textContent = p.n || "—";
  $("panelMeta").textContent = panelMetaText(p);
  $("panelStats").innerHTML = voteMarkup(p);
  applyPanelChrome();
}

function resetSheetTransform() {
  const panel = $("mapPanel");
  const sheet = $("mapSheet");
  const scrim = $("panelScrim");
  if (panel) panel.classList.remove("is-dragging");
  if (sheet) {
    sheet.classList.remove("is-dragging", "is-snapping");
    sheet.style.removeProperty("transform");
    sheet.scrollTop = 0;
  }
  if (scrim) scrim.style.removeProperty("opacity");
}

function applyPanelChrome() {
  const panel = $("mapPanel");
  const sheet = $("mapSheet");
  if (!panel) return;
  const open = !!selectedFeature;
  panel.classList.toggle("is-open", open);
  panel.classList.toggle("is-sheet", open);
  if (sheet) sheet.hidden = !open;
  if (open) resetSheetTransform();
  document.documentElement.classList.toggle("is-map-sheet-open", open);
  if (open) {
    clearTimeout(autoplayTimer);
    autoplayTimer = 0;
  } else {
    scheduleAutoplay();
  }
}

function openPanel(feature) {
  sheetSnapToken += 1;
  sheetDrag = null;
  selectedFeature = feature;
  renderPanel();
  if (geoLayer) geoLayer.resetStyle();
  blurMapFocus();
}

function closePanel() {
  sheetSnapToken += 1;
  sheetDrag = null;
  selectedFeature = null;
  resetSheetTransform();
  applyPanelChrome();
  if (geoLayer) geoLayer.resetStyle();
  blurMapFocus();
}

function releaseSheetPointer(el, pointerId) {
  if (!el || pointerId == null) return;
  try {
    if (el.hasPointerCapture && el.hasPointerCapture(pointerId)) {
      el.releasePointerCapture(pointerId);
    }
  } catch {
    /* ignore */
  }
}

function bindSheetDrag() {
  const panel = $("mapPanel");
  const sheet = $("mapSheet");
  const scrim = $("panelScrim");
  if (!panel || !sheet) return;

  function offsetY(clientY, startY) {
    return Math.max(0, clientY - startY);
  }

  function finishSnap(dismiss, height) {
    const token = (sheetSnapToken += 1);
    panel.classList.remove("is-dragging");
    sheet.classList.remove("is-dragging");
    sheet.classList.add("is-snapping");
    if (dismiss) {
      sheet.style.transform = `translateY(${Math.ceil(height + 32)}px)`;
      if (scrim) scrim.style.opacity = "0";
    } else {
      sheet.style.transform = "translateY(0)";
      if (scrim) scrim.style.removeProperty("opacity");
    }
    const done = () => {
      if (token !== sheetSnapToken) return;
      sheet.classList.remove("is-snapping");
      if (dismiss) closePanel();
      else resetSheetTransform();
    };
    window.setTimeout(done, 300);
  }

  function applyDragY(clientY) {
    if (!sheetDrag) return;
    const y = offsetY(clientY, sheetDrag.y);
    sheetDrag.lastY = clientY;
    const h = sheet.getBoundingClientRect().height || 1;
    sheet.style.transform = `translateY(${y}px)`;
    if (scrim) scrim.style.opacity = String(Math.max(0, 1 - y / h));
  }

  function beginDrag() {
    if (!sheetDrag || sheetDrag.dragging) return;
    sheetDrag.dragging = true;
    sheet.scrollTop = 0;
    panel.classList.add("is-dragging");
    sheet.classList.add("is-dragging");
  }

  function onMove(e) {
    if (!sheetDrag || e.pointerId !== sheetDrag.id) return;
    const dy = e.clientY - sheetDrag.y;
    if (!sheetDrag.dragging) {
      if (dy > 0) beginDrag();
      else return;
    }
    if (!sheetDrag.dragging) return;
    if (e.cancelable) e.preventDefault();
    applyDragY(e.clientY);
  }

  function onEnd(e) {
    if (!sheetDrag || e.pointerId !== sheetDrag.id) return;
    const cur = sheetDrag;
    const clientY = e.clientY || cur.lastY;
    teardownDrag();
    if (!cur.dragging) return;
    const h = sheet.getBoundingClientRect().height || 1;
    const y = offsetY(clientY, cur.y);
    const threshold = Math.max(96, h * 0.2);
    finishSnap(y >= threshold, h);
  }

  function teardownDrag() {
    if (!sheetDrag) return;
    const id = sheetDrag.id;
    sheetDrag = null;
    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", onEnd);
    document.removeEventListener("pointercancel", onEnd);
    releaseSheetPointer(sheet, id);
  }

  sheet.addEventListener("pointerdown", (e) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    if (e.target.closest && e.target.closest(".map-sheet-x")) return;
    if (sheetDrag) teardownDrag();
    sheetDrag = {
      id: e.pointerId,
      y: e.clientY,
      lastY: e.clientY,
      dragging: false,
    };
    beginDrag();
    document.addEventListener("pointermove", onMove, { passive: false });
    document.addEventListener("pointerup", onEnd);
    document.addEventListener("pointercancel", onEnd);
  });
}

function renderLegendPicker() {
  const def = LAYER_DEFS[activeLayer];
  return `<p class="legend-step-label">${escapeHtml(def.label)}</p>`;
}

function legendEndpoints(key) {
  const def = LAYER_DEFS[key];
  const vals = scaleValues(key);
  if (!vals.length) return null;
  // Fixed-break diverging: label the palette thresholds, not local min/max.
  if (def.diverging && def.breaks && def.breaks.length && !def.quantile) {
    const lo = def.breaks[0];
    const hi = def.breaks[def.breaks.length - 1];
    return ["≤ " + def.fmt(lo), "≥ " + def.fmt(hi)];
  }
  return [def.fmt(vals[0]), def.fmt(vals[vals.length - 1])];
}

function updateLegend() {
  const def = LAYER_DEFS[activeLayer];
  const picker = $("legendPicker");
  const scale = $("legendScale");
  if (!picker || !scale) return;
  picker.innerHTML = renderLegendPicker();

  if (def.mode === "bubbles") {
    const ends = legendEndpoints(activeLayer);
    if (!ends) {
      scale.innerHTML = `<p class="legend-empty">Nessun dato</p>`;
    } else {
      const bar = def.colors.map((c) => `<span style="background:${c}"></span>`).join("");
      scale.innerHTML = `
        <div class="legend-bar">${bar}</div>
        <div class="legend-labels"><span>${escapeHtml(ends[0])}</span><span>${escapeHtml(ends[1])}</span></div>
      `;
    }
    updateCarouselDots();
    return;
  }

  const ends = legendEndpoints(activeLayer);
  if (!ends) {
    scale.innerHTML = `<p class="legend-empty">Nessun dato</p>`;
  } else {
    const bar = def.colors.map((c) => `<span style="background:${c}"></span>`).join("");
    scale.innerHTML = `
      <div class="legend-bar">${bar}</div>
      <div class="legend-labels"><span>${escapeHtml(ends[0])}</span><span>${escapeHtml(ends[1])}</span></div>
    `;
  }
  updateCarouselDots();
}

function updateCarouselDots() {
  document.querySelectorAll("#mapDots [data-layer]").forEach((btn) => {
    btn.setAttribute("aria-selected", btn.getAttribute("data-layer") === activeLayer ? "true" : "false");
  });
}

function setActiveLayer(key, dir = 0) {
  if (!LAYER_DEFS[key] || key === activeLayer) return;
  animateLayerChange(key, dir);
}

function cycleLayer(dir) {
  const i = LAYER_ORDER.indexOf(activeLayer);
  const next = LAYER_ORDER[(i + dir + LAYER_ORDER.length) % LAYER_ORDER.length];
  setActiveLayer(next, dir);
}

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function readAutoplayOn() {
  try {
    return localStorage.getItem(AUTOPLAY_KEY) !== "off";
  } catch {
    return true;
  }
}

function syncAutoplayButton() {
  const btn = $("btnAutoplay");
  if (!btn) return;
  btn.setAttribute("aria-pressed", autoplayOn ? "true" : "false");
  btn.setAttribute(
    "aria-label",
    autoplayOn ? "Ferma il cambio automatico" : "Avvia il cambio automatico"
  );
}

function setAutoplayOn(on) {
  autoplayOn = on;
  try {
    localStorage.setItem(AUTOPLAY_KEY, on ? "on" : "off");
  } catch {
    /* ignore */
  }
  syncAutoplayButton();
  if (on) scheduleAutoplay();
  else {
    clearTimeout(autoplayTimer);
    autoplayTimer = 0;
  }
}

function scheduleAutoplay() {
  clearTimeout(autoplayTimer);
  autoplayTimer = 0;
  if (!autoplayOn) return;
  const status = $("mapStatus");
  if (status && !status.hidden) return;
  if (selectedFeature) return;
  autoplayTimer = window.setTimeout(() => {
    cycleLayer(1);
  }, AUTOPLAY_MS);
}

function neighborKey(dir) {
  const i = LAYER_ORDER.indexOf(activeLayer);
  return LAYER_ORDER[(i + dir + LAYER_ORDER.length) % LAYER_ORDER.length];
}

function viewportWidth() {
  const vp = document.querySelector(".map-viewport");
  return (vp && vp.clientWidth) || 1;
}

function setTrackX(px) {
  const track = $("mapTrack");
  if (track) track.style.transform = `translate3d(${px}px, 0, 0)`;
}

function markSwiped() {
  const shell = document.querySelector(".map-shell");
  if (shell) shell.classList.add("is-swiped");
}

function makeOutgoingSlide(mapEl) {
  const rect = mapEl.getBoundingClientRect();
  const pane = mapEl.querySelector(".leaflet-map-pane");
  const slide = document.createElement("div");
  slide.className = "map-outgoing";
  slide.setAttribute("aria-hidden", "true");
  const stage = document.createElement("div");
  stage.className = "map-outgoing-stage leaflet-container";
  stage.style.width = `${Math.round(rect.width)}px`;
  stage.style.height = `${Math.round(rect.height)}px`;
  if (pane) {
    const clone = pane.cloneNode(true);
    clone.querySelectorAll("[id]").forEach((n) => n.removeAttribute("id"));
    clone.querySelectorAll(".leaflet-tooltip-pane, .leaflet-popup-pane").forEach((n) => n.remove());
    stage.appendChild(clone);
  }
  slide.appendChild(stage);
  return slide;
}

function finishLayerSlide() {
  slideToken += 1;
  if (slideTimer) {
    clearTimeout(slideTimer);
    slideTimer = 0;
  }
  const track = $("mapTrack");
  if (track) {
    track.style.transition = "none";
    track.classList.remove("is-sliding", "is-dragging");
    track.style.transform = "";
    track.querySelectorAll(".map-outgoing").forEach((el) => el.remove());
    track.style.transition = "";
  }
  if (map) {
    try {
      map.invalidateSize();
    } catch {
      /* ignore */
    }
  }
}

function prepareSlide(toKey, dir) {
  const mapEl = $("map");
  const track = $("mapTrack");
  if (!geoLayer || !mapEl || !track || !LAYER_DEFS[toKey]) return null;
  const fromKey = activeLayer;
  const outgoing = makeOutgoingSlide(mapEl);
  activeLayer = toKey;
  refreshStyles({ legend: false });
  track.classList.add("is-sliding");
  track.style.transition = "none";
  if (dir > 0) track.insertBefore(outgoing, mapEl);
  else track.appendChild(outgoing);
  try {
    map.invalidateSize();
  } catch {
    /* ignore */
  }
  const width = viewportWidth();
  return {
    track,
    fromKey,
    toKey,
    dir,
    width,
    startX: dir > 0 ? 0 : -width,
    endX: dir > 0 ? -width : 0,
  };
}

function dragX(dir, dx, width) {
  if (dir > 0) return Math.max(-width, Math.min(0, dx));
  return Math.max(-width, Math.min(0, -width + dx));
}

function settleSlide(prep, commit) {
  const token = (slideToken += 1);
  const track = prep.track;
  track.classList.remove("is-dragging");
  track.style.transition = "";
  setTrackX(commit ? prep.endX : prep.startX);
  const done = () => {
    if (token !== slideToken) return;
    if (!commit) {
      activeLayer = prep.fromKey;
      refreshStyles();
    } else {
      updateLegend();
      markSwiped();
    }
    finishLayerSlide();
    scheduleAutoplay();
  };
  track.addEventListener(
    "transitionend",
    (e) => {
      if (e.target !== track) return;
      if (e.propertyName && e.propertyName !== "transform") return;
      done();
    },
    { once: true }
  );
  slideTimer = window.setTimeout(done, SLIDE_MS + 80);
}

function animateLayerChange(key, dir) {
  clearTimeout(autoplayTimer);
  autoplayTimer = 0;
  swipe = null;
  finishLayerSlide();
  const token = (slideToken += 1);
  if (!geoLayer || !dir || prefersReducedMotion()) {
    activeLayer = key;
    refreshStyles();
    scheduleAutoplay();
    return;
  }

  const prep = prepareSlide(key, dir);
  if (!prep) {
    activeLayer = key;
    refreshStyles();
    scheduleAutoplay();
    return;
  }
  setTrackX(prep.startX);

  const done = () => {
    if (token !== slideToken) return;
    updateLegend();
    markSwiped();
    finishLayerSlide();
    scheduleAutoplay();
  };

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      if (token !== slideToken) return;
      prep.track.style.transition = "";
      setTrackX(prep.endX);
    });
  });

  prep.track.addEventListener(
    "transitionend",
    (e) => {
      if (e.target !== prep.track) return;
      if (e.propertyName && e.propertyName !== "transform") return;
      done();
    },
    { once: true }
  );
  slideTimer = window.setTimeout(done, SLIDE_MS + 80);
}

function swipeFromIgnored(el) {
  return Boolean(
    el &&
      el.closest &&
      el.closest(".map-nav, .map-panel, .map-status, a, button")
  );
}

function bindMapSwipe() {
  const shell = document.querySelector(".map-shell");
  if (!shell) return;

  shell.addEventListener("pointerdown", (e) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    if (swipeFromIgnored(e.target)) return;
    const status = $("mapStatus");
    if (status && !status.hidden) return;
    if (prefersReducedMotion()) return;
    clearTimeout(autoplayTimer);
    autoplayTimer = 0;
    swipe = {
      id: e.pointerId,
      x: e.clientX,
      y: e.clientY,
      t0: Date.now(),
      lastX: e.clientX,
      prep: null,
    };
    // Do not setPointerCapture here: on mouse it steals mouseup from Leaflet
    // paths and Nord/Centro/Sud clicks never fire. Capture only after swipe arms.
  });

  shell.addEventListener("pointermove", (e) => {
    if (!swipe || e.pointerId !== swipe.id) return;
    const dx = e.clientX - swipe.x;
    const dy = e.clientY - swipe.y;
    swipe.lastX = e.clientX;

    if (!swipe.prep) {
      if (Math.abs(dx) < SWIPE_ARM_PX && Math.abs(dy) < SWIPE_ARM_PX) return;
      if (Math.abs(dx) < Math.abs(dy) * SWIPE_HORIZ_RATIO) {
        swipe = null;
        scheduleAutoplay();
        return;
      }
      const dir = dx < 0 ? 1 : -1;
      finishLayerSlide();
      const prep = prepareSlide(neighborKey(dir), dir);
      if (!prep) {
        swipe = null;
        return;
      }
      prep.track.classList.add("is-dragging");
      setTrackX(prep.startX);
      swipe.prep = prep;
      suppressClickUntil = Date.now() + 800;
      try {
        shell.setPointerCapture(e.pointerId);
      } catch {
        /* ignore */
      }
    }

    setTrackX(dragX(swipe.prep.dir, e.clientX - swipe.x, swipe.prep.width));
  });

  function endSwipe(e) {
    if (!swipe || e.pointerId !== swipe.id) return;
    const cur = swipe;
    swipe = null;
    if (!cur.prep) {
      scheduleAutoplay();
      return;
    }
    const dx = (e.clientX || cur.lastX) - cur.x;
    const width = cur.prep.width;
    const x = dragX(cur.prep.dir, dx, width);
    const progress = cur.prep.dir > 0 ? -x / width : (x + width) / width;
    const dt = Math.max(1, Date.now() - cur.t0);
    const vx = dx / dt;
    const commit =
      progress > 0.18 ||
      (cur.prep.dir > 0 && vx < -0.4) ||
      (cur.prep.dir < 0 && vx > 0.4);
    suppressClickUntil = Date.now() + 400;
    settleSlide(cur.prep, commit);
  }

  shell.addEventListener("pointerup", endSwipe);
  shell.addEventListener("pointercancel", endSwipe);
  shell.addEventListener(
    "click",
    (e) => {
      if (Date.now() >= suppressClickUntil) return;
      e.preventDefault();
      e.stopImmediatePropagation();
    },
    true
  );
  shell.addEventListener("click", (e) => {
    const step = e.target.closest("[data-layer-step]");
    if (step) cycleLayer(Number(step.getAttribute("data-layer-step")));
  });
}

function macroLabel(id) {
  return MACRO_LABEL[id] || id || "";
}

function regionLabel(id) {
  const rec = ((meta && meta.regions) || []).find((r) => r.id === id);
  return rec ? rec.n : id || "";
}

function currentPlaceLabel() {
  if (view.level === "focus" && view.region) return regionLabel(view.region);
  if (view.level === "region" && view.macro) return macroLabel(view.macro);
  return "Italia";
}

function parentPlaceLabel() {
  if (view.level === "focus" && view.macro) return macroLabel(view.macro);
  if (view.level === "region") return "Italia";
  return "";
}

function goUpOneLevel() {
  if (view.level === "focus" && view.macro) {
    showRegions(view.macro).catch((err) => {
      console.error(err);
      setStatus("Impossibile caricare le regioni.", true);
    });
    return;
  }
  if (view.level === "region") showMacro();
}

function updateChrome() {
  const crumb = $("mapCrumb");
  if (!crumb) return;
  if (view.level === "macro") {
    crumb.innerHTML = "";
    crumb.hidden = true;
  } else {
    const parent = parentPlaceLabel();
    const label = parent ? `Torna a ${parent}` : "Indietro";
    crumb.innerHTML =
      `<button type="button" class="nav-arrow" data-to="up" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">` +
      `<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path fill="currentColor" d="M10.2 2.3a.9.9 0 0 1 0 1.3L6.8 7l3.4 3.4a.9.9 0 1 1-1.3 1.3l-4-4a.9.9 0 0 1 0-1.3l4-4a.9.9 0 0 1 1.3 0z"/></svg>` +
      `</button>` +
      `<span class="nav-here">${escapeHtml(currentPlaceLabel())}</span>`;
    crumb.hidden = false;
  }
  $("mapHint").textContent = HINT[view.level] || HINT.macro;
  updateLegend();
}

function setStatus(text, show) {
  const el = $("mapStatus");
  el.textContent = text;
  el.hidden = !show;
}

function ringAreaKm2(ring) {
  if (!ring || ring.length < 3) return 0;
  let area = 0;
  for (let i = 0; i < ring.length - 1; i += 1) {
    const lon1 = (ring[i][0] * Math.PI) / 180;
    const lat1 = (ring[i][1] * Math.PI) / 180;
    const lon2 = (ring[i + 1][0] * Math.PI) / 180;
    const lat2 = (ring[i + 1][1] * Math.PI) / 180;
    area += (lon2 - lon1) * (2 + Math.sin(lat1) + Math.sin(lat2));
  }
  return Math.abs((area * 6378137 * 6378137) / 2) / 1e6;
}

function featureAreaKm2(feature) {
  const geom = feature && feature.geometry;
  if (!geom || !geom.coordinates) return 0;
  const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates;
  let total = 0;
  for (const poly of polys) {
    if (!poly || !poly[0]) continue;
    total += ringAreaKm2(poly[0]);
    for (let i = 1; i < poly.length; i += 1) total -= ringAreaKm2(poly[i]);
  }
  return total;
}

/** Ensure km² / densità even if a cached geojson predates the build fields. */
function enrichPopDensity(fc) {
  if (!fc || !fc.features) return fc;
  for (const f of fc.features) {
    const p = f.properties || (f.properties = {});
    if (p.km2 == null) {
      const km2 = featureAreaKm2(f);
      if (km2 > 0) p.km2 = Math.round(km2 * 10) / 10;
    }
    if (p.pop != null && p.km2 > 0 && p.dens == null) {
      p.dens = Math.round((Number(p.pop) / p.km2) * 10) / 10;
    }
  }
  return fc;
}

function replaceLayer(geojson) {
  finishLayerSlide();
  if (geoLayer) {
    map.removeLayer(geoLayer);
    geoLayer = null;
  }
  clearLabels();
  selectedFeature = null;
  currentFeatures = geojson.features || [];
  colorFn = makeColorFn(activeLayer);
  geoLayer = L.geoJSON(geojson, {
    style: styleFeature,
    onEachFeature: bindFeature,
  }).addTo(map);
  placeValueLabels();
  const maxZoom =
    view.level === "macro" ? 6 : view.level === "region" ? 8 : 9;
  try {
    map.fitBounds(geoLayer.getBounds(), {
      padding: [28, 28],
      maxZoom,
    });
  } catch {
    /* ignore */
  }
  updateChrome();
}

async function showMacro() {
  view = { level: "macro", macro: null, region: null };
  closePanel();
  replaceLayer(macroGeo);
}

async function showRegions(macroId) {
  view = { level: "region", macro: macroId, region: null };
  closePanel();
  const feats = (regioniGeo.features || []).filter((f) => f.properties.macro === macroId);
  replaceLayer({ type: "FeatureCollection", features: feats });
}

function showRegionFocus(regionId) {
  const feats = regioniGeo.features || [];
  const hit = feats.find((f) => f.properties && f.properties.id === regionId);
  if (!hit) throw new Error("Regione sconosciuta");
  const macroId = hit.properties.macro;
  view = { level: "focus", macro: macroId, region: regionId };
  closePanel();
  const provs = ((provinceGeo && provinceGeo.features) || []).filter(
    (f) => f.properties && f.properties.rs === regionId
  );
  replaceLayer({
    type: "FeatureCollection",
    features: provs.length ? provs : [hit],
  });
}

function onFeatureClick(feature) {
  if (Date.now() < suppressClickUntil) return;
  const p = feature.properties || {};
  if (view.level === "macro") {
    showRegions(p.id).catch((err) => {
      console.error(err);
      setStatus("Impossibile caricare le regioni.", true);
    });
    return;
  }
  if (view.level === "region") {
    try {
      showRegionFocus(p.id);
    } catch (err) {
      console.error(err);
      setStatus("Impossibile caricare la regione.", true);
    }
    return;
  }
  if (view.level === "focus") {
    if (selectedFeature === feature) closePanel();
    else openPanel(feature);
  }
}

function refreshStyles(opts) {
  if (!geoLayer) return;
  colorFn = makeColorFn(activeLayer);
  geoLayer.eachLayer((layer) => {
    layer.setStyle(styleFeature(layer.feature));
    const tip = layer.getTooltip && layer.getTooltip();
    if (tip) tip.setContent(tooltipHtml(layer.feature.properties || {}));
  });
  if (view.level === "macro" || view.level === "region") {
    placeValueLabels();
  } else {
    clearLabels();
  }
  if (!opts || opts.legend !== false) updateLegend();
  if (selectedFeature) renderPanel();
}

async function applyDeepLink() {
  const q = new URLSearchParams(location.search);
  const regione = (q.get("regione") || "").trim();
  const macro = (q.get("macro") || "").trim();
  try {
    if (regione && (meta.regions || []).some((r) => r.id === regione)) {
      showRegionFocus(regione);
      return;
    }
    if (macro && (macroGeo.features || []).some((f) => f.properties && f.properties.id === macro)) {
      await showRegions(macro);
    }
  } catch (err) {
    console.error(err);
  }
}

async function loadMap() {
  setStatus("Caricamento mappa…", true);
  const [macroRes, regRes, provRes, metaRes] = await Promise.all([
    fetch("data/map/macro.geojson"),
    fetch("data/map/regioni.geojson"),
    fetch("data/map/province.geojson"),
    fetch("data/map/meta.json"),
  ]);
  if (!macroRes.ok || !regRes.ok) throw new Error("GeoJSON non disponibile");
  meta = metaRes.ok ? await metaRes.json() : { italy: {}, regions: [] };
  macroGeo = await macroRes.json();
  regioniGeo = await regRes.json();
  provinceGeo = provRes.ok ? await provRes.json() : { type: "FeatureCollection", features: [] };
  enrichPopDensity(macroGeo);
  enrichPopDensity(regioniGeo);
  enrichPopDensity(provinceGeo);
  scaleFeatures =
    (provinceGeo.features && provinceGeo.features.length)
      ? provinceGeo.features
      : regioniGeo.features || [];

  map = L.map("map", {
    zoomControl: false,
    attributionControl: false,
    scrollWheelZoom: false,
    doubleClickZoom: false,
    boxZoom: false,
    keyboard: false,
    touchZoom: false,
    dragging: false,
    preferCanvas: true,
    minZoom: 5,
    maxZoom: 12,
  }).setView([42.5, 12.5], 6);

  await showMacro();
  await applyDeepLink();
  requestAnimationFrame(() => map.invalidateSize());
  setStatus("", false);
  scheduleAutoplay();
}

function bindControls() {
  $("mapLegend").addEventListener("click", (e) => {
    const dot = e.target.closest("#mapDots [data-layer]");
    if (dot) {
      const key = dot.getAttribute("data-layer");
      const from = LAYER_ORDER.indexOf(activeLayer);
      const to = LAYER_ORDER.indexOf(key);
      if (to < 0 || to === from) return;
      setActiveLayer(key, to > from ? 1 : -1);
    }
  });

  $("btnAutoplay").addEventListener("click", () => {
    setAutoplayOn(!autoplayOn);
  });

  $("mapCrumb").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-to]");
    if (!btn || btn.disabled) return;
    if (btn.getAttribute("data-to") === "up") goUpOneLevel();
  });

  $("btnPanelClose").addEventListener("click", closePanel);
  const scrim = $("panelScrim");
  if (scrim) scrim.addEventListener("click", closePanel);
  bindSheetDrag();
  bindMapSwipe();
}

async function init() {
  initIosBar();
  autoplayOn = readAutoplayOn();
  syncAutoplayButton();
  applyPanelChrome();
  const url = new URL(location.href);
  if (url.searchParams.has("legend") || url.searchParams.has("nav")) {
    url.searchParams.delete("legend");
    url.searchParams.delete("nav");
    history.replaceState(null, "", url);
  }
  try {
    localStorage.removeItem("escilo-map-nav-style");
    localStorage.removeItem("escilo-map-panel-try");
  } catch {
    /* ignore */
  }
  if (!window.L) {
    $("mapStatus").textContent = "Errore: libreria mappa non caricata.";
    return;
  }
  try {
    await loadMap();
    bindControls();
  } catch (err) {
    console.error(err);
    $("mapStatus").hidden = false;
    $("mapStatus").textContent = "Impossibile caricare la mappa. Riprova più tardi.";
  }
}

init();
