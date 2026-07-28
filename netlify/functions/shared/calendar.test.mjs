import { readFile } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  binsForDate,
  formatBinsLabel,
  nextDay,
  parseCalendarEntries,
  romeParts,
} from "./calendar.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const sample = join(root, "docs", "calendars", "candiolo-z1-2027.h");

const text = await readFile(sample, "utf8");
const entries = parseCalendarEntries(text);
if (entries.length < 10) {
  console.error("FAIL: too few entries", entries.length);
  process.exit(1);
}

const bins = binsForDate(entries, 2027, 1, 4);
const label = formatBinsLabel(bins);
if (label !== "Organico, Indifferenziata, Plastica") {
  console.error("FAIL: unexpected bins for 2027-01-04:", label);
  process.exit(1);
}

const n = nextDay(2027, 1, 31);
if (n.year !== 2027 || n.month !== 2 || n.day !== 1) {
  console.error("FAIL: nextDay month rollover", n);
  process.exit(1);
}

const rome = romeParts(new Date("2026-07-28T18:30:00Z"));
if (rome.hour !== 20 || rome.dateKey !== "2026-07-28") {
  console.error("FAIL: romeParts", rome);
  process.exit(1);
}

console.log("ok", { entries: entries.length, label, rome });
