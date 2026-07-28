import webpush from "web-push";
import { readFile } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { json, methodNotAllowed } from "./shared/http.mjs";
import {
  activeYears,
  binsForDate,
  formatBinsLabel,
  loadCalendarEntries,
  nextDay,
  romeParts,
} from "./shared/calendar.mjs";
import { getPushStore, listAllSubscriptions } from "./shared/store.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DOCS_CANDIDATES = [
  join(process.cwd(), "docs"),
  join(__dirname, "..", "..", "docs"),
];

function siteBaseUrl() {
  return (
    process.env.URL ||
    process.env.DEPLOY_PRIME_URL ||
    process.env.SITE_URL ||
    ""
  ).replace(/\/$/, "");
}

function authorize(event) {
  const secret = process.env.DISPATCH_SECRET;
  if (!secret) return false;
  const header =
    event.headers["x-dispatch-secret"] ||
    event.headers["X-Dispatch-Secret"] ||
    "";
  if (header && header === secret) return true;
  const auth = event.headers.authorization || event.headers.Authorization || "";
  if (auth === `Bearer ${secret}`) return true;
  return false;
}

async function fetchCalendarText(relPath) {
  const rel = relPath.replace(/^\//, "");
  for (const root of DOCS_CANDIDATES) {
    try {
      return await readFile(join(root, rel), "utf8");
    } catch {
      /* try next */
    }
  }

  const base = siteBaseUrl();
  if (!base) return null;
  try {
    const res = await fetch(`${base}/${rel}`);
    if (!res.ok) return null;
    return await res.text();
  } catch {
    return null;
  }
}

async function loadIndexYears(romeYear) {
  const text = await fetchCalendarText("calendars/index.json");
  if (!text) return activeYears(null, romeYear);
  try {
    return activeYears(JSON.parse(text), romeYear);
  } catch {
    return activeYears(null, romeYear);
  }
}

const entryCache = new Map();

async function entriesForCalendar(calendarId, years) {
  const cacheKey = `${calendarId}|${years.join(",")}`;
  if (entryCache.has(cacheKey)) return entryCache.get(cacheKey);
  const entries = await loadCalendarEntries(fetchCalendarText, calendarId, years);
  entryCache.set(cacheKey, entries);
  return entries;
}

export async function handler(event) {
  if (event.httpMethod === "OPTIONS") {
    return json(204, {});
  }
  if (event.httpMethod !== "POST" && event.httpMethod !== "GET") {
    return methodNotAllowed("POST, GET");
  }
  if (!authorize(event)) {
    return json(401, { error: "unauthorized" });
  }

  const publicKey = process.env.VAPID_PUBLIC_KEY;
  const privateKey = process.env.VAPID_PRIVATE_KEY;
  const subject = process.env.VAPID_SUBJECT || "mailto:salvatore.bonventre.ai@gmail.com";
  if (!publicKey || !privateKey) {
    return json(503, { error: "vapid_not_configured" });
  }

  webpush.setVapidDetails(subject, publicKey, privateKey);

  // TEST: PUSH_TEST_MODE=1 → ignora ora utente e lastSentDate (push a ogni dispatch se c’è ritiro).
  // Prod: togliere/false + cron orario nel workflow.
  const testMode =
    process.env.PUSH_TEST_MODE === "1" ||
    process.env.PUSH_TEST_MODE === "true";

  const now = romeParts();
  const tomorrow = nextDay(now.year, now.month, now.day);
  const years = await loadIndexYears(now.year);
  const store = getPushStore();
  const all = await listAllSubscriptions(store);

  let sent = 0;
  let skipped = 0;
  let removed = 0;
  let errors = 0;

  for (const { key, record } of all) {
    if (!testMode && Number(record.hour) !== now.hour) {
      skipped += 1;
      continue;
    }
    if (!testMode && record.lastSentDate === now.dateKey) {
      skipped += 1;
      continue;
    }

    const entries = await entriesForCalendar(record.calendarId, years);
    if (!entries) {
      skipped += 1;
      continue;
    }

    const bins = binsForDate(entries, tomorrow.year, tomorrow.month, tomorrow.day);
    if (!bins.length) {
      if (!testMode) {
        await store.setJSON(key, {
          ...record,
          lastSentDate: now.dateKey,
          updatedAt: new Date().toISOString(),
        });
      }
      skipped += 1;
      continue;
    }

    const label = formatBinsLabel(bins);
    const payload = JSON.stringify({
      title: testMode ? "Escilo (test)" : "Escilo",
      body: `Domani: ${label}`,
      url: "./",
    });

    try {
      await webpush.sendNotification(record.subscription, payload, {
        TTL: testMode ? 60 * 5 : 60 * 60 * 12,
        urgency: "normal",
      });
      if (!testMode) {
        await store.setJSON(key, {
          ...record,
          lastSentDate: now.dateKey,
          updatedAt: new Date().toISOString(),
        });
      }
      sent += 1;
    } catch (err) {
      const status = err && (err.statusCode || err.status);
      if (status === 404 || status === 410) {
        await store.delete(key);
        removed += 1;
      } else {
        console.error("push_send_failed", key, err && err.message);
        errors += 1;
      }
    }
  }

  return json(200, {
    ok: true,
    testMode,
    rome: now,
    tomorrow,
    sent,
    skipped,
    removed,
    errors,
    total: all.length,
  });
}
