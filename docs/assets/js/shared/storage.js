import {
  LS_COMUNE,
  LS_COMUNE_NAME,
  LS_VIA,
  LS_CALENDAR,
  LS_ACCESS_MODE,
  LS_ISTAT,
  ACCESS_CALENDAR,
  ACCESS_STATS,
} from "./constants.js";
import { normalizeCalendarBase } from "../data/zones.js";
import { hideStatsTeaser } from "../data/ispr.js";
import { state } from "../state.js";

export function readStoredChoice() {
  const comuneId = localStorage.getItem(LS_COMUNE);
  if (!comuneId) return null;
  const comuneName = localStorage.getItem(LS_COMUNE_NAME) || "";
  const mode = localStorage.getItem(LS_ACCESS_MODE) || "";
  const istat = localStorage.getItem(LS_ISTAT) || "";

  if (mode === ACCESS_STATS) {
    return {
      mode: ACCESS_STATS,
      comuneId,
      comuneName,
      istat,
      via: "",
      calendar: "",
    };
  }

  const via = localStorage.getItem(LS_VIA);
  const calendar = normalizeCalendarBase(localStorage.getItem(LS_CALENDAR));
  if (!via || !calendar) return null;

  return {
    mode: ACCESS_CALENDAR,
    comuneId,
    comuneName,
    via,
    calendar,
    istat,
  };
}

export function saveChoice(choice) {
  const mode = choice.mode === ACCESS_STATS ? ACCESS_STATS : ACCESS_CALENDAR;
  localStorage.setItem(LS_ACCESS_MODE, mode);
  localStorage.setItem(LS_COMUNE, choice.comuneId);
  localStorage.setItem(LS_COMUNE_NAME, choice.comuneName || "");
  if (choice.istat) localStorage.setItem(LS_ISTAT, choice.istat);
  else localStorage.removeItem(LS_ISTAT);

  if (mode === ACCESS_STATS) {
    localStorage.removeItem(LS_VIA);
    localStorage.removeItem(LS_CALENDAR);
    state.zoneChoice = {
      mode: ACCESS_STATS,
      comuneId: choice.comuneId,
      comuneName: choice.comuneName || "",
      istat: choice.istat || "",
      via: "",
      calendar: "",
    };
    return;
  }

  const calendar = normalizeCalendarBase(choice.calendar);
  localStorage.setItem(LS_VIA, choice.via);
  localStorage.setItem(LS_CALENDAR, calendar);
  state.zoneChoice = { ...choice, mode: ACCESS_CALENDAR, calendar };
}

export function clearChoice() {
  localStorage.removeItem(LS_COMUNE);
  localStorage.removeItem(LS_COMUNE_NAME);
  localStorage.removeItem(LS_VIA);
  localStorage.removeItem(LS_CALENDAR);
  localStorage.removeItem(LS_ACCESS_MODE);
  localStorage.removeItem(LS_ISTAT);
  state.zoneChoice = null;
  hideStatsTeaser();
}
