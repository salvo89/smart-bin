import {
  LS_COMUNE,
  LS_COMUNE_NAME,
  LS_VIA,
  LS_CALENDAR,
  LS_ACCESS_MODE,
  LS_ISTAT,
  ACCESS_STATS,
  contactMailto,
} from "./shared/constants.js";
import { $ } from "./shared/dom.js";
import { initIosBar } from "./shared/ios-bar.js";
import { shareStatsPageLink } from "./shared/share.js";
import {
  bindShareStatsSheet,
  bindShareMixSheet,
  bindShareProdSheet,
  setShareStatsContext,
} from "./share/stats-share-ui.js";
import { parseMixItems } from "./share/mix-helpers.js";
import { renderMixWidget, observeMixBinsLayout } from "./share/mix-variants.js";
import {
  PROD_BIN_KINDS,
  prodBinMeasureSvg,
  resolveProdBins,
  resetProdBinSvgSeq,
} from "./share/prod-variants.js";

const LS_KPI_COST_ON = "escilo.kpiCostOn";

/** @type {{ rec: object | null, baselines: object | null }} */
let kpiCtx = { rec: null, baselines: null };
function fmtPct(n, digits) {
  if (n == null || Number.isNaN(n)) return "—";
  return (
    Number(n).toLocaleString("it-IT", {
      minimumFractionDigits: digits == null ? 1 : digits,
      maximumFractionDigits: digits == null ? 1 : digits,
    }) + "%"
  );
}

function fmtNum(n, digits) {
  if (n == null || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("it-IT", {
    minimumFractionDigits: digits == null ? 0 : digits,
    maximumFractionDigits: digits == null ? 1 : digits,
  });
}

function fmtEuro(n, digits) {
  if (n == null || Number.isNaN(n)) return "—";
  const d = digits == null ? 0 : digits;
  return (
    Number(n).toLocaleString("it-IT", {
      minimumFractionDigits: d,
      maximumFractionDigits: d,
    }) + " €"
  );
}

function toneClass(delta, invert) {
  if (delta == null) return "";
  const good = invert ? delta < 0 : delta > 0;
  const bad = invert ? delta > 0 : delta < 0;
  if (good) return "tone-good";
  if (bad) return "tone-bad";
  return "tone-warn";
}

function comuneIdFromUrl() {
  const q = new URLSearchParams(location.search);
  return (q.get("comune") || "").trim();
}

function resolveComuneId() {
  return comuneIdFromUrl() || localStorage.getItem(LS_COMUNE) || "";
}

function renderSpark(series, delta) {
  const root = $("spark");
  const years = ["2022", "2023", "2024"];
  const pts = years.map((y) => {
    const raw = series[y];
    const v = raw == null || Number.isNaN(Number(raw)) ? null : Number(raw);
    return { y: y, v: v };
  });
  const known = pts.filter((p) => p.v != null);
  if (!known.length) {
    root.className = "trend-chart";
    root.innerHTML = '<p class="lead" style="margin:0">Serie storica non disponibile.</p>';
    root.setAttribute("aria-label", "Andamento non disponibile");
    return;
  }

  const vals = known.map((p) => p.v);
  const min = Math.min.apply(null, vals);
  const max = Math.max.apply(null, vals);
  const pad = Math.max((max - min) * 0.35, 0.9);
  const yMin = min - pad;
  const yMax = max + pad;
  const span = yMax - yMin || 1;

  const W = 320;
  const H = 148;
  const left = 28;
  const right = W - 28;
  const top = 34;
  const bottom = H - 28;
  const n = pts.length;
  const xAt = function (i) {
    return n === 1 ? (left + right) / 2 : left + (i / (n - 1)) * (right - left);
  };
  const yAt = function (v) {
    return top + (1 - (v - yMin) / span) * (bottom - top);
  };

  const plotted = pts
    .map(function (p, i) {
      if (p.v == null) return null;
      return { i: i, x: xAt(i), y: yAt(p.v), v: p.v, year: p.y };
    })
    .filter(Boolean);

  const lineD = plotted
    .map(function (p, i) {
      return (i === 0 ? "M" : "L") + p.x.toFixed(1) + " " + p.y.toFixed(1);
    })
    .join(" ");
  const areaD = plotted.length
    ? lineD +
      " L" +
      plotted[plotted.length - 1].x.toFixed(1) +
      " " +
      bottom.toFixed(1) +
      " L" +
      plotted[0].x.toFixed(1) +
      " " +
      bottom.toFixed(1) +
      " Z"
    : "";

  const first = known[0].v;
  const last = known[known.length - 1].v;
  const dir = last > first + 0.05 ? "is-up" : last < first - 0.05 ? "is-down" : "";
  const tone = toneClass(delta, false);
  root.className =
    "trend-chart" +
    (dir ? " " + dir : "") +
    (tone ? " " + tone : "");

  const lastIdx = plotted.length - 1;
  const labels = plotted
    .map(function (p, idx) {
      const isEnd = idx === lastIdx;
      return (
        '<text class="tl-val" x="' +
        p.x.toFixed(1) +
        '" y="' +
        (p.y - 12).toFixed(1) +
        '">' +
        fmtPct(p.v, 1) +
        "</text>" +
        '<circle class="tl-dot' +
        (isEnd ? " tl-dot-end" : "") +
        '" cx="' +
        p.x.toFixed(1) +
        '" cy="' +
        p.y.toFixed(1) +
        '" r="' +
        (isEnd ? "6" : "4.5") +
        '"/>' +
        '<text class="tl-year" x="' +
        p.x.toFixed(1) +
        '" y="' +
        (H - 8) +
        '">' +
        p.year +
        "</text>"
      );
    })
    .join("");

  let deltaSvg = "";
  let deltaAria = "";
  if (delta != null && plotted.length >= 2) {
    const b = plotted[lastIdx];
    const abs = fmtNum(Math.abs(delta), 1);
    const arrow = delta > 0.05 ? "↑" : delta < -0.05 ? "↓" : "→";
    const signed = arrow + " " + (delta >= 0 ? "+" : "−") + abs + "%";
    deltaAria =
      (delta >= 0 ? "In crescita di " : "In calo di ") +
      abs +
      "% dal 2022 al 2024.";

    const badgeW = 74;
    const badgeH = 30;
    const gap = 12;
    // Keep near the last point (original spot), smaller so it clears % labels.
    let badgeX = b.x - badgeW - 12;
    let badgeY = b.y - badgeH - gap;
    if (badgeX < 6) badgeX = Math.min(W - badgeW - 6, b.x + 8);
    if (badgeY < 4) badgeY = Math.min(bottom - badgeH - 8, b.y + gap);
    // Clear the last point % label (above the dot).
    const lastLabelTop = b.y - 12 - 12;
    if (badgeY + badgeH > lastLabelTop - 3 && badgeX + badgeW > b.x - 28) {
      badgeY = Math.max(4, lastLabelTop - badgeH - 4);
    }
    badgeX = Math.max(6, Math.min(W - badgeW - 6, badgeX));
    badgeY = Math.max(4, Math.min(H - badgeH - 22, badgeY));

    deltaSvg =
      '<g class="tl-delta" aria-hidden="true">' +
      '<g class="tl-delta-badge">' +
      '<rect class="tl-delta-bg" x="' +
      badgeX.toFixed(1) +
      '" y="' +
      badgeY.toFixed(1) +
      '" width="' +
      badgeW +
      '" height="' +
      badgeH +
      '" rx="8" ry="8"/>' +
      '<text class="tl-delta-val" x="' +
      (badgeX + badgeW / 2).toFixed(1) +
      '" y="' +
      (badgeY + 13).toFixed(1) +
      '">' +
      signed +
      "</text>" +
      '<text class="tl-delta-sub" x="' +
      (badgeX + badgeW / 2).toFixed(1) +
      '" y="' +
      (badgeY + 24).toFixed(1) +
      '">2022→2024</text>' +
      "</g></g>";
  }

  root.innerHTML =
    '<svg viewBox="0 0 ' +
    W +
    " " +
    H +
    '" width="100%" height="' +
    H +
    '" aria-hidden="true">' +
    (areaD ? '<path class="tl-area" d="' + areaD + '"/>' : "") +
    (lineD ? '<path class="tl-line" d="' + lineD + '"/>' : "") +
    deltaSvg +
    labels +
    "</svg>";

  root.setAttribute(
    "aria-label",
    "Raccolta differenziata: " +
      plotted
        .map(function (p) {
          return p.year + " " + fmtPct(p.v, 1);
        })
        .join(", ") +
      (deltaAria ? ". " + deltaAria : "")
  );
}

let mixBinsLayoutObserver = null;

function renderMix(mix) {
  const root = $("mix");
  const items = parseMixItems(mix);

  if (mixBinsLayoutObserver) {
    mixBinsLayoutObserver.disconnect();
    mixBinsLayoutObserver = null;
  }

  root.innerHTML = renderMixWidget(items);

  if (items.length) {
    root.setAttribute(
      "aria-label",
      items
        .map(function (item) {
          return item.label + " " + fmtPct(item.v, 1);
        })
        .join(", ")
    );
    mixBinsLayoutObserver = observeMixBinsLayout(root);
  } else {
    root.removeAttribute("aria-label");
  }
}

function renderProdCards(rec, baselines) {
  const root = $("prodCards");
  const resolved = resolveProdBins(rec, baselines || {});
  const regione = resolved.regione;
  const legendCom = $("prodLegendCom");
  if (legendCom) legendCom.textContent = (rec.name || "").trim() || "Comune";
  const legendReg = $("prodLegendReg");
  if (legendReg) legendReg.textContent = regione || "Regione";
  resetProdBinSvgSeq();

  const byKind = {};
  resolved.bins.forEach(function (b) {
    byKind[b.kind] = b;
  });

  function binBlock(kind) {
    const kindMeta = PROD_BIN_KINDS[kind] || PROD_BIN_KINDS.total;
    const bin = byKind[kind];
    if (!bin) {
      return (
        '<article class="prod-bin escilo-block" role="listitem">' +
        '<figure class="prod-bin-fig prod-bin-fig--' +
        kind +
        '">' +
        '<figcaption class="prod-bin-kind">' +
        kindMeta.label +
        "</figcaption></figure>" +
        '<p class="prod-hint">dato non disponibile</p></article>'
      );
    }
    const aria =
      kindMeta.aria +
      ": comune " +
      fmtNum(bin.value, 0) +
      " kg per abitante, Italia " +
      fmtNum(bin.medianIt, 0) +
      (bin.medianReg != null ? ", " + regione + " " + fmtNum(bin.medianReg, 0) : "") +
      ".";
    return (
      '<article class="prod-bin escilo-block" role="listitem">' +
      '<figure class="prod-bin-fig prod-bin-fig--' +
      kind +
      '" aria-label="' +
      aria +
      '">' +
      prodBinMeasureSvg(bin.value, bin.medianIt, bin.medianReg, kind) +
      '<figcaption class="prod-bin-kind">' +
      kindMeta.label +
      "</figcaption></figure>" +
      (bin.hint ? '<p class="prod-hint">' + bin.hint + "</p>" : "") +
      "</article>"
    );
  }

  root.innerHTML = binBlock("total") + binBlock("ind");
}

function fmtTopN(n) {
  return Number(n).toLocaleString("it-IT");
}

/** Fasce nazionali da percentile RD (% comuni con RD più bassa). */
function rdRankBandMessage(pctile, nComuni) {
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

function fmtDeltaPp(comune, ref) {
  if (comune == null || ref == null || Number.isNaN(comune) || Number.isNaN(ref)) {
    return { text: "—", tone: "" };
  }
  const d = Number(comune) - Number(ref);
  if (Math.abs(d) < 0.05) return { text: "in linea", tone: "tone-warn" };
  const abs = Math.abs(d).toLocaleString("it-IT", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  return {
    text: (d >= 0 ? "+" : "−") + abs + "%",
    tone: toneClass(d, false),
  };
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

function shortProvinciaLabel(name) {
  const n = (name || "").trim();
  if (!n) return "Provincia";
  if (/^prov/i.test(n)) return n;
  return "Prov. " + n;
}

function fillBenchCell(valueId, deltaId, median, rd) {
  const valueEl = $(valueId);
  const deltaEl = $(deltaId);
  if (!valueEl || !deltaEl) return;
  valueEl.textContent = fmtPct(median, 1);
  const d = fmtDeltaPp(rd, median);
  deltaEl.textContent = d.text === "—" ? "—" : "(" + d.text + ")";
  deltaEl.className = "kpi-bench-delta" + (d.tone ? " " + d.tone : "");
}

/** Cost overlay: RD median as value, small cost instead of delta %. */
function fillBenchRdWithCost(valueId, deltaId, rdMedian, costMedian) {
  const valueEl = $(valueId);
  const deltaEl = $(deltaId);
  if (!valueEl || !deltaEl) return;
  valueEl.textContent = fmtPct(rdMedian, 1);
  if (costMedian == null || Number.isNaN(Number(costMedian))) {
    deltaEl.textContent = "—";
    deltaEl.className = "kpi-bench-delta kpi-bench-cost";
    return;
  }
  deltaEl.textContent = fmtEuro(costMedian, 0);
  deltaEl.className = "kpi-bench-delta kpi-bench-cost";
}

function hasCostData(rec) {
  return (
    rec &&
    rec.costo_tot_ab != null &&
    !Number.isNaN(Number(rec.costo_tot_ab))
  );
}

function readKpiCostOn() {
  return localStorage.getItem(LS_KPI_COST_ON) === "1";
}

function writeKpiCostOn(on) {
  localStorage.setItem(LS_KPI_COST_ON, on ? "1" : "0");
}

function resolveBenchContext(rec, baselines) {
  const provincia = (rec.provincia || "").trim();
  const regione = (rec.regione || "").trim();
  const provBase =
    (baselines &&
      baselines.by_provincia &&
      provincia &&
      baselines.by_provincia[provincia]) ||
    null;
  const regBase =
    (baselines &&
      baselines.by_regione &&
      regione &&
      baselines.by_regione[regione]) ||
    null;
  const clusters = (baselines && baselines.pop_clusters) || [];
  const peer =
    (rec.pop_cluster_id &&
      clusters.find(function (c) {
        return c && c.id === rec.pop_cluster_id;
      })) ||
    null;
  const agg = rec.aggregation;
  const clusterPop =
    agg && agg.n >= 2 && agg.pop != null ? agg.pop : rec.pop;
  popClustersState = {
    clusters: clusters,
    currentId: peer && peer.id,
    pop: clusterPop,
    aggregation: agg && agg.n >= 2 ? agg : null,
  };
  return {
    provincia: provincia,
    regione: regione,
    peer: peer,
    medRdProv: provBase && provBase.rd_pct_median,
    medRdReg: regBase && regBase.rd_pct_median,
    medRdIt: baselines && baselines.rd_pct_median,
    medRdPeer: peer && peer.rd_pct_n >= 30 ? peer.rd_pct_median : null,
    medCostProv: provBase && provBase.costo_tot_ab_median,
    medCostReg: regBase && regBase.costo_tot_ab_median,
    medCostIt: baselines && baselines.costo_tot_ab_median,
    medCostPeer:
      peer && peer.costo_tot_ab_n >= 30 ? peer.costo_tot_ab_median : null,
  };
}

function syncPeerButton(peer) {
  const peerBtn = $("btnPopClusters");
  if (!peerBtn) return;
  const fascia = (peer && peer.label) || "";
  peerBtn.setAttribute(
    "aria-label",
    fascia
      ? "Per abitanti, fascia " +
          fascia.replace(/\.$/, "") +
          ". Apri i dettagli sulle fasce di popolazione"
      : "Per abitanti. Apri i dettagli sulle fasce di popolazione"
  );
  peerBtn.title = fascia
    ? "Fascia " + fascia + " · tocca per tutte le fasce"
    : "Tocca per le fasce di popolazione";
}

function renderKpi(rec, baselines) {
  const card = $("kpiCard");
  if (!card || !rec) return;

  kpiCtx = { rec: rec, baselines: baselines || {} };
  const hasCost = hasCostData(rec);
  const costOn = hasCost && readKpiCostOn();
  const ctx = resolveBenchContext(rec, baselines || {});

  const costToggle = $("kpiCostToggle");
  const chk = $("chkKpiCost");
  if (costToggle) costToggle.hidden = !hasCost;
  if (chk) chk.checked = costOn;

  card.classList.toggle("is-cost-overlay", costOn);

  const labelEl = $("kpiLabel");
  const valueEl = $("kpiRd");
  const subEl = $("kpiRdSub");
  const beside = $("kpiCostBeside");
  const besideVal = $("kpiCostBesideVal");
  const root = $("kpiBench");
  const peerCell = $("kpiBenchPeerCell");

  if (labelEl) labelEl.textContent = "Raccolta differenziata";
  valueEl.textContent = fmtPct(rec.rd_pct, 1);
  if (costOn) {
    subEl.textContent = costVsItalyMessage(rec.costo_tot_ab, ctx.medCostIt);
    if (beside) beside.hidden = false;
    if (besideVal) besideVal.textContent = fmtEuro(rec.costo_tot_ab, 0);
  } else {
    subEl.textContent = rdRankBandMessage(
      rec.rd_pctile_it,
      baselines && baselines.rd_pct_n
    );
    if (beside) beside.hidden = true;
  }

  const provLabel = $("kpiBenchProvLabel");
  const regLabel = $("kpiBenchRegLabel");
  if (provLabel) provLabel.textContent = shortProvinciaLabel(ctx.provincia);
  if (regLabel) regLabel.textContent = ctx.regione || "Regione";
  syncPeerButton(ctx.peer);

  const showPeer = ctx.medRdPeer != null;
  if (costOn) {
    fillBenchRdWithCost(
      "kpiBenchProv",
      "kpiBenchProvDelta",
      ctx.medRdProv,
      ctx.medCostProv
    );
    fillBenchRdWithCost(
      "kpiBenchReg",
      "kpiBenchRegDelta",
      ctx.medRdReg,
      ctx.medCostReg
    );
    fillBenchRdWithCost(
      "kpiBenchIt",
      "kpiBenchItDelta",
      ctx.medRdIt,
      ctx.medCostIt
    );
    if (showPeer) {
      fillBenchRdWithCost(
        "kpiBenchPeer",
        "kpiBenchPeerDelta",
        ctx.medRdPeer,
        ctx.medCostPeer
      );
    }
  } else {
    fillBenchCell("kpiBenchProv", "kpiBenchProvDelta", ctx.medRdProv, rec.rd_pct);
    fillBenchCell("kpiBenchReg", "kpiBenchRegDelta", ctx.medRdReg, rec.rd_pct);
    fillBenchCell("kpiBenchIt", "kpiBenchItDelta", ctx.medRdIt, rec.rd_pct);
    if (showPeer) {
      fillBenchCell(
        "kpiBenchPeer",
        "kpiBenchPeerDelta",
        ctx.medRdPeer,
        rec.rd_pct
      );
    }
  }

  if (peerCell) peerCell.hidden = !showPeer;
  if (root) {
    const hasAny =
      ctx.medRdProv != null ||
      ctx.medRdReg != null ||
      ctx.medRdIt != null ||
      showPeer;
    root.classList.toggle("is-three", !showPeer);
    root.hidden = !hasAny;
    root.setAttribute(
      "aria-label",
      costOn
        ? "Confronti RD con costi mediani ISPRA"
        : "Confronti mediana raccolta differenziata ISPRA"
    );
  }
}

function bindKpiControls() {
  const chk = $("chkKpiCost");
  if (!chk || chk.dataset.bound === "1") return;
  chk.dataset.bound = "1";
  chk.addEventListener("change", function () {
    writeKpiCostOn(!!chk.checked);
    if (kpiCtx.rec) renderKpi(kpiCtx.rec, kpiCtx.baselines);
  });
}

let popClustersState = { clusters: [], currentId: null, pop: null };
let sheetScrollY = 0;

function lockPageScroll() {
  sheetScrollY = window.scrollY || window.pageYOffset || 0;
  document.documentElement.classList.add("is-sheet-open");
  document.body.style.top = "-" + sheetScrollY + "px";
}

function unlockPageScroll() {
  document.documentElement.classList.remove("is-sheet-open");
  document.body.style.top = "";
  window.scrollTo(0, sheetScrollY);
}

function renderPopClustersList() {
  const list = $("popClustersList");
  const legend = $("popClustersLegend");
  if (!list) return;
  const clusters = popClustersState.clusters || [];
  const currentId = popClustersState.currentId;
  const pop = popClustersState.pop;
  if (legend) {
    if (pop != null) {
      legend.hidden = false;
      const agg = popClustersState.aggregation;
      if (agg && agg.n >= 2) {
        legend.textContent =
          "Per il confronto usiamo " +
          fmtNum(pop, 0) +
          " abitanti totali dell’aggregazione ISPRA «" +
          (agg.name || "gruppo") +
          "» (" +
          fmtNum(agg.n, 0) +
          " comuni): rientri nel cluster evidenziato.";
      } else {
        legend.textContent =
          "Il tuo comune ha " +
          fmtNum(pop, 0) +
          " abitanti e rientra nel cluster evidenziato.";
      }
    } else {
      legend.hidden = true;
      legend.textContent = "";
    }
  }
  if (!clusters.length) {
    list.innerHTML =
      '<li><p class="pop-cluster-name">Cluster non disponibili.</p></li>';
    return;
  }
  list.innerHTML = clusters
    .map(function (c) {
      const isCurrent = c.id === currentId;
      const n = c.rd_pct_n != null ? fmtNum(c.rd_pct_n, 0) : "—";
      const costMed =
        c.costo_tot_ab_median != null ? fmtEuro(c.costo_tot_ab_median, 0) : null;
      const costN =
        c.costo_tot_ab_n != null && c.costo_tot_ab_n > 0
          ? fmtNum(c.costo_tot_ab_n, 0)
          : null;
      return (
        '<li' +
        (isCurrent ? ' class="is-current"' : "") +
        ">" +
        '<div class="pop-cluster-head">' +
        '<p class="pop-cluster-kicker">Cluster</p>' +
        '<p class="pop-cluster-name">' +
        (c.label || c.id) +
        "</p>" +
        "</div>" +
        '<div class="pop-cluster-stats">' +
        '<p class="pop-cluster-stat-label">Mediane</p>' +
        '<div class="pop-cluster-med-row">' +
        '<p class="pop-cluster-med">' +
        fmtPct(c.rd_pct_median, 1) +
        "</p>" +
        (costMed
          ? '<span class="pop-cluster-cost">' + costMed + "</span>"
          : "") +
        "</div>" +
        "</div>" +
        '<p class="pop-cluster-meta">' +
        n +
        " comuni" +
        (costN ? " · " + costN + " con costo" : "") +
        "</p>" +
        "</li>"
      );
    })
    .join("");
}

function openPopClustersSheet() {
  const sheet = $("popClustersSheet");
  if (!sheet || sheet.hidden === false) return;
  renderPopClustersList();
  lockPageScroll();
  sheet.hidden = false;
  const closeBtn = $("btnPopClustersClose");
  if (closeBtn) closeBtn.focus();
}

function closePopClustersSheet() {
  const sheet = $("popClustersSheet");
  if (!sheet || sheet.hidden) return;
  sheet.hidden = true;
  unlockPageScroll();
  const btn = $("btnPopClusters");
  if (btn) btn.focus();
}

function slugifyRegion(name) {
  let s = String(name || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  if (s.indexOf("trentino") === 0) return "trentino-alto-adige";
  if (s.indexOf("valle-d-aosta") === 0 || s.indexOf("valle-daosta") === 0) {
    return "valle-d-aosta";
  }
  return s;
}

function mapHrefFromRec(rec) {
  if (!rec) return "mappa.html";
  const q = new URLSearchParams();
  if (rec.id) q.set("comune", rec.id);
  const rs = slugifyRegion(rec.regione);
  if (rs) q.set("regione", rs);
  const s = q.toString();
  return s ? "mappa.html?" + s : "mappa.html";
}

function openMapFromKpi() {
  const href = mapHrefFromRec(kpiCtx.rec);
  const card = $("kpiCard");
  const reduce =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!card || reduce) {
    location.href = href;
    return;
  }
  if (card.classList.contains("is-opening-map")) return;
  card.classList.add("is-opening-map");
  window.setTimeout(function () {
    location.href = href;
  }, 280);
}

function bindMapFromKpi() {
  const card = $("kpiCard");
  const valueRow = card && card.querySelector(".kpi-value-row");
  if (!card || card.dataset.mapBound === "1") return;
  card.dataset.mapBound = "1";

  if (!valueRow) return;

  let startX = 0;
  let startY = 0;
  let tracking = false;
  const SWIPE = 56;

  function resetSwipe() {
    tracking = false;
    card.classList.remove("is-swiping");
    card.style.removeProperty("--kpi-swipe");
  }

  valueRow.addEventListener("pointerdown", function (ev) {
    if (ev.button != null && ev.button !== 0) return;
    startX = ev.clientX;
    startY = ev.clientY;
    tracking = true;
    try {
      valueRow.setPointerCapture(ev.pointerId);
    } catch {
      /* ignore */
    }
  });

  valueRow.addEventListener("pointermove", function (ev) {
    if (!tracking) return;
    const dx = ev.clientX - startX;
    const dy = ev.clientY - startY;
    if (Math.abs(dx) > Math.abs(dy)) {
      card.classList.add("is-swiping");
      card.style.setProperty("--kpi-swipe", Math.max(-72, Math.min(72, dx)) + "px");
    }
  });

  valueRow.addEventListener("pointerup", function (ev) {
    if (!tracking) {
      resetSwipe();
      return;
    }
    const dx = ev.clientX - startX;
    const dy = ev.clientY - startY;
    resetSwipe();
    if (Math.abs(dx) >= SWIPE && Math.abs(dx) > Math.abs(dy) * 1.25) {
      openMapFromKpi();
    }
  });

  valueRow.addEventListener("pointercancel", resetSwipe);
}

function bindPopClustersSheet() {
  const btn = $("btnPopClusters");
  const sheet = $("popClustersSheet");
  const closeBtn = $("btnPopClustersClose");
  if (!btn || !sheet || btn.dataset.bound === "1") return;
  btn.dataset.bound = "1";
  btn.addEventListener("click", openPopClustersSheet);
  if (closeBtn) closeBtn.addEventListener("click", closePopClustersSheet);
  sheet.addEventListener("click", function (ev) {
    if (ev.target === sheet) closePopClustersSheet();
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") closePopClustersSheet();
  });
}

function render(rec, baselines) {
  const content = $("content");
  content.hidden = false;
  content.classList.add("escilo-enter");
  const year = rec.year || 2024;
  $("statsYear").textContent = String(year);
  $("statsTitle").textContent = "Come va a " + (rec.name || "questo comune");
  $("statsMeta").textContent = "Numero di abitanti " + fmtNum(rec.pop, 0);
  const aggNote = $("aggNote");
  if (aggNote) {
    const agg = rec.aggregation;
    if (agg && agg.n >= 2 && agg.name) {
      aggNote.hidden = false;
      aggNote.textContent =
        "ISPRA pubblica solo dati aggregati per «" +
        agg.name +
        "» (" +
        fmtNum(agg.n, 0) +
        " comuni" +
        (agg.pop != null ? ", " + fmtNum(agg.pop, 0) + " abitanti totali" : "") +
        "). Percentuali, kg/ab e confronto per abitanti si riferiscono al gruppo.";
    } else {
      aggNote.hidden = true;
      aggNote.textContent = "";
    }
  }

  renderKpi(rec, baselines || {});
  bindMapFromKpi();

  const delta = rec.delta_rd_22_24;
  renderSpark(rec.series_rd || {}, delta);
  const deltaEl = $("trendDelta");
  if (delta == null) {
    deltaEl.hidden = false;
    deltaEl.textContent = "Serie storica incompleta.";
  } else {
    deltaEl.hidden = true;
    deltaEl.textContent = "";
  }

  renderProdCards(rec, baselines || {});
  renderMix(rec.mix_rd_pct || {});
  setShareStatsContext(rec, baselines || {});
  syncIntroShareBtn(rec);
}

let introShareRec = null;

function syncIntroShareBtn(rec) {
  introShareRec = rec || null;
  const btn = $("btnShareIntro");
  if (btn) btn.hidden = !rec;
}

function bindShareIntro() {
  const btn = $("btnShareIntro");
  if (!btn || btn.dataset.bound === "1") return;
  btn.dataset.bound = "1";
  btn.addEventListener("click", function () {
    if (!introShareRec) return;
    void shareStatsPageLink(introShareRec.id, introShareRec.name);
  });
}

function syncBottomNav(comuneId, statsOnly) {
  const q = comuneId ? "?comune=" + encodeURIComponent(comuneId) : "";
  const home = $("navHome");
  const cal = $("navCal");
  const stats = $("navStats");
  if (home) {
    home.href = statsOnly ? "./?reset=1" : "./" + q;
    const svg = home.querySelector("svg");
    home.textContent = "";
    if (svg) home.appendChild(svg);
    home.appendChild(document.createTextNode(statsOnly ? "Cambia" : "Home"));
  }
  if (cal) {
    if (statsOnly) {
      cal.hidden = true;
      cal.removeAttribute("href");
    } else {
      cal.hidden = false;
      cal.href = "./?tab=cal" + (comuneId ? "&comune=" + encodeURIComponent(comuneId) : "");
    }
  }
  if (stats) stats.href = "stats.html" + q;
  const bottomNav = $("bottomNav");
  if (bottomNav) {
    bottomNav.classList.toggle("stats-only", !!statsOnly);
    bottomNav.classList.toggle("has-stats", !statsOnly);
  }
}

function updateZoneMeta(comuneNameOpt) {
  const meta = $("zoneMeta");
  const label = $("zoneLabel");
  if (!meta || !label) return;
  const comuneName = comuneNameOpt || localStorage.getItem(LS_COMUNE_NAME) || "";
  const via = localStorage.getItem(LS_VIA) || "";
  if (!comuneName && !via) {
    meta.hidden = true;
    return;
  }
  label.textContent = via ? comuneName + " · " + via : comuneName || "—";
  meta.hidden = false;
}

function clearChoiceAndGoHome() {
  localStorage.removeItem(LS_COMUNE);
  localStorage.removeItem(LS_COMUNE_NAME);
  localStorage.removeItem(LS_VIA);
  localStorage.removeItem(LS_CALENDAR);
  localStorage.removeItem(LS_ACCESS_MODE);
  localStorage.removeItem(LS_ISTAT);
  location.href = "./";
}

function isStatsOnlyMode() {
  return localStorage.getItem(LS_ACCESS_MODE) === ACCESS_STATS;
}

function syncProposeBanner(rec, statsOnly) {
  const banner = $("proposeBanner");
  if (!banner) return;
  if (!statsOnly || !rec) {
    banner.hidden = true;
    return;
  }
  const name = rec.name || "il tuo comune";
  const text = $("proposeBannerText");
  if (text) {
    text.textContent =
      "Per " +
      name +
      " non abbiamo ancora il calendario porta a porta. Puoi comunque consultare i dati ISPRA.";
  }
  const link = $("proposeBannerLink");
  if (link) {
    link.href = contactMailto("Escilo — proponi calendario " + name);
  }
  banner.hidden = false;
}

function baselinesFromIt(raw) {
  if (!raw) return {};
  const latest = String(raw.latestYear || "2024");
  const y = (raw.years && raw.years[latest]) || {};
  return {
    rd_pct_median: y.rd_pct && y.rd_pct.median,
    rd_pct_n: y.rd_pct && y.rd_pct.n,
    kg_ru_ab_median: y.kg_ru_ab && y.kg_ru_ab.median,
    kg_ind_ab_median: y.kg_ind_ab && y.kg_ind_ab.median,
    costo_tot_ab_median: y.costo_tot_ab && y.costo_tot_ab.median,
    costo_tot_ab_n: y.costo_tot_ab && y.costo_tot_ab.n,
    by_regione: raw.by_regione || {},
    by_provincia: raw.by_provincia || {},
    pop_clusters: raw.pop_clusters || [],
  };
}

async function main() {
  const status = $("status");
  const id = resolveComuneId();
  const statsOnly = isStatsOnlyMode();
  syncBottomNav(id, statsOnly);
  updateZoneMeta();
  const btnChange = $("btnChangeZone");
  if (btnChange) btnChange.addEventListener("click", clearChoiceAndGoHome);
  if (!id) {
    status.hidden = false;
    status.className = "status error";
    status.innerHTML =
      'Nessun comune selezionato. Torna alla <a href="./">home</a> e scegli il tuo comune.';
    return;
  }
  try {
    const [baseRes, comuneRes] = await Promise.all([
      fetch("data/ispr/baselines-it.json", { cache: "no-cache" }),
      fetch("data/ispr/c/" + encodeURIComponent(id) + ".json", { cache: "no-cache" }),
    ]);
    if (!baseRes.ok || !comuneRes.ok) throw new Error("HTTP");
    const rawBase = await baseRes.json();
    const rec = await comuneRes.json();
    if (!rec || rec.rd_pct == null) {
      status.hidden = false;
      status.className = "status error";
      status.textContent =
        "Statistiche ISPRA non disponibili per " +
        (localStorage.getItem(LS_COMUNE_NAME) || id) +
        ".";
      return;
    }
    document.title = "Escilo — differenziata a " + rec.name;
    updateZoneMeta(rec.name);
    syncProposeBanner(rec, statsOnly);
    render(rec, baselinesFromIt(rawBase));
  } catch (err) {
    status.hidden = false;
    status.className = "status error";
    status.textContent = "Impossibile caricare i dati statistici.";
    console.error(err);
  }
}

initIosBar();
bindKpiControls();
bindPopClustersSheet();
bindShareIntro();
bindShareStatsSheet();
bindShareMixSheet();
bindShareProdSheet();
main();
