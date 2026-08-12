import { MIX_CAL_COLORS, MIX_EMOJI } from "./mix-helpers.js";

const BODY_PATH = "M20 67 C20 67 20 148 28 153 L72 153 C80 148 80 67 80 67 Z";

let mixBinSeq = 0;

function fmtPct(n, digits) {
  if (n == null || Number.isNaN(n)) return "—";
  return (
    Number(n).toLocaleString("it-IT", {
      minimumFractionDigits: digits == null ? 1 : digits,
      maximumFractionDigits: digits == null ? 1 : digits,
    }) + "%"
  );
}

function emojiFor(item) {
  return item.emoji || MIX_EMOJI[item.key] || "•";
}

function binWheel(cx, cy) {
  return (
    '<g class="prod-bin-wheel">' +
    '<circle cx="' + cx + '" cy="' + cy + '" r="7.2" fill="#141414"/>' +
    '<circle cx="' + cx + '" cy="' + cy + '" r="5.2" fill="#252525"/>' +
    '<circle cx="' + cx + '" cy="' + cy + '" r="2.1" fill="#4a4a4a"/>' +
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

/** Stesso sacco di binMeasureSvg in stats.js */
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

/** SVG cassonetto (stesso markup della card UI). Esportato per la share image. */
export function mixBinSvg(item) {
  mixBinSeq += 1;
  const uid = "mixBin" + mixBinSeq;
  const cal = MIX_CAL_COLORS[item.key] || MIX_CAL_COLORS.altro;
  const color = cal.color;
  const ink = cal.ink;
  const pct = fmtPct(item.v, 0);
  const emoji = emojiFor(item);

  return (
    '<svg class="mix-bin-svg prod-bin-svg" viewBox="0 34 100 127" preserveAspectRatio="xMidYMin meet" aria-hidden="true">' +
    "<defs>" +
    '<linearGradient id="' +
    uid +
    'Bin" x1="0%" y1="0%" x2="100%" y2="0%">' +
    '<stop offset="0%" stop-color="' +
    color +
    '"/>' +
    '<stop offset="50%" stop-color="' +
    color +
    '"/>' +
    '<stop offset="100%" stop-color="' +
    color +
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
    '<ellipse cx="50" cy="67" rx="31" ry="4.2" fill="' +
    color +
    '" opacity="0.85"/>' +
    '<path d="M16 63 L84 63 L82 70 L18 70 Z" fill="' +
    color +
    '" opacity="0.75"/>' +
    '<rect x="18" y="59" width="64" height="5" rx="1.2" fill="' +
    color +
    '" opacity="0.9"/>' +
    '<g opacity="0.4">' +
    '<rect x="24" y="70" width="2" height="7" rx="0.8" fill="#142018"/>' +
    '<rect x="32" y="70" width="2" height="7" rx="0.8" fill="#142018"/>' +
    '<rect x="66" y="70" width="2" height="7" rx="0.8" fill="#142018"/>' +
    '<rect x="74" y="70" width="2" height="7" rx="0.8" fill="#142018"/>' +
    "</g>" +
    binWheel(27, 153) +
    binWheel(73, 153) +
    '<rect x="24" y="78" width="52" height="20" rx="5" fill="rgba(0,0,0,0.16)"/>' +
    '<text x="50" y="93" text-anchor="middle" fill="' +
    ink +
    '" font-size="18" font-weight="800" font-family="system-ui,sans-serif">' +
    pct +
    "</text>" +
    '<rect x="34" y="116" width="32" height="22" rx="4.5" fill="rgba(0,0,0,0.14)"/>' +
    '<text x="50" y="132" text-anchor="middle" font-size="15">' +
    emoji +
    "</text>" +
    "</svg>"
  );
}

/** Fila di cassonetti (proposta E): stesso SVG di «Quanto produciamo», colori calendario. */
export function renderMixWidget(items) {
  if (!items.length) {
    return '<p class="lead" style="margin:0">Mix frazioni non disponibile per questo comune.</p>';
  }

  const bins = items
    .map(function (item) {
      const short = item.short || item.label;
      const title = item.label + ": " + fmtPct(item.v, 1);
      return (
        '<article class="mix-bin escilo-block" role="listitem" title="' +
        title +
        '">' +
        '<figure class="mix-bin-fig" aria-label="' +
        title +
        '">' +
        mixBinSvg(item) +
        "</figure>" +
        '<p class="mix-bin-label">' +
        short +
        "</p>" +
        "</article>"
      );
    })
    .join("");

  return (
    '<div class="mix-bins" role="list" aria-label="Quote per frazione">' +
    bins +
    "</div>"
  );
}

/**
 * Se i cassonetti vanno a capo in modo sbilanciato (es. 4+2),
 * passa a griglia con colonne = ceil(n/2) così le due righe sono equilibrate (3+3).
 * Se stanno su una riga sola, lascia il flex naturale.
 */
export function layoutMixBins(root) {
  const bins = root && root.querySelector(".mix-bins");
  if (!bins || bins.dataset.mixLayouting === "1") return;

  const items = Array.prototype.slice.call(bins.children);
  const n = items.length;
  if (n < 2) {
    bins.classList.remove("mix-bins--balanced");
    bins.style.removeProperty("--mix-cols");
    return;
  }

  bins.dataset.mixLayouting = "1";
  bins.classList.remove("mix-bins--balanced");
  bins.style.removeProperty("--mix-cols");
  void bins.offsetWidth;

  const tops = {};
  let rowCount = 0;
  for (let i = 0; i < items.length; i += 1) {
    const t = Math.round(items[i].getBoundingClientRect().top);
    if (tops[t] == null) {
      tops[t] = 0;
      rowCount += 1;
    }
    tops[t] += 1;
  }

  if (rowCount >= 2) {
    bins.style.setProperty("--mix-cols", String(Math.ceil(n / 2)));
    bins.classList.add("mix-bins--balanced");
  }

  delete bins.dataset.mixLayouting;
}

/** Osserva resize e ribilancia le due righe. */
export function observeMixBinsLayout(root) {
  if (!root) return null;
  const bins = root.querySelector(".mix-bins");
  if (!bins) return null;

  let raf = 0;
  function schedule() {
    if (bins.dataset.mixLayouting === "1") return;
    if (raf) cancelAnimationFrame(raf);
    raf = requestAnimationFrame(function () {
      raf = 0;
      layoutMixBins(root);
    });
  }

  schedule();

  if (typeof ResizeObserver === "undefined") {
    window.addEventListener("resize", schedule);
    return {
      disconnect: function () {
        window.removeEventListener("resize", schedule);
        if (raf) cancelAnimationFrame(raf);
      },
    };
  }

  const ro = new ResizeObserver(schedule);
  ro.observe(bins);
  if (root !== bins) ro.observe(root);
  return {
    disconnect: function () {
      ro.disconnect();
      if (raf) cancelAnimationFrame(raf);
    },
  };
}
