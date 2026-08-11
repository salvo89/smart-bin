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
import {
  bindShareStatsSheet,
  setShareStatsContext,
} from "./share/stats-share-ui.js";

const MIX_LABELS = [
  { key: "umida", label: "Organico / umido", cls: "mix-o" },
  { key: "carta", label: "Carta e cartone", cls: "mix-c" },
  { key: "plastica", label: "Plastica", cls: "mix-p" },
  { key: "verde", label: "Verde", cls: "mix-v" },
  { key: "vetro", label: "Vetro", cls: "mix-g" },
];

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

function renderSpark(series) {
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
  const H = 128;
  const left = 28;
  const right = W - 28;
  const top = 26;
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
  root.className = "trend-chart" + (dir ? " " + dir : "");

  const labels = plotted
    .map(function (p) {
      return (
        '<text class="tl-val" x="' +
        p.x.toFixed(1) +
        '" y="' +
        (p.y - 12).toFixed(1) +
        '">' +
        fmtPct(p.v, 1) +
        "</text>" +
        '<circle class="tl-dot" cx="' +
        p.x.toFixed(1) +
        '" cy="' +
        p.y.toFixed(1) +
        '" r="4.5"/>' +
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
    labels +
    "</svg>";

  root.setAttribute(
    "aria-label",
    "Raccolta differenziata: " +
      plotted
        .map(function (p) {
          return p.year + " " + fmtPct(p.v, 1);
        })
        .join(", ")
  );
}

function renderMix(mix) {
  const root = $("mix");
  const items = MIX_LABELS.map((item) => {
    const v = mix && mix[item.key];
    if (v == null) return null;
    return { ...item, v: Number(v), w: Math.max(0, Math.min(100, Number(v))) };
  })
    .filter(Boolean)
    .sort((a, b) => b.v - a.v);

  if (!items.length) {
    root.innerHTML =
      '<p class="lead" style="margin:0">Mix frazioni non disponibile per questo comune.</p>';
    return;
  }

  const sum = items.reduce((acc, item) => acc + item.v, 0);
  const rest = Math.max(0, 100 - sum);
  if (rest >= 0.5) {
    items.push({
      key: "altro",
      label: "Altro",
      cls: "mix-x",
      v: rest,
      w: Math.min(100, rest),
    });
  }

  const segs = items
    .map(
      (item) =>
        '<span class="mix-seg ' +
        item.cls +
        '" style="width:' +
        item.w +
        '%" title="' +
        item.label +
        ": " +
        fmtPct(item.v, 1) +
        '"></span>'
    )
    .join("");
  const legend = items
    .map(
      (item) =>
        '<div class="mix-item">' +
        '<span class="mix-dot ' +
        item.cls +
        '" aria-hidden="true"></span>' +
        "<span>" +
        item.label +
        "</span>" +
        '<span class="pct">' +
        fmtPct(item.v, 1) +
        "</span>" +
        "</div>"
    )
    .join("");

  root.innerHTML =
    '<div class="mix-stack" role="img" aria-label="Composizione della differenziata">' +
    segs +
    "</div>" +
    '<div class="mix-legend">' +
    legend +
    "</div>";
}

function renderProdCards(rec, baselines) {
  const root = $("prodCards");
  const medRu = baselines.kg_ru_ab_median;
  const medInd = baselines.kg_ind_ab_median;
  const regione = (rec.regione || "").trim();
  const regBase =
    (baselines.by_regione && regione && baselines.by_regione[regione]) || null;
  const medRuReg = regBase && regBase.kg_ru_ab_median;
  const medIndReg = regBase && regBase.kg_ind_ab_median;
  const ru = rec.kg_ru_ab;
  const ind = rec.kg_ind_ab;
  const legendReg = $("prodLegendReg");
  if (legendReg) legendReg.textContent = regione || "Regione";

  function medianMarker(pct, value, kind, title) {
    // Keep regional labels centered on the marker; only Italy may shift at edges.
    const edge =
      kind === "reg"
        ? ""
        : pct < 12
          ? " is-edge-left"
          : pct > 88
            ? " is-edge-right"
            : "";
    return (
      '<span class="prod-median prod-median--' +
      kind +
      edge +
      '" style="left:' +
      pct.toFixed(1) +
      '%" title="' +
      title +
      '">' +
      '<span class="prod-median-val">' +
      fmtNum(value, 0) +
      "</span>" +
      "</span>"
    );
  }

  function barBlock(label, value, medianIt, medianReg) {
    if (value == null || medianIt == null) {
      return (
        '<article class="prod-card"><div class="prod-head"><h3>' +
        label +
        '</h3></div><p class="prod-hint">dato non disponibile</p></article>'
      );
    }
    const refs = [value, medianIt];
    if (medianReg != null) refs.push(medianReg);
    const max = Math.max.apply(null, refs.concat([1])) * 1.08;
    const wVal = Math.max(4, Math.min(100, (value / max) * 100));
    const wMedIt = Math.max(2, Math.min(98, (medianIt / max) * 100));
    const wMedReg =
      medianReg != null ? Math.max(2, Math.min(98, (medianReg / max) * 100)) : null;
    const d = value - medianIt;
    const tone = toneClass(d, true);
    const fillTone = Math.abs(d) < 0.5 ? "" : d > 0 ? " is-bad" : " is-good";
    const markers =
      medianMarker(wMedIt, medianIt, "it", "Mediana Italia") +
      (wMedReg != null
        ? medianMarker(
            wMedReg,
            medianReg,
            "reg",
            "Mediana " + (regione || "regione")
          )
        : "");
    const hint = pctVsMediansHint(value, medianIt, medianReg, regione);
    return (
      '<article class="prod-card">' +
      '<div class="prod-head"><h3>' +
      label +
      "</h3>" +
      '<span class="prod-val ' +
      tone +
      '">' +
      fmtNum(value, 0) +
      "</span></div>" +
      '<div class="prod-track-wrap' +
      (wMedReg != null ? " has-reg" : "") +
      '"><div class="prod-track">' +
      '<div class="prod-fill' +
      fillTone +
      '" style="width:' +
      wVal.toFixed(1) +
      '%"></div>' +
      markers +
      "</div></div>" +
      (hint ? '<p class="prod-hint">' + hint + "</p>" : "") +
      "</article>"
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

  function pctVsMediansHint(value, medianIt, medianReg, regName) {
    const it = pctVsOne(value, medianIt, "Italia");
    const reg = pctVsOne(value, medianReg, regName || "regione");
    const parts = [];
    if (it) parts.push(it);
    if (reg) parts.push(reg);
    if (!parts.length) return "";
    const joined = parts.join(" · ");
    return joined.charAt(0).toUpperCase() + joined.slice(1);
  }

  root.innerHTML =
    barBlock("Rifiuti urbani totali", ru, medRu, medRuReg) +
    barBlock("Solo indifferenziato", ind, medInd, medIndReg);
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
  // Parentheses mark the companion figure as delta vs the comune.
  deltaEl.textContent = d.text === "—" ? "—" : "(" + d.text + ")";
  deltaEl.className = "kpi-bench-delta" + (d.tone ? " " + d.tone : "");
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
        '<div class="pop-cluster-stat">' +
        '<p class="pop-cluster-stat-label">Mediana Italia</p>' +
        '<p class="pop-cluster-med">' +
        fmtPct(c.rd_pct_median, 1) +
        "</p>" +
        "</div>" +
        '<p class="pop-cluster-meta">' +
        n +
        " comuni in questo cluster</p>" +
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

function renderKpiBench(rec, baselines) {
  const root = $("kpiBench");
  if (!root) return;
  const rd = rec.rd_pct;
  const medIt = baselines && baselines.rd_pct_median;
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
  const medProv = provBase && provBase.rd_pct_median;
  const medReg = regBase && regBase.rd_pct_median;

  const clusters = (baselines && baselines.pop_clusters) || [];
  const peer =
    (rec.pop_cluster_id &&
      clusters.find(function (c) {
        return c && c.id === rec.pop_cluster_id;
      })) ||
    null;
  const medPeer =
    peer && peer.rd_pct_n >= 30 ? peer.rd_pct_median : null;
  const peerCell = $("kpiBenchPeerCell");
  const showPeer = medPeer != null;

  const agg = rec.aggregation;
  const clusterPop =
    agg && agg.n >= 2 && agg.pop != null ? agg.pop : rec.pop;
  popClustersState = {
    clusters: clusters,
    currentId: peer && peer.id,
    pop: clusterPop,
    aggregation: agg && agg.n >= 2 ? agg : null,
  };

  if (medProv == null && medReg == null && medIt == null && !showPeer) {
    root.hidden = true;
    return;
  }

  const provLabel = $("kpiBenchProvLabel");
  const regLabel = $("kpiBenchRegLabel");
  const peerBtn = $("btnPopClusters");
  if (provLabel) provLabel.textContent = shortProvinciaLabel(provincia);
  if (regLabel) regLabel.textContent = regione || "Regione";
  if (peerBtn) {
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

  fillBenchCell("kpiBenchProv", "kpiBenchProvDelta", medProv, rd);
  fillBenchCell("kpiBenchReg", "kpiBenchRegDelta", medReg, rd);
  fillBenchCell("kpiBenchIt", "kpiBenchItDelta", medIt, rd);
  if (peerCell) {
    peerCell.hidden = !showPeer;
    if (showPeer) fillBenchCell("kpiBenchPeer", "kpiBenchPeerDelta", medPeer, rd);
  }
  root.classList.toggle("is-three", !showPeer);

  const parts = [];
  if (medProv != null) {
    parts.push(
      shortProvinciaLabel(provincia) +
        " " +
        fmtPct(medProv, 1) +
        " (" +
        fmtDeltaPp(rd, medProv).text +
        ")"
    );
  }
  if (medReg != null) {
    parts.push(
      (regione || "Regione") +
        " " +
        fmtPct(medReg, 1) +
        " (" +
        fmtDeltaPp(rd, medReg).text +
        ")"
    );
  }
  if (medIt != null) {
    parts.push(
      "Italia " + fmtPct(medIt, 1) + " (" + fmtDeltaPp(rd, medIt).text + ")"
    );
  }
  if (showPeer) {
    parts.push(
      "Per abitanti" +
        (peer && peer.label ? " (" + peer.label + ")" : "") +
        " " +
        fmtPct(medPeer, 1) +
        " (" +
        fmtDeltaPp(rd, medPeer).text +
        ")"
    );
  }
  root.setAttribute(
    "aria-label",
    "Confronti mediana ISPRA: " + parts.join("; ")
  );
  root.hidden = false;
}

function render(rec, baselines) {
  $("content").hidden = false;
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

  $("kpiRd").textContent = fmtPct(rec.rd_pct, 1);
  $("kpiRdSub").textContent = rdRankBandMessage(
    rec.rd_pctile_it,
    baselines && baselines.rd_pct_n
  );
  renderKpiBench(rec, baselines || {});

  renderSpark(rec.series_rd || {});
  const delta = rec.delta_rd_22_24;
  const deltaEl = $("trendDelta");
  if (delta == null) {
    deltaEl.textContent = "Serie storica incompleta.";
    deltaEl.removeAttribute("aria-label");
    deltaEl.className = "delta-chip is-plain";
  } else {
    const abs = fmtNum(Math.abs(delta), 1);
    const signed = (delta >= 0 ? "+" : "−") + abs;
    deltaEl.className = "delta-chip " + toneClass(delta, false);
    deltaEl.textContent = signed + "% · 2022→2024";
    deltaEl.setAttribute(
      "aria-label",
      (delta >= 0 ? "In crescita di " : "In calo di ") +
        abs +
        "% dal 2022 al 2024."
    );
  }

  renderProdCards(rec, baselines || {});
  renderMix(rec.mix_rd_pct || {});
  setShareStatsContext(rec, baselines || {});
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
bindPopClustersSheet();
bindShareStatsSheet();
main();
