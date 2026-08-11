import { $ } from "../shared/dom.js";
import { state } from "../state.js";

/** Escilo calendar subset remains at data/ispr/comuni-by-id.json for smoke/compat. */

export async function loadIsprDirectory() {
  const res = await fetch("data/ispr/directory.json");
  if (!res.ok) return;
  const data = await res.json();
  if (!data || !Array.isArray(data.comuni)) return;
  state.isprDirectory = data.comuni;
}

export function ensureIsprDirectory() {
  if (state.isprDirectory) return Promise.resolve();
  if (!state.isprDirectoryPromise) {
    state.isprDirectoryPromise = loadIsprDirectory().catch((err) => {
      state.isprDirectoryPromise = null;
      throw err;
    });
  }
  return state.isprDirectoryPromise;
}

export async function loadIsprBaselines() {
  if (state.isprBaselines) return;
  const res = await fetch("data/ispr/baselines-it.json");
  if (!res.ok) return;
  const data = await res.json();
  if (!data) return;
  state.isprBaselines = data;
}

export async function loadIsprComune(comuneId) {
  if (!comuneId) return null;
  if (state.isprComuneCache && state.isprComuneCache[comuneId]) {
    return state.isprComuneCache[comuneId];
  }
  const res = await fetch("data/ispr/c/" + encodeURIComponent(comuneId) + ".json");
  if (!res.ok) return null;
  const rec = await res.json();
  if (!rec || rec.rd_pct == null) return null;
  if (!state.isprComuneCache) state.isprComuneCache = {};
  state.isprComuneCache[comuneId] = rec;
  return rec;
}

/** Compat: teaser still expects state.isprStats shape with comuni map + baselines. */
export async function loadIsprStats() {
  await loadIsprBaselines();
  const baselines = state.isprBaselines;
  if (!baselines) return;
  const years = baselines.years || {};
  const latest = String(baselines.latestYear || "2024");
  const y = years[latest] || {};
  state.isprStats = {
    latestYear: baselines.latestYear,
    comuni: state.isprComuneCache || {},
    baselines: {
      rd_pct_median: y.rd_pct && y.rd_pct.median,
      rd_pct_n: y.rd_pct && y.rd_pct.n,
      kg_ru_ab_median: y.kg_ru_ab && y.kg_ru_ab.median,
      kg_ind_ab_median: y.kg_ind_ab && y.kg_ind_ab.median,
      by_regione: baselines.by_regione || {},
      by_provincia: baselines.by_provincia || {},
      pop_clusters: baselines.pop_clusters || [],
    },
  };
}

export function ensureIsprStats() {
  if (state.isprStats && state.isprBaselines) return Promise.resolve();
  if (!state.isprStatsPromise) {
    state.isprStatsPromise = loadIsprStats().catch((err) => {
      state.isprStatsPromise = null;
      throw err;
    });
  }
  return state.isprStatsPromise;
}

export function hideStatsTeaser() {
  const el = $("statsTeaser");
  if (el) {
    el.hidden = true;
    el.classList.remove("is-visible");
  }
  const nav = $("navStats");
  if (nav) nav.hidden = true;
  const bottomNav = $("bottomNav");
  if (bottomNav) bottomNav.classList.remove("has-stats");
}

export function renderStatsTeaser(comuneId, comuneName, rec) {
  const el = $("statsTeaser");
  if (!el) return;
  if (!rec || !comuneId || rec.rd_pct == null) {
    hideStatsTeaser();
    return;
  }
  const rd = Number(rec.rd_pct);
  $("statsTeaserRd").textContent =
    rd.toLocaleString("it-IT", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";

  const indCol = $("statsTeaserIndCol");
  const indEl = $("statsTeaserInd");
  const medInd =
    state.isprStats &&
    state.isprStats.baselines &&
    state.isprStats.baselines.kg_ind_ab_median;
  const kgInd = rec.kg_ind_ab;
  if (medInd != null && medInd > 0 && kgInd != null) {
    const pctVs = ((kgInd - medInd) / medInd) * 100;
    const absPct = Math.round(Math.abs(pctVs));
    indEl.classList.remove("is-good", "is-bad", "is-mid");
    if (Math.abs(pctVs) < 2) {
      indEl.textContent = "0%";
      indEl.classList.add("is-mid");
    } else if (pctVs > 0) {
      indEl.textContent = "+" + absPct + "%";
      indEl.classList.add("is-bad");
    } else {
      indEl.textContent = "−" + absPct + "%";
      indEl.classList.add("is-good");
    }
    indCol.hidden = false;
    el.classList.remove("is-single");
  } else {
    indEl.textContent = "—";
    indEl.classList.remove("is-good", "is-bad", "is-mid");
    indCol.hidden = true;
    el.classList.add("is-single");
  }
  const href = "stats.html?comune=" + encodeURIComponent(comuneId);
  el.href = href;
  const name = comuneName ? String(comuneName) : "il tuo comune";
  el.setAttribute(
    "aria-label",
    "Anteprima dati rifiuti di " + name + ": apri tutte le metriche"
  );
  el.hidden = false;
  el.classList.add("is-visible");
  const nav = $("navStats");
  if (nav) {
    nav.href = href;
    nav.hidden = false;
  }
  const bottomNav = $("bottomNav");
  if (bottomNav) bottomNav.classList.add("has-stats");
}

export function refreshStatsTeaser() {
  if (!state.zoneChoice) {
    hideStatsTeaser();
    return;
  }
  const id = state.zoneChoice.comuneId;
  const name = state.zoneChoice.comuneName;
  ensureIsprStats()
    .then(() => loadIsprComune(id))
    .then((rec) => {
      if (rec && state.isprStats) {
        if (!state.isprStats.comuni) state.isprStats.comuni = {};
        state.isprStats.comuni[id] = rec;
      }
      renderStatsTeaser(id, name, rec);
    })
    .catch((err) => {
      console.error(err);
      hideStatsTeaser();
    });
}
