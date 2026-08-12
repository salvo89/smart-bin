import { $ } from "../shared/dom.js";
import { shareFiles } from "../shared/share.js";
import { parseMixItems } from "./mix-helpers.js";
import { resolveProdBins } from "./prod-variants.js";
import { buildSingleCard, buildMixCard, buildProdCard } from "./stats-cards.js?v=43";

let currentRec = null;
let currentBaselines = null;
let sharing = false;
let sharingMix = false;
let sharingProd = false;

const LS_KPI_COST_ON = "escilo.kpiCostOn";

function isKpiCostOn() {
  const toggle = $("kpiCostToggle");
  if (toggle && toggle.hidden) return false;
  const chk = $("chkKpiCost");
  if (chk) return !!chk.checked;
  return localStorage.getItem(LS_KPI_COST_ON) === "1";
}

function setShareLoading(on) {
  const btn = $("btnShareStats");
  if (!btn) return;
  btn.classList.toggle("is-loading", !!on);
  btn.disabled = !!on;
  btn.setAttribute("aria-busy", on ? "true" : "false");
  const overlay = $("shareStatsLoader");
  if (overlay) overlay.hidden = !on;
}

function setShareMixLoading(on) {
  const btn = $("btnShareMix");
  if (!btn) return;
  btn.classList.toggle("is-loading", !!on);
  btn.disabled = !!on;
  btn.setAttribute("aria-busy", on ? "true" : "false");
  const overlay = $("shareMixLoader");
  if (overlay) overlay.hidden = !on;
}

function setShareProdLoading(on) {
  const btn = $("btnShareProd");
  if (!btn) return;
  btn.classList.toggle("is-loading", !!on);
  btn.disabled = !!on;
  btn.setAttribute("aria-busy", on ? "true" : "false");
  const overlay = $("shareProdLoader");
  if (overlay) overlay.hidden = !on;
}

export function setShareStatsContext(rec, baselines) {
  currentRec = rec;
  currentBaselines = baselines || {};
  const btn = $("btnShareStats");
  if (btn) btn.hidden = !rec;
  setShareMixContext(rec, baselines);
  setShareProdContext(rec, baselines);
}

export function setShareMixContext(rec) {
  const btn = $("btnShareMix");
  const items = rec && parseMixItems(rec.mix_rd_pct || {});
  if (btn) btn.hidden = !items || !items.length;
}

export function setShareProdContext(rec, baselines) {
  const btn = $("btnShareProd");
  const bins = rec && resolveProdBins(rec, baselines || {}).bins;
  if (btn) btn.hidden = !bins || !bins.length;
}

async function shareNow() {
  if (!currentRec || sharing || sharingMix || sharingProd) return;
  sharing = true;
  setShareLoading(true);
  try {
    const hasCost =
      currentRec.costo_tot_ab != null &&
      !Number.isNaN(Number(currentRec.costo_tot_ab));
    const costOn = hasCost && isKpiCostOn();
    const result = await buildSingleCard(currentRec, currentBaselines || {}, {
      costOn: costOn,
    });
    const name = currentRec.name || "il tuo comune";
    const rd =
      currentRec.rd_pct != null && !Number.isNaN(Number(currentRec.rd_pct))
        ? Number(currentRec.rd_pct).toLocaleString("it-IT", {
            minimumFractionDigits: 1,
            maximumFractionDigits: 1,
          }) + "%"
        : "";
    const cost =
      costOn &&
      Number(currentRec.costo_tot_ab).toLocaleString("it-IT", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }) + " €/ab";
    const url =
      location.origin +
      "/stats.html?comune=" +
      encodeURIComponent(currentRec.id || "");
    let text;
    if (rd && cost) {
      text =
        "A " +
        name +
        " la differenziata è al " +
        rd +
        " · costo " +
        cost +
        " — dati su Escilo " +
        url;
    } else if (rd) {
      text =
        "A " + name + " la differenziata è al " + rd + " — dati su Escilo " + url;
    } else {
      text = "Differenziata a " + name + " — Escilo " + url;
    }
    await shareFiles([result.file], {
      title: "Escilo — " + name,
      text,
      url,
    });
  } catch (err) {
    if (err && err.name === "AbortError") return;
    console.error(err);
  } finally {
    sharing = false;
    setShareLoading(false);
  }
}

export function bindShareStatsSheet() {
  const btn = $("btnShareStats");
  if (!btn || btn.dataset.bound === "1") return;
  btn.dataset.bound = "1";
  btn.addEventListener("click", function () {
    void shareNow();
  });
}

async function shareMixNow() {
  if (!currentRec || sharingMix || sharing || sharingProd) return;
  const items = parseMixItems(currentRec.mix_rd_pct || {});
  if (!items.length) return;
  sharingMix = true;
  setShareMixLoading(true);
  try {
    const result = await buildMixCard(currentRec);
    const name = currentRec.name || "il tuo comune";
    const url =
      location.origin +
      "/stats.html?comune=" +
      encodeURIComponent(currentRec.id || "");
    const top = items[0];
    const hook =
      top &&
      (top.short || top.label) +
        " " +
        (top.v != null
          ? Number(top.v).toLocaleString("it-IT", {
              minimumFractionDigits: 0,
              maximumFractionDigits: 0,
            }) + "%"
          : "");
    const text = hook + " del differenziato a " + name + " — Escilo " + url;
    await shareFiles([result.file], {
      title: "Escilo — " + name,
      text,
      url,
    });
  } catch (err) {
    if (err && err.name === "AbortError") return;
    console.error(err);
  } finally {
    sharingMix = false;
    setShareMixLoading(false);
  }
}

export function bindShareMixSheet() {
  const btn = $("btnShareMix");
  if (!btn || btn.dataset.bound === "1") return;
  btn.dataset.bound = "1";
  btn.addEventListener("click", function () {
    void shareMixNow();
  });
}

async function shareProdNow() {
  if (!currentRec || sharingProd || sharing || sharingMix) return;
  const resolved = resolveProdBins(currentRec, currentBaselines || {});
  if (!resolved.bins.length) return;
  sharingProd = true;
  setShareProdLoading(true);
  try {
    const result = await buildProdCard(currentRec, currentBaselines || {});
    const name = currentRec.name || "il tuo comune";
    const url =
      location.origin +
      "/stats.html?comune=" +
      encodeURIComponent(currentRec.id || "");
    const top = resolved.bins[0];
    const kg =
      top &&
      Number(top.value).toLocaleString("it-IT", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      });
    const text =
      (kg ? kg + " kg/ab " + (top.label || "totale").toLowerCase() + " a " : "Produzione rifiuti a ") +
      name +
      " — Escilo " +
      url;
    await shareFiles([result.file], {
      title: "Escilo — " + name,
      text,
      url,
    });
  } catch (err) {
    if (err && err.name === "AbortError") return;
    console.error(err);
  } finally {
    sharingProd = false;
    setShareProdLoading(false);
  }
}

export function bindShareProdSheet() {
  const btn = $("btnShareProd");
  if (!btn || btn.dataset.bound === "1") return;
  btn.dataset.bound = "1";
  btn.addEventListener("click", function () {
    void shareProdNow();
  });
}
