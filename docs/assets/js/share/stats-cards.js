/** Canvas cards 9:16 (1080×1920) for social Stories share. */

import { MIX_CAL_COLORS, MIX_EMOJI, parseMixItems } from "./mix-helpers.js";
import { mixBinSvg } from "./mix-variants.js";
import {
  prodBinMeasureSvg,
  resolveProdBins,
  resetProdBinSvgSeq,
} from "./prod-variants.js";

export const CARD_W = 1080;
export const CARD_H = 1920;

const COLORS = {
  bgTop: "#12281e",
  bgMid: "#1a4a36",
  bgBot: "#246b4a",
  cream: "#f3faf6",
  ink: "#142018",
  muted: "#5a7266",
  accent: "#1f5c42",
  surface: "#ffffff",
  soft: "rgba(243, 250, 246, 0.12)",
};

function fmtPct(n, digits) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return (
    Number(n).toLocaleString("it-IT", {
      minimumFractionDigits: digits == null ? 1 : digits,
      maximumFractionDigits: digits == null ? 1 : digits,
    }) + "%"
  );
}

function fmtNum(n, digits) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return Number(n).toLocaleString("it-IT", {
    minimumFractionDigits: digits == null ? 0 : digits,
    maximumFractionDigits: digits == null ? 1 : digits,
  });
}

function fmtEuro(n, digits) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return (
    Number(n).toLocaleString("it-IT", {
      minimumFractionDigits: digits == null ? 0 : digits,
      maximumFractionDigits: digits == null ? 0 : digits,
    }) + " €"
  );
}

function costVsItalyMessage(cost, medIt) {
  if (cost == null || medIt == null) return "—";
  const d = Number(cost) - Number(medIt);
  if (Math.abs(d) < 0.5) return "In linea con la mediana Italia";
  const abs = Math.abs(d).toLocaleString("it-IT", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
  if (d < 0) return abs + " € sotto la mediana Italia";
  return abs + " € sopra la mediana Italia";
}

function fmtTopN(n) {
  return Number(n).toLocaleString("it-IT");
}

/** @param {number|null|undefined} pctile @param {number|null|undefined} nComuni */
export function rdRankBandMessage(pctile, nComuni) {
  if (pctile == null || Number.isNaN(pctile) || !nComuni) return "—";
  const n = Number(nComuni);
  const rankBest = Math.max(1, Math.round(n * (1 - Number(pctile) / 100)));
  const rankWorst = Math.max(1, n - rankBest + 1);

  if (rankBest <= 100) return "Top 100 comuni italiani";
  if (rankBest <= 250) return "Top 250 comuni italiani";
  if (rankBest <= 500) return "Top 500 comuni italiani";
  if (rankBest <= 1000) return "Top " + fmtTopN(1000) + " comuni italiani";
  if (rankBest <= 2000) return "Top " + fmtTopN(2000) + " comuni italiani";

  if (rankWorst <= 100) return "Fra gli ultimi 100 comuni italiani";
  if (rankWorst <= 250) return "Fra gli ultimi 250 comuni italiani";
  if (rankWorst <= 500) return "Fra gli ultimi 500 comuni italiani";
  if (rankWorst <= 1000) return "Fra gli ultimi " + fmtTopN(1000) + " comuni italiani";
  if (rankWorst <= 2000) return "Fra gli ultimi " + fmtTopN(2000) + " comuni italiani";

  if (pctile >= 50) return "Fra i migliori comuni italiani";
  return "Fra i comuni italiani con meno differenziata";
}

/** Same delta format as stats.html KPI bench: +1,8% / −1,8% / in linea */
function fmtDeltaPct(comune, ref) {
  if (comune == null || ref == null || Number.isNaN(comune) || Number.isNaN(ref)) {
    return null;
  }
  const d = Number(comune) - Number(ref);
  if (Math.abs(d) < 0.05) return { text: "in linea", d: 0 };
  const abs = Math.abs(d).toLocaleString("it-IT", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  return { text: (d >= 0 ? "+" : "−") + abs + "%", d: d };
}

function shortProvinciaLabel(name) {
  const n = (name || "").trim();
  if (!n) return "Provincia";
  if (/^prov/i.test(n)) return n;
  return "Prov. " + n;
}

function slugify(name) {
  return (
    String(name || "comune")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 48) || "comune"
  );
}

function roundRect(ctx, x, y, w, h, r) {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
}

function wrapText(ctx, text, maxWidth) {
  const words = String(text || "").split(/\s+/);
  const lines = [];
  let line = "";
  for (let i = 0; i < words.length; i++) {
    const test = line ? line + " " + words[i] : words[i];
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line);
      line = words[i];
    } else {
      line = test;
    }
  }
  if (line) lines.push(line);
  return lines;
}

/** Truncate with ellipsis so text fits maxWidth (single line). */
function ellipsizeText(ctx, text, maxWidth) {
  const s = String(text || "");
  if (!s || ctx.measureText(s).width <= maxWidth) return s;
  const ell = "…";
  if (ctx.measureText(ell).width > maxWidth) return "";
  let lo = 0;
  let hi = s.length;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    if (ctx.measureText(s.slice(0, mid) + ell).width <= maxWidth) lo = mid;
    else hi = mid - 1;
  }
  return s.slice(0, Math.max(0, lo)) + ell;
}

/**
 * Fit a label into a narrow cell: shrink font, wrap ≤2 lines, then ellipsize.
 * @returns {{ lines: string[], size: number }}
 */
function fitCellLabel(ctx, text, maxWidth) {
  const raw = String(text || "").trim() || "—";
  for (let size = 22; size >= 15; size--) {
    ctx.font = '650 ' + size + 'px "Outfit", "Segoe UI", sans-serif';
    const wrapped = wrapText(ctx, raw, maxWidth);
    if (wrapped.length > 2) continue;
    const lines = wrapped.map(function (ln) {
      return ellipsizeText(ctx, ln, maxWidth);
    });
    const ok = wrapped.every(function (ln) {
      return ctx.measureText(ln).width <= maxWidth + 0.5;
    });
    if (ok || size === 15) return { lines: lines, size: size };
  }
  ctx.font = '650 15px "Outfit", "Segoe UI", sans-serif';
  return { lines: [ellipsizeText(ctx, raw, maxWidth)], size: 15 };
}

function drawBackground(ctx) {
  const g = ctx.createLinearGradient(0, 0, CARD_W * 0.2, CARD_H);
  g.addColorStop(0, COLORS.bgTop);
  g.addColorStop(0.42, COLORS.bgMid);
  g.addColorStop(1, COLORS.bgBot);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, CARD_W, CARD_H);

  ctx.fillStyle = COLORS.soft;
  ctx.beginPath();
  ctx.arc(CARD_W * 0.88, CARD_H * 0.08, 320, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.arc(CARD_W * -0.05, CARD_H * 0.72, 280, 0, Math.PI * 2);
  ctx.fill();
}

/**
 * @returns {Promise<HTMLImageElement|null>}
 */
function loadBrandMark() {
  return new Promise(function (resolve) {
    const img = new Image();
    img.decoding = "async";
    img.onload = function () {
      resolve(img);
    };
    img.onerror = function () {
      resolve(null);
    };
    img.src = "brand-mark.png";
  });
}

/** Tint brand-mark to solid cream; drop low-alpha rounded-corner arcs. */
function tintMarkLight(mark) {
  const w = mark.naturalWidth || mark.width;
  const h = mark.naturalHeight || mark.height;
  if (!w || !h) return null;
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const t = c.getContext("2d");
  if (!t) return null;
  t.drawImage(mark, 0, 0);
  const imgData = t.getImageData(0, 0, w, h);
  const d = imgData.data;
  // Corner frame of the PNG is faint (alpha ≲120); icon body is near-opaque.
  const minAlpha = 120;
  for (let i = 0; i < d.length; i += 4) {
    if (d[i + 3] > minAlpha) {
      d[i] = 243;
      d[i + 1] = 250;
      d[i + 2] = 246;
      d[i + 3] = 255;
    } else {
      d[i] = 0;
      d[i + 1] = 0;
      d[i + 2] = 0;
      d[i + 3] = 0;
    }
  }
  t.putImageData(imgData, 0, 0);
  return c;
}

async function ensureFonts() {
  try {
    if (document.fonts && document.fonts.ready) {
      await document.fonts.ready;
    }
  } catch {
    /* ignore */
  }
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {HTMLCanvasElement|HTMLImageElement|null} markLight
 * @param {number} y
 */
function drawBrandHeader(ctx, markLight, y) {
  const x = 56;
  const size = 140;
  if (markLight) {
    ctx.drawImage(markLight, x, y, size, size);
    ctx.fillStyle = COLORS.cream;
    ctx.font = '700 92px "Fraunces", Georgia, serif';
    ctx.textBaseline = "middle";
    ctx.fillText("Escilo", x + size + 28, y + size / 2 + 4);
  } else {
    ctx.fillStyle = COLORS.cream;
    ctx.font = '700 96px "Fraunces", Georgia, serif';
    ctx.textBaseline = "top";
    ctx.fillText("Escilo", x, y + 24);
  }
  ctx.textBaseline = "alphabetic";
}

function drawFooter(ctx) {
  ctx.fillStyle = "rgba(243, 250, 246, 0.95)";
  ctx.font = '700 36px "Fraunces", Georgia, serif';
  ctx.textAlign = "center";
  ctx.textBaseline = "alphabetic";
  ctx.fillText("escilo.it", CARD_W / 2, CARD_H - 96);
  ctx.fillStyle = "rgba(243, 250, 246, 0.62)";
  ctx.font = '500 24px "Outfit", "Segoe UI", sans-serif';
  ctx.fillText("perché i cassonetti non si escono da soli", CARD_W / 2, CARD_H - 54);
  ctx.textAlign = "left";
}

/**
 * @param {HTMLCanvasElement} canvas
 * @param {string} filename
 * @returns {Promise<{ file: File, blob: Blob, dataUrl: string }>}
 */
function canvasToShareFile(canvas, filename) {
  return new Promise(function (resolve, reject) {
    canvas.toBlob(
      function (blob) {
        if (!blob) {
          reject(new Error("PNG export failed"));
          return;
        }
        const file = new File([blob], filename, { type: "image/png" });
        const dataUrl = canvas.toDataURL("image/png");
        resolve({ file: file, blob: blob, dataUrl: dataUrl });
      },
      "image/png",
      0.92
    );
  });
}

/**
 * Bench cells like stats.html: label / mediana% / (delta% | costo chip)
 * @param {CanvasRenderingContext2D} ctx
 * @param {Array<{label:string,value:string,delta?:string,tone?:string,cost?:string|null}>} cells
 * @param {boolean} [costMode]
 */
function drawBenchRow(ctx, cells, x, y, w, h, costMode) {
  const n = cells.length;
  if (!n) return;
  const gap = 16;
  const cellW = (w - gap * (n - 1)) / n;
  const labelMaxW = Math.max(40, cellW - 24);
  for (let i = 0; i < n; i++) {
    const cell = cells[i];
    const cx = x + i * (cellW + gap);
    roundRect(ctx, cx, y, cellW, h, 28);
    ctx.fillStyle = "#f0f5f2";
    ctx.fill();

    const fitted = fitCellLabel(ctx, cell.label, labelMaxW);
    ctx.fillStyle = COLORS.muted;
    ctx.font =
      '650 ' + fitted.size + 'px "Outfit", "Segoe UI", sans-serif';
    ctx.textAlign = "center";
    const lineH = fitted.size + 6;
    const labelBlockH = fitted.lines.length * lineH;
    let labelY = y + 18 + (52 - labelBlockH) / 2 + fitted.size;
    for (let li = 0; li < fitted.lines.length; li++) {
      ctx.fillText(fitted.lines[li], cx + cellW / 2, labelY);
      labelY += lineH;
    }

    ctx.fillStyle = COLORS.ink;
    ctx.font = '700 40px "Outfit", "Segoe UI", sans-serif';
    const valueText = ellipsizeText(ctx, cell.value, labelMaxW);
    ctx.fillText(valueText, cx + cellW / 2, y + 96);

    if (costMode) {
      const costTextRaw = cell.cost || "—";
      let costSize = 26;
      ctx.font = '650 ' + costSize + 'px "Outfit", "Segoe UI", sans-serif';
      let costText = costTextRaw;
      const chipPadX = 12;
      const chipInnerMax = Math.max(24, cellW - 16 - chipPadX * 2);
      while (costSize > 18 && ctx.measureText(costText).width > chipInnerMax) {
        costSize -= 1;
        ctx.font = '650 ' + costSize + 'px "Outfit", "Segoe UI", sans-serif';
      }
      costText = ellipsizeText(ctx, costText, chipInnerMax);
      const tw = ctx.measureText(costText).width;
      const chipH = 40;
      const chipW = Math.min(cellW - 16, tw + chipPadX * 2);
      const chipX = cx + (cellW - chipW) / 2;
      const chipY = y + 118;
      roundRect(ctx, chipX, chipY, chipW, chipH, 12);
      ctx.fillStyle = "rgba(31, 92, 66, 0.12)";
      ctx.fill();
      ctx.strokeStyle = "rgba(31, 92, 66, 0.22)";
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.fillStyle = COLORS.ink;
      ctx.textBaseline = "middle";
      ctx.fillText(costText, cx + cellW / 2, chipY + chipH / 2 + 1);
      ctx.textBaseline = "alphabetic";
    } else {
      ctx.fillStyle =
        cell.tone === "good"
          ? COLORS.accent
          : cell.tone === "bad"
            ? "#8b3a3a"
            : COLORS.muted;
      ctx.font = '650 28px "Outfit", "Segoe UI", sans-serif';
      const deltaText = ellipsizeText(ctx, cell.delta || "", labelMaxW);
      ctx.fillText(deltaText, cx + cellW / 2, y + 142);
    }
  }
  ctx.textAlign = "left";
}

/**
 * Box bianco COMUNE + nome (+ abitanti), come nella card RD.
 * @returns {number} y sotto il box
 */
function drawComuneNameBox(ctx, rec, nameBoxY) {
  const name = rec.name || "Comune";
  const nameBoxX = 48;
  const nameBoxW = CARD_W - 96;
  const namePadX = 44;
  const namePadTop = 40;
  const namePadBot = 40;
  const titleLabel = "COMUNE";
  const titleH = 32;
  const gapAfterTitle = 16;
  ctx.font = '700 56px "Fraunces", Georgia, serif';
  const nameLines = wrapText(ctx, name, nameBoxW - namePadX * 2);
  const nameLineCount = Math.min(nameLines.length, 2);
  const nameLineH = 64;
  const popLine =
    rec.pop != null ? "Numero di abitanti " + fmtNum(rec.pop, 0) : "";
  const popH = popLine ? 44 : 0;
  const gapNamePop = popLine ? 18 : 0;
  const nameBoxH =
    namePadTop +
    titleH +
    gapAfterTitle +
    nameLineCount * nameLineH +
    gapNamePop +
    popH +
    namePadBot;

  roundRect(ctx, nameBoxX, nameBoxY, nameBoxW, nameBoxH, 36);
  ctx.fillStyle = COLORS.surface;
  ctx.fill();

  ctx.fillStyle = COLORS.muted;
  ctx.font = '700 28px "Outfit", "Segoe UI", sans-serif';
  try {
    ctx.letterSpacing = "0.04em";
  } catch {
    /* ignore */
  }
  ctx.fillText(titleLabel, nameBoxX + namePadX, nameBoxY + namePadTop + 8);
  try {
    ctx.letterSpacing = "0px";
  } catch {
    /* ignore */
  }

  ctx.fillStyle = COLORS.ink;
  ctx.font = '700 56px "Fraunces", Georgia, serif';
  let nameY = nameBoxY + namePadTop + titleH + gapAfterTitle + 44;
  for (let i = 0; i < nameLineCount; i++) {
    ctx.fillText(nameLines[i], nameBoxX + namePadX, nameY);
    nameY += nameLineH;
  }
  if (popLine) {
    ctx.fillStyle = COLORS.muted;
    ctx.font = '550 28px "Outfit", "Segoe UI", sans-serif';
    ctx.fillText(popLine, nameBoxX + namePadX, nameBoxY + nameBoxH - namePadBot);
  }

  return nameBoxY + nameBoxH;
}

/**
 * @param {object} rec
 * @param {object} baselines
 * @param {{ costOn?: boolean }} [opts] — costi solo se selezionati in UI; mai lo switch
 */
export async function buildSingleCard(rec, baselines, opts) {
  await ensureFonts();
  const mark = await loadBrandMark();
  const markLight = mark ? tintMarkLight(mark) : null;
  const canvas = document.createElement("canvas");
  canvas.width = CARD_W;
  canvas.height = CARD_H;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas unavailable");

  drawBackground(ctx);
  drawBrandHeader(ctx, markLight, 56);

  const name = rec.name || "Comune";
  const afterNameY = drawComuneNameBox(ctx, rec, 230);
  const rd = rec.rd_pct;
  const hasCost =
    rec.costo_tot_ab != null && !Number.isNaN(Number(rec.costo_tot_ab));
  const costOn = !!(opts && opts.costOn) && hasCost;
  const provincia = (rec.provincia || "").trim();
  const regione = (rec.regione || "").trim();
  const medIt = baselines && baselines.rd_pct_median;
  const medCostIt = baselines && baselines.costo_tot_ab_median;
  const provBase =
    baselines &&
    baselines.by_provincia &&
    provincia &&
    baselines.by_provincia[provincia];
  const regBase =
    baselines &&
    baselines.by_regione &&
    regione &&
    baselines.by_regione[regione];
  const clusters = (baselines && baselines.pop_clusters) || [];
  const peer =
    (rec.pop_cluster_id &&
      clusters.find(function (c) {
        return c && c.id === rec.pop_cluster_id;
      })) ||
    null;
  const medProv = provBase && provBase.rd_pct_median;
  const medReg = regBase && regBase.rd_pct_median;
  const medPeer = peer && peer.rd_pct_n >= 30 ? peer.rd_pct_median : null;
  const medCostProv = provBase && provBase.costo_tot_ab_median;
  const medCostReg = regBase && regBase.costo_tot_ab_median;
  const medCostPeer =
    peer && peer.costo_tot_ab_n >= 30 ? peer.costo_tot_ab_median : null;

  const cells = [];
  if (costOn) {
    function pushCostCell(label, rdMedian, costMedian) {
      if (rdMedian == null) return;
      cells.push({
        label: label,
        value: fmtPct(rdMedian, 1),
        cost: costMedian != null ? fmtEuro(costMedian, 0) : "—",
      });
    }
    pushCostCell(shortProvinciaLabel(provincia), medProv, medCostProv);
    pushCostCell(regione || "Regione", medReg, medCostReg);
    pushCostCell("Italia", medIt, medCostIt);
    pushCostCell("Per abitanti", medPeer, medCostPeer);
  } else {
    function pushCell(label, median) {
      if (median == null) return;
      const d = fmtDeltaPct(rd, median);
      if (!d) return;
      const tone = d.d > 0 ? "good" : d.d < 0 ? "bad" : "warn";
      cells.push({
        label: label,
        value: fmtPct(median, 1),
        delta: d.text === "in linea" ? "(in linea)" : "(" + d.text + ")",
        tone: tone,
      });
    }
    pushCell(shortProvinciaLabel(provincia), medProv);
    pushCell(regione || "Regione", medReg);
    pushCell("Italia", medIt);
    pushCell("Per abitanti", medPeer);
  }

  const band = costOn
    ? costVsItalyMessage(rec.costo_tot_ab, medCostIt)
    : rdRankBandMessage(rec.rd_pctile_it, baselines && baselines.rd_pct_n);
  const padX = 52;
  const padTop = 48;
  const padBot = 52;
  const kpiTitleH = 36;
  const kpiGapAfterTitle = 18;
  const valueH = 150;
  const gapAfterValue = 22;
  ctx.font = '600 34px "Outfit", "Segoe UI", sans-serif';
  const bandLines = wrapText(ctx, band, CARD_W - 96 - padX * 2);
  const bandH = Math.max(1, bandLines.length) * 44;
  const gapBeforeBench = cells.length ? 40 : 0;
  const benchH = cells.length ? 180 : 0;

  const cardH =
    padTop +
    kpiTitleH +
    kpiGapAfterTitle +
    valueH +
    gapAfterValue +
    bandH +
    gapBeforeBench +
    benchH +
    padBot;
  const cardX = 48;
  const cardW = CARD_W - 96;
  const cardY = afterNameY + 28;

  roundRect(ctx, cardX, cardY, cardW, cardH, 48);
  ctx.fillStyle = COLORS.surface;
  ctx.fill();

  // box-title (no € switch — only in live UI)
  ctx.fillStyle = COLORS.muted;
  ctx.font = '700 28px "Outfit", "Segoe UI", sans-serif';
  try {
    ctx.letterSpacing = "0.04em";
  } catch {
    /* ignore */
  }
  ctx.fillText("RACCOLTA DIFFERENZIATA", cardX + padX, cardY + padTop + 8);
  try {
    ctx.letterSpacing = "0px";
  } catch {
    /* ignore */
  }

  let cy = cardY + padTop + kpiTitleH + kpiGapAfterTitle;
  const rdText = fmtPct(rec.rd_pct, 1);
  ctx.fillStyle = COLORS.accent;
  ctx.font = '700 148px "Fraunces", Georgia, serif';
  ctx.textBaseline = "alphabetic";
  ctx.fillText(rdText, cardX + padX, cy + 120);

  if (costOn) {
    const rdW = ctx.measureText(rdText).width;
    const costMain = fmtEuro(rec.costo_tot_ab, 0);
    const unit = "/ab·anno";
    ctx.font = '650 42px "Fraunces", Georgia, serif';
    const costW = ctx.measureText(costMain).width;
    ctx.font = '550 22px "Outfit", "Segoe UI", sans-serif';
    const unitW = ctx.measureText(unit).width;
    const chipPadX = 20;
    const chipGap = 10;
    const chipW = costW + chipGap + unitW + chipPadX * 2;
    const chipH = 64;
    const chipX = cardX + padX + rdW + 28;
    const chipY = cy + 120 - 52;
    roundRect(ctx, chipX, chipY, chipW, chipH, 16);
    ctx.fillStyle = "rgba(31, 92, 66, 0.12)";
    ctx.fill();
    ctx.strokeStyle = "rgba(31, 92, 66, 0.22)";
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.fillStyle = COLORS.ink;
    ctx.font = '650 42px "Fraunces", Georgia, serif';
    ctx.textBaseline = "middle";
    ctx.fillText(costMain, chipX + chipPadX, chipY + chipH / 2 + 1);
    ctx.fillStyle = COLORS.muted;
    ctx.font = '550 22px "Outfit", "Segoe UI", sans-serif';
    ctx.fillText(
      unit,
      chipX + chipPadX + costW + chipGap,
      chipY + chipH / 2 + 2
    );
    ctx.textBaseline = "alphabetic";
  }
  cy += valueH + gapAfterValue;

  ctx.fillStyle = COLORS.ink;
  ctx.font = '600 34px "Outfit", "Segoe UI", sans-serif';
  for (let i = 0; i < bandLines.length; i++) {
    ctx.fillText(bandLines[i], cardX + padX, cy + 30);
    cy += 44;
  }

  if (cells.length) {
    drawBenchRow(ctx, cells, cardX + 40, cy + 12, cardW - 80, benchH, costOn);
  }

  drawFooter(ctx);

  const filename =
    "escilo-" + slugify(name) + (costOn ? "-rd-costo.png" : "-rd.png");
  return canvasToShareFile(canvas, filename);
}

/**
 * Rasterizza l’SVG cassonetto della UI (stesso markup di mix-variants).
 * @param {string} svgMarkup
 * @param {number} widthPx
 * @returns {Promise<HTMLImageElement|null>}
 */
function loadMixBinImage(svgMarkup, widthPx) {
  const h = Math.round((widthPx * 127) / 100);
  const withNs = svgMarkup.replace(
    "<svg ",
    '<svg xmlns="http://www.w3.org/2000/svg" width="' +
      widthPx +
      '" height="' +
      h +
      '" '
  );
  return new Promise(function (resolve) {
    const img = new Image();
    img.decoding = "async";
    img.onload = function () {
      resolve(img);
    };
    img.onerror = function () {
      resolve(null);
    };
    img.src =
      "data:image/svg+xml;charset=utf-8," + encodeURIComponent(withNs);
  });
}

/**
 * Fallback canvas se l’SVG non rasterizza (stessi colori calendario).
 * @param {CanvasRenderingContext2D} ctx
 */
function drawMixBinFallback(ctx, item, x, y, w, h) {
  const cal = MIX_CAL_COLORS[item.key] || MIX_CAL_COLORS.altro;
  const sx = w / 100;
  const sy = h / 127;
  ctx.save();
  ctx.translate(x, y - 34 * sy);
  ctx.scale(sx, sy);

  ctx.fillStyle = "#0c0c0c";
  ctx.beginPath();
  ctx.ellipse(50, 56, 20, 14, 0, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = cal.color;
  ctx.beginPath();
  ctx.moveTo(20, 67);
  ctx.bezierCurveTo(20, 67, 20, 148, 28, 153);
  ctx.lineTo(72, 153);
  ctx.bezierCurveTo(80, 148, 80, 67, 80, 67);
  ctx.closePath();
  ctx.fill();

  ctx.fillStyle = "rgba(0,0,0,0.14)";
  ctx.fillRect(18, 59, 64, 11);
  ctx.beginPath();
  ctx.ellipse(50, 67, 31, 4.2, 0, 0, Math.PI * 2);
  ctx.fillStyle = cal.color;
  ctx.globalAlpha = 0.85;
  ctx.fill();
  ctx.globalAlpha = 1;

  ctx.fillStyle = "#141414";
  ctx.beginPath();
  ctx.arc(27, 153, 7.2, 0, Math.PI * 2);
  ctx.arc(73, 153, 7.2, 0, Math.PI * 2);
  ctx.fill();

  roundRect(ctx, 24, 78, 52, 20, 5);
  ctx.fillStyle = "rgba(0,0,0,0.16)";
  ctx.fill();
  ctx.fillStyle = cal.ink;
  ctx.font = '800 18px "Outfit", "Segoe UI", sans-serif';
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(fmtPct(item.v, 0), 50, 88);

  roundRect(ctx, 34, 116, 32, 22, 4.5);
  ctx.fillStyle = "rgba(0,0,0,0.14)";
  ctx.fill();
  ctx.font = '700 15px "Segoe UI Emoji", "Apple Color Emoji", sans-serif';
  ctx.fillText(MIX_EMOJI[item.key] || "📋", 50, 127);

  ctx.restore();
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
}

/**
 * Story card: composizione differenziata — stessa griglia cassonetti della UI.
 * @param {object} rec
 */
export async function buildMixCard(rec) {
  await ensureFonts();
  const items = parseMixItems(rec.mix_rd_pct || {});
  if (!items.length) throw new Error("Mix unavailable");

  const mark = await loadBrandMark();
  const markLight = mark ? tintMarkLight(mark) : null;
  const canvas = document.createElement("canvas");
  canvas.width = CARD_W;
  canvas.height = CARD_H;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas unavailable");

  drawBackground(ctx);
  drawBrandHeader(ctx, markLight, 56);

  const name = rec.name || "Comune";
  const afterNameY = drawComuneNameBox(ctx, rec, 230);
  const padX = 40;
  const cardX = 48;
  const cardW = CARD_W - 96;
  let y = afterNameY + 28;

  const n = items.length;
  const cols = n <= 3 ? n : Math.ceil(n / 2);
  const rows = Math.ceil(n / cols);
  const panelX = cardX;
  const panelW = cardW;
  const panelPadX = padX;
  const panelPadTop = 44;
  const panelPadBot = 48;
  const titleH = 36;
  const leadGap = 18;
  const leadLineH = 34;
  const lead =
    "Cosa finisce nei cassonetti colorati, in quote sul differenziato.";
  ctx.font = '500 26px "Outfit", "Segoe UI", sans-serif';
  const leadLines = wrapText(ctx, lead, panelW - panelPadX * 2);
  const leadH = leadLines.length * leadLineH;
  const binsTopGap = 32;
  const binGapX = 24;
  const binGapY = 28;
  const labelH = 40;
  const labelGap = 12;
  const innerW = panelW - panelPadX * 2;
  const binW = Math.min(
    250,
    Math.floor((innerW - binGapX * (cols - 1)) / cols)
  );
  const binH = Math.round((binW * 127) / 100);
  const cellH = binH + labelGap + labelH;
  const gridW = cols * binW + (cols - 1) * binGapX;
  const gridH = rows * cellH + (rows - 1) * binGapY;
  const panelH =
    panelPadTop +
    titleH +
    leadGap +
    leadH +
    binsTopGap +
    gridH +
    panelPadBot;

  roundRect(ctx, panelX, y, panelW, panelH, 48);
  ctx.fillStyle = COLORS.surface;
  ctx.fill();

  let py = y + panelPadTop;
  ctx.fillStyle = COLORS.muted;
  ctx.font = '700 28px "Outfit", "Segoe UI", sans-serif';
  try {
    ctx.letterSpacing = "0.04em";
  } catch {
    /* ignore */
  }
  ctx.fillText("COSA DIFFERENZIAMO", panelX + panelPadX, py + 8);
  try {
    ctx.letterSpacing = "0px";
  } catch {
    /* ignore */
  }
  py += titleH + leadGap;

  ctx.fillStyle = COLORS.muted;
  ctx.font = '500 26px "Outfit", "Segoe UI", sans-serif';
  for (let i = 0; i < leadLines.length; i++) {
    ctx.fillText(leadLines[i], panelX + panelPadX, py + 22);
    py += leadLineH;
  }
  py += binsTopGap;

  const binImgs = await Promise.all(
    items.map(function (item) {
      return loadMixBinImage(mixBinSvg(item), binW * 2);
    })
  );

  const gridX = panelX + (panelW - gridW) / 2;
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    const col = i % cols;
    const row = Math.floor(i / cols);
    const bx = gridX + col * (binW + binGapX);
    const by = py + row * (cellH + binGapY);
    const img = binImgs[i];
    if (img) {
      ctx.drawImage(img, bx, by, binW, binH);
    } else {
      drawMixBinFallback(ctx, item, bx, by, binW, binH);
    }
    ctx.fillStyle = COLORS.muted;
    ctx.font = '650 24px "Outfit", "Segoe UI", sans-serif';
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillText(item.short || item.label, bx + binW / 2, by + binH + labelGap);
  }
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";

  drawFooter(ctx);

  const filename = "escilo-" + slugify(name) + "-mix.png";
  return canvasToShareFile(canvas, filename);
}

/**
 * Story card: produzione kg/ab — stessi cassonetti misuratori della UI.
 * @param {object} rec
 * @param {object} baselines
 */
export async function buildProdCard(rec, baselines) {
  await ensureFonts();
  const resolved = resolveProdBins(rec, baselines || {});
  if (!resolved.bins.length) throw new Error("Prod unavailable");

  const mark = await loadBrandMark();
  const markLight = mark ? tintMarkLight(mark) : null;
  const canvas = document.createElement("canvas");
  canvas.width = CARD_W;
  canvas.height = CARD_H;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas unavailable");

  drawBackground(ctx);
  drawBrandHeader(ctx, markLight, 56);

  const name = rec.name || "Comune";
  const afterNameY = drawComuneNameBox(ctx, rec, 230);
  const padX = 40;
  const cardX = 48;
  const cardW = CARD_W - 96;
  let y = afterNameY + 28;

  const bins = resolved.bins;
  const n = bins.length;
  const cols = n;
  const panelX = cardX;
  const panelW = cardW;
  const panelPadX = padX;
  const panelPadTop = 44;
  const panelPadBot = 48;
  const titleH = 36;
  const leadGap = 18;
  const leadLineH = 34;
  const lead = "Tutti i valori sono in kg/abitante anno.";
  ctx.font = '500 26px "Outfit", "Segoe UI", sans-serif';
  const leadLines = wrapText(ctx, lead, panelW - panelPadX * 2);
  const leadH = leadLines.length * leadLineH;
  const binsTopGap = 28;
  const binGapX = 36;
  const labelH = 36;
  const labelGap = 10;
  const hintLineH = 30;
  const hintGap = 10;
  const legendGap = 28;
  const legendH = 36;
  const innerW = panelW - panelPadX * 2;
  const binW = Math.min(
    360,
    Math.floor((innerW - binGapX * (cols - 1)) / cols)
  );
  const binH = Math.round((binW * 127) / 100);

  let maxHintLines = 1;
  ctx.font = '550 22px "Outfit", "Segoe UI", sans-serif';
  bins.forEach(function (bin) {
    if (!bin.hint) return;
    const lines = wrapText(ctx, bin.hint, binW);
    if (lines.length > maxHintLines) maxHintLines = lines.length;
  });
  const hintBlockH = maxHintLines * hintLineH;
  const cellH = binH + labelGap + labelH + hintGap + hintBlockH;
  const gridW = cols * binW + (cols - 1) * binGapX;
  const panelH =
    panelPadTop +
    titleH +
    leadGap +
    leadH +
    binsTopGap +
    cellH +
    legendGap +
    legendH +
    panelPadBot;

  roundRect(ctx, panelX, y, panelW, panelH, 48);
  ctx.fillStyle = COLORS.surface;
  ctx.fill();

  let py = y + panelPadTop;
  ctx.fillStyle = COLORS.muted;
  ctx.font = '700 28px "Outfit", "Segoe UI", sans-serif';
  try {
    ctx.letterSpacing = "0.04em";
  } catch {
    /* ignore */
  }
  ctx.fillText("QUANTO PRODUCIAMO", panelX + panelPadX, py + 8);
  try {
    ctx.letterSpacing = "0px";
  } catch {
    /* ignore */
  }
  py += titleH + leadGap;

  ctx.fillStyle = COLORS.muted;
  ctx.font = '500 26px "Outfit", "Segoe UI", sans-serif';
  for (let i = 0; i < leadLines.length; i++) {
    ctx.fillText(leadLines[i], panelX + panelPadX, py + 22);
    py += leadLineH;
  }
  py += binsTopGap;

  resetProdBinSvgSeq();
  const binImgs = await Promise.all(
    bins.map(function (bin) {
      return loadMixBinImage(
        prodBinMeasureSvg(bin.value, bin.medianIt, bin.medianReg, bin.kind),
        binW * 2
      );
    })
  );

  const gridX = panelX + (panelW - gridW) / 2;
  for (let i = 0; i < bins.length; i++) {
    const bin = bins[i];
    const bx = gridX + i * (binW + binGapX);
    const by = py;
    const img = binImgs[i];
    if (img) {
      ctx.drawImage(img, bx, by, binW, binH);
    }
    ctx.fillStyle = COLORS.ink;
    ctx.font = '700 26px "Outfit", "Segoe UI", sans-serif';
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillText(bin.label, bx + binW / 2, by + binH + labelGap);

    if (bin.hint) {
      ctx.fillStyle = COLORS.muted;
      ctx.font = '550 22px "Outfit", "Segoe UI", sans-serif';
      const hintLines = wrapText(ctx, bin.hint, binW);
      let hy = by + binH + labelGap + labelH + hintGap;
      for (let h = 0; h < hintLines.length; h++) {
        ctx.fillText(hintLines[h], bx + binW / 2, hy);
        hy += hintLineH;
      }
    }
  }
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";

  const legendY = py + cellH + legendGap + 10;
  const legendItems = [
    { label: (rec.name || "").trim() || "Comune", fill: "#1f5c42" },
    { label: "Italia", fill: "#142018" },
  ];
  if (resolved.regione) {
    legendItems.push({ label: resolved.regione, fill: "#3d6eb5" });
  }
  ctx.font = '600 22px "Outfit", "Segoe UI", sans-serif';
  const legendGapX = 28;
  const dotR = 7;
  let legendW = 0;
  const measures = legendItems.map(function (item) {
    const tw = ctx.measureText(item.label).width;
    const w = dotR * 2 + 10 + tw;
    legendW += w;
    return w;
  });
  legendW += legendGapX * (legendItems.length - 1);
  let lx = panelX + (panelW - legendW) / 2;
  for (let i = 0; i < legendItems.length; i++) {
    const item = legendItems[i];
    ctx.beginPath();
    ctx.arc(lx + dotR, legendY, dotR, 0, Math.PI * 2);
    ctx.fillStyle = item.fill;
    ctx.fill();
    ctx.fillStyle = COLORS.muted;
    ctx.textBaseline = "middle";
    ctx.fillText(item.label, lx + dotR * 2 + 10, legendY);
    lx += measures[i] + legendGapX;
  }
  ctx.textBaseline = "alphabetic";

  drawFooter(ctx);

  const filename = "escilo-" + slugify(name) + "-prod.png";
  return canvasToShareFile(canvas, filename);
}
