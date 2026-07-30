/**
 * Smoke check locale: pezzi push presenti e coerenti.
 * Non sostituisce il test device (PWA killata su Android/iOS).
 */
import { readFile } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");

const mustExist = [
  "netlify/functions/push-subscribe.mjs",
  "netlify/functions/push-unsubscribe.mjs",
  "netlify/functions/push-dispatch.mjs",
  "netlify/functions/push-vapid-public.mjs",
  "docs/sw.js",
  "docs/calendars/sources-lite.json",
  "docs/robots.txt",
  "docs/sitemap.xml",
  "docs/llms.txt",
  "docs/llms-full.txt",
  "docs/comuni/index.html",
  "docs/comuni/rivoli.html",
  "docs/googled19b3747a0a192a7.html",
  "tools/build_seo_pages.py",
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
  "/api/push/subscribe",
  "syncPushOffer",
  "requestNotificationPermission",
  "pushEnableWanted",
  "precacheSelectedZone",
  "cache-zone",
  "ensureZonesIndex",
  "ensureSourcesLite",
  "sources-lite.json",
  "initialComuneFromUrl",
  'rel="canonical"',
  "application/ld+json",
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

const dispatch = await readFile(join(root, "netlify/functions/push-dispatch.mjs"), "utf8");
for (const needle of ["pickupDate", "bins", "BIN_NAMES", "Domani:", "tab=cal&day="]) {
  if (!dispatch.includes(needle)) {
    console.error("push-dispatch.mjs missing", needle);
    failed += 1;
  }
}
if (dispatch.includes('url: `./?tab=home`')) {
  console.error("push-dispatch.mjs still opens home tab on notification");
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

const robots = await readFile(join(root, "docs/robots.txt"), "utf8");
if (!robots.includes("Sitemap: https://escilo.netlify.app/sitemap.xml")) {
  console.error("robots.txt missing sitemap URL");
  failed += 1;
}
if (!robots.includes("GPTBot") || !robots.includes("ClaudeBot")) {
  console.error("robots.txt missing AI bot Allow rules");
  failed += 1;
}

const sitemap = await readFile(join(root, "docs/sitemap.xml"), "utf8");
if (!sitemap.includes("https://escilo.netlify.app/comuni/rivoli.html")) {
  console.error("sitemap.xml missing rivoli landing");
  failed += 1;
}

const llms = await readFile(join(root, "docs/llms.txt"), "utf8");
if (!llms.includes("llms-full.txt") || !llms.includes("calendars/index.json")) {
  console.error("llms.txt missing expected links");
  failed += 1;
}

if (failed) {
  console.error("FAIL", failed);
  process.exit(1);
}
console.log("ok smoke push files");
