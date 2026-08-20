/**
 * Smoke check locale: pezzi push presenti e coerenti.
 * Non sostituisce il test device (PWA killata su Android/iOS).
 */
import { readFile } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { matchAndRankItems } from "../../../docs/assets/js/shared/search.js";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");

const mustExist = [
  "netlify/functions/push-subscribe.mjs",
  "netlify/functions/push-unsubscribe.mjs",
  "netlify/functions/push-dispatch.mjs",
  "netlify/functions/push-vapid-public.mjs",
  "docs/sw.js",
  "docs/notify-icon-192.png",
  "docs/calendars/sources-lite.json",
  "docs/data/ispr/comuni-by-id.json",
  "docs/data/ispr/baselines-it.json",
  "docs/data/ispr/directory.json",
  "docs/data/ispr/c/chieri.json",
  "docs/stats.html",
  "docs/privacy.html",
  "docs/assets/fonts/outfit-latin-wght-normal.woff2",
  "docs/assets/fonts/fraunces-latin-wght-normal.woff2",
  "docs/assets/vendor/leaflet/leaflet.js",
  "docs/assets/vendor/leaflet/leaflet.css",
  "docs/mappa.html",
  "docs/data/map/meta.json",
  "docs/data/map/macro.geojson",
  "docs/data/map/regioni.geojson",
  "docs/data/map/province.geojson",
  "docs/data/map/comuni/piemonte.json",
  "docs/robots.txt",
  "docs/sitemap.xml",
  "docs/llms.txt",
  "docs/llms-full.txt",
  "docs/comuni/index.html",
  "docs/comuni/rivoli.html",
  "docs/comuni/roma.html",
  "docs/comuni/regioni/piemonte.html",
  "docs/comuni/regioni/lazio.html",
  "docs/comuni/province/torino.html",
  "docs/comuni/province/roma.html",
  "docs/assets/js/comuni-nav.js",
  "docs/assets/js/shared/search.js",
  "docs/googled19b3747a0a192a7.html",
  "tools/build_seo_pages.py",
  "tools/build_ispr_stats.py",
  ".github/workflows/push-dispatch.yml",
  ".env.example",
];

let failed = 0;

for (const rel of mustExist) {
  try {
    await readFile(join(root, rel));
  } catch {
    console.error("missing", rel);
    failed += 1;
  }
}

const sw = await readFile(join(root, "docs/sw.js"), "utf8");
for (const needle of [
  'addEventListener("push"',
  'addEventListener("notificationclick"',
  "cache-zone",
  "ZONE_CACHE",
  "pickupDate",
  "normalizeBins",
  "notify-icon-192.png",
  'icon: "./notify-icon-192.png"',
]) {
  if (!sw.includes(needle)) {
    console.error("sw.js missing", needle);
    failed += 1;
  }
}

const html = await readFile(join(root, "docs/index.html"), "utf8");
for (const needle of [
  "btnPushOffer",
  "notifySheet",
  "notifyToggle",
  "notify-privacy",
  "privacy.html",
  "statsTeaser",
  'rel="canonical"',
  "application/ld+json",
  'src="assets/js/boot.js"',
  "assets/css/tokens.css",
  "assets/css/chrome.css",
  "assets/css/app.css",
]) {
  if (!html.includes(needle)) {
    console.error("index.html missing", needle);
    failed += 1;
  }
}
for (const banned of ["panelNotify", 'data-tab="notify"', "notifyHistoryList"]) {
  if (html.includes(banned)) {
    console.error("index.html should not include", banned);
    failed += 1;
  }
}

if (html.includes("fonts.googleapis.com")) {
  console.error("index.html should not load Google Fonts");
  failed += 1;
}

/** App logic lives in ES modules under docs/assets/js/ */
const jsRoot = join(root, "docs", "assets", "js");
const { readdir } = await import("node:fs/promises");
async function readJsTree(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const chunks = [];
  for (const ent of entries) {
    const p = join(dir, ent.name);
    if (ent.isDirectory()) chunks.push(await readJsTree(p));
    else if (ent.name.endsWith(".js")) chunks.push(await readFile(p, "utf8"));
  }
  return chunks.join("\n");
}
const appJs = await readJsTree(jsRoot);
for (const needle of [
  "/api/push/subscribe",
  "syncPushOffer",
  "requestNotificationPermission",
  "pushEnableWanted",
  "precacheSelectedZone",
  "cache-zone",
  "ensureZonesIndex",
  "ensureSourcesLite",
  "sources-lite.json",
  "refreshStatsTeaser",
  "data/ispr/directory.json",
  "data/ispr/c/",
  "data/ispr/comuni-by-id.json",
  "initialComuneFromUrl",
  "calendarChoiceIfSingleVia",
  "applyComuneDeepLink",
  "data/map/province.geojson",
]) {
  if (!appJs.includes(needle)) {
    console.error("assets/js missing", needle);
    failed += 1;
  }
}

for (const rel of [
  "docs/assets/css/tokens.css",
  "docs/assets/css/chrome.css",
  "docs/assets/css/app.css",
  "docs/assets/css/seo.css",
  "docs/assets/css/stats.css",
  "docs/assets/css/mappa.css",
  "docs/assets/js/boot.js",
  "docs/assets/js/fonti.js",
  "docs/assets/js/stats.js",
  "docs/assets/js/mappa.js",
]) {
  try {
    await readFile(join(root, rel));
  } catch {
    console.error("missing", rel);
    failed += 1;
  }
}

const fontiHtml = await readFile(join(root, "docs/fonti.html"), "utf8");
for (const needle of [
  'src="assets/js/fonti.js',
  "assets/css/seo.css",
  'rel="canonical"',
  'href="privacy.html">Privacy</a>',
]) {
  if (!fontiHtml.includes(needle)) {
    console.error("fonti.html missing", needle);
    failed += 1;
  }
}
if (fontiHtml.includes("fonts.googleapis.com")) {
  console.error("fonti.html should not load Google Fonts");
  failed += 1;
}

const statsHtml = await readFile(join(root, "docs/stats.html"), "utf8");
for (const needle of [
  'src="assets/js/stats.js',
  "assets/css/stats.css",
  'rel="canonical"',
  'href="fonti.html">Fonti</a>',
  'href="comuni/">Comuni</a>',
  ">Segnala</a>",
  'href="privacy.html">Privacy</a>',
  "data-share>Condividi",
]) {
  if (!statsHtml.includes(needle)) {
    console.error("stats.html missing", needle);
    failed += 1;
  }
}
if (statsHtml.includes("fonts.googleapis.com")) {
  console.error("stats.html should not load Google Fonts");
  failed += 1;
}
if (statsHtml.includes('href="./">Home</a>')) {
  console.error("stats.html footer should match home/calendario (no Home link)");
  failed += 1;
}

const privacyHtml = await readFile(join(root, "docs/privacy.html"), "utf8");
for (const needle of [
  'rel="canonical"',
  "application/ld+json",
  "Notifiche",
  "localStorage",
  "Garante",
]) {
  if (!privacyHtml.includes(needle)) {
    console.error("privacy.html missing", needle);
    failed += 1;
  }
}

const mappaHtml = await readFile(join(root, "docs/mappa.html"), "utf8");
for (const needle of [
  "assets/vendor/leaflet/leaflet.css",
  "assets/vendor/leaflet/leaflet.js",
  'href="privacy.html">Privacy</a>',
]) {
  if (!mappaHtml.includes(needle)) {
    console.error("mappa.html missing", needle);
    failed += 1;
  }
}
if (mappaHtml.includes("unpkg.com/leaflet") || mappaHtml.includes("fonts.googleapis.com")) {
  console.error("mappa.html should self-host Leaflet and fonts");
  failed += 1;
}

const comuneSample = await readFile(join(root, "docs/comuni/rivoli.html"), "utf8");
for (const needle of [
  "../assets/css/tokens.css",
  "../assets/css/chrome.css",
  "../assets/css/seo.css",
  "Apri il calendario di Rivoli",
  "Raccolta differenziata",
  "../privacy.html",
]) {
  if (!comuneSample.includes(needle)) {
    console.error("comuni/rivoli.html missing", needle);
    failed += 1;
  }
}
if (comuneSample.includes("fonts.googleapis.com")) {
  console.error("comuni/rivoli.html should not load Google Fonts");
  failed += 1;
}
if (comuneSample.includes("<style>")) {
  console.error("comuni/rivoli.html should not inline <style>");
  failed += 1;
}
if (comuneSample.includes("Andamento:") || comuneSample.includes("Obiettivo 65%")) {
  console.error("comuni/rivoli.html should not include 65% target or trend copy");
  failed += 1;
}

const romaSample = await readFile(join(root, "docs/comuni/roma.html"), "utf8");
for (const needle of [
  "Raccolta differenziata a Roma",
  "stats.html?comune=roma",
  "ISPRA",
]) {
  if (!romaSample.includes(needle)) {
    console.error("comuni/roma.html missing", needle);
    failed += 1;
  }
}
if (romaSample.includes("Apri il calendario di Roma")) {
  console.error("comuni/roma.html should not offer a calendar CTA");
  failed += 1;
}
if (romaSample.includes("Andamento:") || romaSample.includes("obiettivo nazionale del 65%")) {
  console.error("comuni/roma.html should not include 65% target or trend copy");
  failed += 1;
}
if (!romaSample.includes("../stats.html?comune=roma")) {
  console.error("comuni/roma.html stats CTA must be relative to /stats.html");
  failed += 1;
}

const hub = await readFile(join(root, "docs/comuni/index.html"), "utf8");
for (const needle of [
  "regioni/piemonte.html",
  "regioni/lazio.html",
  "data-comuni-search",
  'type="module"',
  "comuni-nav.js",
]) {
  if (!hub.includes(needle)) {
    console.error("comuni/index.html missing", needle);
    failed += 1;
  }
}

{
  const hits = matchAndRankItems(
    [
      { name: "Airasca", provincia: "Torino" },
      { name: "Baldissero Torinese", provincia: "Torino" },
      { name: "Torino", provincia: "Torino" },
      { name: "Settimo Torinese", provincia: "Torino" },
      { name: "Roma", provincia: "Roma" },
    ],
    "torino"
  );
  if (!hits.length || hits[0].name !== "Torino") {
    console.error("search: Torino should rank first for query torino");
    failed += 1;
  }
  if (hits.some((h) => h.name === "Airasca" || h.name === "Roma")) {
    console.error("search: should not match provincia-only or unrelated names");
    failed += 1;
  }
}

const regionePiemonte = await readFile(join(root, "docs/comuni/regioni/piemonte.html"), "utf8");
for (const needle of [
  "../../assets/css/seo.css",
  "../province/torino.html",
  "Differenziata in Piemonte",
]) {
  if (!regionePiemonte.includes(needle)) {
    console.error("comuni/regioni/piemonte.html missing", needle);
    failed += 1;
  }
}

const provinciaTorino = await readFile(join(root, "docs/comuni/province/torino.html"), "utf8");
for (const needle of [
  "../rivoli.html",
  "Provincia di Torino",
  "data-comuni-search",
  "Calendario Escilo",
  "geo-group",
]) {
  if (!provinciaTorino.includes(needle)) {
    console.error("comuni/province/torino.html missing", needle);
    failed += 1;
  }
}
if (provinciaTorino.includes('class="badge">calendario<')) {
  console.error("comuni/province/torino.html should spell out Calendario Escilo");
  failed += 1;
}

{
  const iAbruzzo = hub.indexOf("regioni/abruzzo.html");
  const iPiemonte = hub.indexOf("regioni/piemonte.html");
  if (iAbruzzo < 0 || iPiemonte < 0 || iAbruzzo > iPiemonte) {
    console.error("comuni/index.html regions should be alphabetical (Abruzzo before Piemonte)");
    failed += 1;
  }
}

{
  const iAlessandria = regionePiemonte.indexOf("../province/alessandria.html");
  const iTorino = regionePiemonte.indexOf("../province/torino.html");
  if (iAlessandria < 0 || iTorino < 0 || iAlessandria > iTorino) {
    console.error("comuni/regioni/piemonte.html provinces should be alphabetical (Alessandria before Torino)");
    failed += 1;
  }
  if (!regionePiemonte.includes("data-comuni-search")) {
    console.error("comuni/regioni/piemonte.html missing data-comuni-search");
    failed += 1;
  }
}

const dispatch = await readFile(join(root, "netlify/functions/push-dispatch.mjs"), "utf8");
for (const needle of [
  "pickupDate",
  "bins",
  "Domani c’è un ritiro",
  'url: "./"',
  "now.hour < preferHour",
]) {
  if (!dispatch.includes(needle)) {
    console.error("push-dispatch.mjs missing", needle);
    failed += 1;
  }
}
if (dispatch.includes("Number(record.hour) !== now.hour")) {
  console.error("push-dispatch.mjs still requires exact hour match");
  failed += 1;
}
if (dispatch.includes("tab=cal&day=")) {
  console.error("push-dispatch.mjs should open home, not calendar, on notification");
  failed += 1;
}
if (dispatch.includes("Domani:")) {
  console.error("push-dispatch.mjs should not list bins in notification body");
  failed += 1;
}

const toml = await readFile(join(root, "netlify.toml"), "utf8");
if (!toml.includes("push-dispatch") || !toml.includes("included_files")) {
  console.error("netlify.toml missing push config");
  failed += 1;
}
if (!toml.includes("build_seo_pages.py")) {
  console.error("netlify.toml missing SEO build step");
  failed += 1;
}
if (!toml.includes("build_map_data.py")) {
  console.error("netlify.toml missing map build step");
  failed += 1;
}

const robots = await readFile(join(root, "docs/robots.txt"), "utf8");
if (!robots.includes("Sitemap: https://escilo.it/sitemap.xml")) {
  console.error("robots.txt missing sitemap URL");
  failed += 1;
}
if (!robots.includes("GPTBot") || !robots.includes("ClaudeBot")) {
  console.error("robots.txt missing AI bot Allow rules");
  failed += 1;
}

const sitemap = await readFile(join(root, "docs/sitemap.xml"), "utf8");
if (!sitemap.includes("https://escilo.it/comuni/rivoli.html")) {
  console.error("sitemap.xml missing rivoli landing");
  failed += 1;
}
if (!sitemap.includes("https://escilo.it/comuni/roma.html")) {
  console.error("sitemap.xml missing roma landing");
  failed += 1;
}
if (!sitemap.includes("https://escilo.it/comuni/regioni/piemonte.html")) {
  console.error("sitemap.xml missing piemonte region");
  failed += 1;
}
if (!sitemap.includes("https://escilo.it/comuni/province/torino.html")) {
  console.error("sitemap.xml missing torino province");
  failed += 1;
}
if (!sitemap.includes("https://escilo.it/stats.html")) {
  console.error("sitemap.xml missing stats.html");
  failed += 1;
}
if (!sitemap.includes("https://escilo.it/mappa.html")) {
  console.error("sitemap.xml missing mappa.html");
  failed += 1;
}
if (!sitemap.includes("https://escilo.it/privacy.html")) {
  console.error("sitemap.xml missing privacy.html");
  failed += 1;
}

const llms = await readFile(join(root, "docs/llms.txt"), "utf8");
if (!llms.includes("llms-full.txt") || !llms.includes("calendars/index.json")) {
  console.error("llms.txt missing expected links");
  failed += 1;
}
if (!llms.includes("/comuni/")) {
  console.error("llms.txt missing comuni hub");
  failed += 1;
}
if (!llms.includes("stats.html") || !llms.includes("data/ispr/comuni-by-id.json")) {
  console.error("llms.txt missing ISPRA stats links");
  failed += 1;
}
if (!llms.includes("privacy.html")) {
  console.error("llms.txt missing privacy.html");
  failed += 1;
}
if (!llms.includes("mappa.html")) {
  console.error("llms.txt missing mappa.html");
  failed += 1;
}
if (!llms.includes("data/map/province.geojson")) {
  console.error("llms.txt missing province.geojson");
  failed += 1;
}
if (!llms.includes("data/ispr/directory.json") || !llms.includes("data/ispr/c/")) {
  console.error("llms.txt missing national ISPRA directory links");
  failed += 1;
}

const ispr = JSON.parse(
  await readFile(join(root, "docs/data/ispr/comuni-by-id.json"), "utf8")
);
if (!ispr.comuni || !ispr.comuni.chieri || ispr.comuni.chieri.rd_pct == null) {
  console.error("comuni-by-id.json missing chieri KPIs");
  failed += 1;
}
if (ispr.comuni.chieri.rd_pctile_it == null || ispr.comuni.chieri.kg_ind_vs_median_it == null) {
  console.error("comuni-by-id.json missing national comparison fields");
  failed += 1;
}

if (failed) {
  console.error("FAIL", failed);
  process.exit(1);
}
console.log("ok smoke push files");
