import { $ } from "./shared/dom.js";
import { state } from "./state.js";
import { ACCESS_CALENDAR, ACCESS_STATS } from "./shared/constants.js";
import { normalizeCalendarBase, loadCalendarEntries, precacheSelectedZone, ensureZonesIndex } from "./data/zones.js";
import { refreshStatsTeaser } from "./data/ispr.js";
import { ensureWeekMonthsCached } from "./data/calendar-model.js";
import { hideZoneGate, directoryEntry } from "./ui/zone-picker.js";
import { showHomeSkeleton, loadTomorrowHero } from "./ui/hero.js";
import { setMonthLoading, loadMonth } from "./ui/month-calendar.js";
import { updateZoneMeta } from "./ui/zone-meta.js";
import { syncPushOffer, refreshPushRegistration } from "./ui/push-notify.js";

/** Con index/directory caricati valida comune/via; altrimenti si fida di localStorage (boot veloce). */
export function resolveStoredChoice(stored) {
  if (!stored) return null;

  if (stored.mode === ACCESS_STATS) {
    if (state.isprDirectory) {
      const entry = directoryEntry(stored.comuneId);
      if (!entry || entry.hasCalendar) return null;
      return {
        mode: ACCESS_STATS,
        comuneId: entry.id,
        comuneName: entry.name,
        istat: entry.istat || stored.istat || "",
        via: "",
        calendar: "",
      };
    }
    return {
      mode: ACCESS_STATS,
      comuneId: stored.comuneId,
      comuneName: stored.comuneName || stored.comuneId,
      istat: stored.istat || "",
      via: "",
      calendar: "",
    };
  }

  if (state.zonesIndex) {
    const comune = state.zonesIndex.comuni.find((c) => c.id === stored.comuneId);
    if (!comune) return null;
    const base = normalizeCalendarBase(stored.calendar);
    const viaEntry = comune.vie.find(
      (v) => v.name === stored.via && normalizeCalendarBase(v.calendar) === base
    );
    if (!viaEntry) return null;
    return {
      mode: ACCESS_CALENDAR,
      comuneId: comune.id,
      comuneName: comune.name,
      via: viaEntry.name,
      calendar: normalizeCalendarBase(viaEntry.calendar),
      istat: stored.istat || "",
    };
  }
  return {
    mode: ACCESS_CALENDAR,
    comuneId: stored.comuneId,
    comuneName: stored.comuneName || stored.comuneId,
    via: stored.via,
    calendar: normalizeCalendarBase(stored.calendar),
    istat: stored.istat || "",
  };
}

export function applyStatsOnly(choice) {
  state.zoneChoice = { ...choice, mode: ACCESS_STATS };
  hideZoneGate();
  const q = "stats.html?comune=" + encodeURIComponent(choice.comuneId);
  window.location.assign(q);
}

export async function applyZoneAndRender(choice) {
  if (choice.mode === ACCESS_STATS) {
    applyStatsOnly(choice);
    return;
  }
  if (!state.zonesIndex) {
    await ensureZonesIndex();
  }
  state.zoneChoice = { ...choice, mode: ACCESS_CALENDAR };
  updateZoneMeta();
  state.dayCache.clear();
  hideZoneGate();
  showHomeSkeleton();
  setMonthLoading(true);
  await loadCalendarEntries(choice.calendar);
  precacheSelectedZone(choice.calendar);
  loadTomorrowHero();
  ensureWeekMonthsCached();
  loadMonth();
  refreshStatsTeaser();
  $("liveLine").textContent =
    "Calendario ritiri — " + choice.comuneName + ", " + choice.via;
  syncPushOffer();
  refreshPushRegistration().catch((err) => console.error(err));
}
