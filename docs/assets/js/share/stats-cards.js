/** Canvas cards 9:16 (1080×1920) for social Stories share. */

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
 * Bench cells like stats.html: label / mediana% / (delta%)
 * @param {CanvasRenderingContext2D} ctx
 */
function drawBenchRow(ctx, cells, x, y, w, h) {
  const n = cells.length;
  if (!n) return;
  const gap = 16;
  const cellW = (w - gap * (n - 1)) / n;
  for (let i = 0; i < n; i++) {
    const cell = cells[i];
    const cx = x + i * (cellW + gap);
    roundRect(ctx, cx, y, cellW, h, 28);
    ctx.fillStyle = "#f0f5f2";
    ctx.fill();

    ctx.fillStyle = COLORS.muted;
    ctx.font = '650 22px "Outfit", "Segoe UI", sans-serif';
    ctx.textAlign = "center";
    ctx.fillText(cell.label, cx + cellW / 2, y + 42);

    ctx.fillStyle = COLORS.ink;
    ctx.font = '700 40px "Outfit", "Segoe UI", sans-serif';
    ctx.fillText(cell.value, cx + cellW / 2, y + 96);

    ctx.fillStyle = cell.tone === "good" ? COLORS.accent : cell.tone === "bad" ? "#8b3a3a" : COLORS.muted;
    ctx.font = '650 28px "Outfit", "Segoe UI", sans-serif';
    ctx.fillText(cell.delta, cx + cellW / 2, y + 142);
  }
  ctx.textAlign = "left";
}

/**
 * @param {object} rec
 * @param {object} baselines
 */
export async function buildSingleCard(rec, baselines) {
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
  const nameBoxY = 230;

  roundRect(ctx, nameBoxX, nameBoxY, nameBoxW, nameBoxH, 36);
  ctx.fillStyle = COLORS.surface;
  ctx.fill();

  // box-title style (chrome.css)
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

  const afterNameY = nameBoxY + nameBoxH;
  const rd = rec.rd_pct;
  const provincia = (rec.provincia || "").trim();
  const regione = (rec.regione || "").trim();
  const medIt = baselines && baselines.rd_pct_median;
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
  const medProv = provBase && provBase.rd_pct_median;
  const medReg = regBase && regBase.rd_pct_median;

  const cells = [];
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

  const band = rdRankBandMessage(
    rec.rd_pctile_it,
    baselines && baselines.rd_pct_n
  );
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

  // box-title style (chrome.css): Outfit 700 uppercase muted + letter-spacing
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
  ctx.fillStyle = COLORS.accent;
  ctx.font = '700 148px "Fraunces", Georgia, serif';
  ctx.fillText(fmtPct(rec.rd_pct, 1), cardX + padX, cy + 120);
  cy += valueH + gapAfterValue;

  ctx.fillStyle = COLORS.ink;
  ctx.font = '600 34px "Outfit", "Segoe UI", sans-serif';
  for (let i = 0; i < bandLines.length; i++) {
    ctx.fillText(bandLines[i], cardX + padX, cy + 30);
    cy += 44;
  }

  if (cells.length) {
    drawBenchRow(ctx, cells, cardX + 40, cy + 12, cardW - 80, benchH);
  }

  drawFooter(ctx);

  const filename = "escilo-" + slugify(name) + "-rd.png";
  return canvasToShareFile(canvas, filename);
}
