/** Mutable app state — import and mutate in place. */
export const state = {
  calendarEntries: [],
  /** @type {{ years?: number[], comuni: Array<{ id: string, name: string, vie: Array<{ name: string, calendar: string }> }> } | null} */
  zonesIndex: null,
  /** @type {Array<{ id: string, name: string, provincia: string, regione: string, istat: string, hasCalendar: boolean }> | null} */
  isprDirectory: null,
  /** @type {Promise<void> | null} */
  isprDirectoryPromise: null,
  /** @type {Record<string, object> | null} */
  isprComuneCache: null,
  /** @type {object | null} */
  isprBaselines: null,
  /** @type {Record<string, { id: string, provider: string, sourcePage: string }> | null} */
  sourcesLite: null,
  /** @type {{ mode?: string, comuneId: string, comuneName: string, via: string, calendar: string, istat?: string } | null} */
  zoneChoice: null,
  /** @type {Promise<void> | null} */
  zonesIndexPromise: null,
  /** @type {Promise<void> | null} */
  sourcesLitePromise: null,
  /** @type {Promise<void> | null} */
  isprStatsPromise: null,
  /** @type {{ latestYear?: number, comuni?: Record<string, object>, baselines?: object } | null} */
  isprStats: null,
  /** @type {boolean} */
  gateShowPicker: false,
  viewYear: new Date().getFullYear(),
  viewMonth: new Date().getMonth() + 1,
  /** @type {string | null} */
  selectedDayKey: null,
  activeTab: "home",
  /** @type {Map<string, { initials: string }>} */
  dayCache: new Map(),
  /** @type {import("./ui/zone-picker.js").ZonePickerApi | null} */
  comunePicker: null,
  /** @type {import("./ui/zone-picker.js").ZonePickerApi | null} */
  viaPicker: null,
  monthNavBusy: false,
  /** @type {BeforeInstallPromptEvent | null} */
  deferredInstallPrompt: null,
  pushEnableWanted: false,
  notifyToggleBusy: false,
  /** @type {PermissionStatus | null} */
  notifyPermissionWatch: null,
};
