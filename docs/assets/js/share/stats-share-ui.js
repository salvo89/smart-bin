import { $ } from "../shared/dom.js";
import { shareFiles } from "../shared/share.js";
import { buildSingleCard } from "./stats-cards.js?v=28";

let currentRec = null;
let currentBaselines = null;
let sharing = false;

function setShareLoading(on) {
  const btn = $("btnShareStats");
  if (!btn) return;
  btn.classList.toggle("is-loading", !!on);
  btn.disabled = !!on;
  btn.setAttribute("aria-busy", on ? "true" : "false");
  const overlay = $("shareStatsLoader");
  if (overlay) overlay.hidden = !on;
}

export function setShareStatsContext(rec, baselines) {
  currentRec = rec;
  currentBaselines = baselines || {};
  const btn = $("btnShareStats");
  if (btn) btn.hidden = !rec;
}

async function shareNow() {
  if (!currentRec || sharing) return;
  sharing = true;
  setShareLoading(true);
  try {
    const result = await buildSingleCard(currentRec, currentBaselines || {});
    const name = currentRec.name || "il tuo comune";
    const rd =
      currentRec.rd_pct != null && !Number.isNaN(Number(currentRec.rd_pct))
        ? Number(currentRec.rd_pct).toLocaleString("it-IT", {
            minimumFractionDigits: 1,
            maximumFractionDigits: 1,
          }) + "%"
        : "";
    const url =
      location.origin +
      "/stats.html?comune=" +
      encodeURIComponent(currentRec.id || "");
    const text = rd
      ? "A " + name + " la differenziata è al " + rd + " — dati su Escilo " + url
      : "Differenziata a " + name + " — Escilo " + url;
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
