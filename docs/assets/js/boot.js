import { initIosBar } from "./shared/ios-bar.js";
import { $ } from "./shared/dom.js";
import { shareAppLink } from "./shared/share.js";
import { readStoredChoice, saveChoice, clearChoice } from "./shared/storage.js";
import { ACCESS_STATS } from "./shared/constants.js";
import { state } from "./state.js";
import { parseYmd, buildDowHeader, syncCalLegend } from "./data/calendar-model.js";
import { applyZoneAndRender, applyStatsOnly, resolveStoredChoice } from "./app-core.js";
import {
  createZonePicker,
  updateGateSubmitState,
  populateViaSelect,
  choiceFromGateForm,
  setZoneGateBusy,
  openZoneGate,
  showZoneGate,
  goToGatePicker,
  goToGateMarketing,
  directoryEntry,
} from "./ui/zone-picker.js";
import { ensureIsprDirectory } from "./data/ispr.js";
import { renderHero, showHomeSkeleton } from "./ui/hero.js";
import { setTab } from "./ui/tabs.js";
import {
  navigateMonth,
  bindCalSwipe,
  setMonthLoading,
  jumpToTodayMonth,
  openCalendarDay,
} from "./ui/month-calendar.js";
import { updateZoneMeta } from "./ui/zone-meta.js";
import {
  syncInstallButton,
  onBeforeInstallPrompt,
  onAppInstalled,
  handleInstallAppClick,
  closeIosInstallSheet,
} from "./ui/install-pwa.js";
import {
  migratePushHourDefault,
  fillNotifyHourSelect,
  watchNotificationPermission,
  syncPushOffer,
  openNotifySheet,
  closeNotifySheet,
  handleNotifyToggleChange,
  handleNotifyHourChange,
  resumePushIfPermitted,
} from "./ui/push-notify.js";

export async function registerServiceWorker() {
  if (!("serviceWorker" in navigator) || !window.isSecureContext) return;
  try {
    await navigator.serviceWorker.register("sw.js");
  } catch (err) {
    console.error(err);
  }
}

export function initialTabFromUrl() {
  const tab = new URLSearchParams(window.location.search).get("tab");
  if (tab === "cal" || tab === "home") return tab;
  return null;
}

export function initialDayFromUrl() {
  const raw = new URLSearchParams(window.location.search).get("day");
  return parseYmd(raw);
}

export function initialComuneFromUrl() {
  const raw = new URLSearchParams(window.location.search).get("comune");
  if (!raw) return null;
  const id = String(raw).trim().toLowerCase();
  return id || null;
}

export async function boot() {
  buildDowHeader();
  migratePushHourDefault();
  fillNotifyHourSelect();
  await registerServiceWorker();
  watchNotificationPermission();
  syncInstallButton();

  const comuneParam = initialComuneFromUrl();
  if (new URLSearchParams(window.location.search).get("reset") === "1") {
    clearChoice();
    const url = new URL(window.location.href);
    url.searchParams.delete("reset");
    url.searchParams.delete("comune");
    window.history.replaceState({}, "", url.pathname + url.search);
  }
  const stored = readStoredChoice();

  // Deep-link to a stats-only comune → stats page.
  if (comuneParam) {
    try {
      await ensureIsprDirectory();
      const entry = directoryEntry(comuneParam);
      if (entry && !entry.hasCalendar) {
        saveChoice({
          mode: ACCESS_STATS,
          comuneId: entry.id,
          comuneName: entry.name,
          istat: entry.istat || "",
        });
        applyStatsOnly({
          mode: ACCESS_STATS,
          comuneId: entry.id,
          comuneName: entry.name,
          istat: entry.istat || "",
        });
        return;
      }
    } catch (err) {
      console.error(err);
    }
  }

  const resolved = resolveStoredChoice(stored);
  if (resolved && (!comuneParam || comuneParam === resolved.comuneId)) {
    if (resolved.mode === ACCESS_STATS) {
      applyStatsOnly(resolved);
      return;
    }
    showHomeSkeleton();
    setMonthLoading(true);
    try {
      await applyZoneAndRender(resolved);
      const day = initialDayFromUrl();
      if (day) {
        openCalendarDay(day.year, day.month, day.day);
        return;
      }
      const tab = initialTabFromUrl();
      if (tab && tab !== "home") setTab(tab);
      return;
    } catch (err) {
      console.error(err);
      clearChoice();
      setMonthLoading(false);
      $("weekStrip").innerHTML = "";
      $("dayDetail").classList.remove("is-loading");
      $("dayDetailLabel").textContent = "—";
      $("dayDetailChips").innerHTML = "";
    }
  }

  renderHero(null);
  await openZoneGate(comuneParam);
  syncPushOffer();
}

function wireDom() {
  $("btnCalPrev").addEventListener("click", () => {
    navigateMonth(-1);
  });
  $("btnCalNext").addEventListener("click", () => {
    navigateMonth(1);
  });
  $("btnCalToday").addEventListener("click", () => {
    void jumpToTodayMonth();
  });

  bindCalSwipe();

  $("btnWeekGotoCal").addEventListener("click", () => setTab("cal"));

  document.querySelectorAll("[data-share]").forEach((btn) => {
    btn.addEventListener("click", () => {
      void shareAppLink();
    });
  });

  document.querySelectorAll("#bottomNav [data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => setTab(btn.dataset.tab));
  });

  state.comunePicker = createZonePicker({
    inputId: "inpComune",
    listId: "listComune",
    hiddenId: "valComune",
    placeholder: "Cerca comune…",
    emptyLabel: "Digita per filtrare",
    onSelect: async () => {
      $("zoneGateError").textContent = "";
      const comuneId = state.comunePicker.getValue();
      await populateViaSelect(comuneId);
      const entry = directoryEntry(comuneId);
      if (entry && entry.hasCalendar && state.viaPicker) {
        state.viaPicker.focus();
      }
    },
    onChange: () => {
      $("zoneGateError").textContent = "";
      void populateViaSelect("");
      updateGateSubmitState();
    },
  });

  state.viaPicker = createZonePicker({
    inputId: "inpVia",
    listId: "listVia",
    hiddenId: "valVia",
    extraId: "valViaCalendar",
    placeholder: "Cerca via…",
    disabledPlaceholder: "Prima il comune…",
    emptyLabel: "Digita per filtrare",
    onSelect: () => {
      $("zoneGateError").textContent = "";
      updateGateSubmitState();
    },
    onChange: updateGateSubmitState,
  });

  state.viaPicker.setDisabled(true);

  const startButtons = [$("btnGateStart"), $("btnGateStartCal")].filter(Boolean);
  startButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      goToGatePicker();
    });
  });

  const btnClose = $("btnGateClose");
  if (btnClose) {
    btnClose.addEventListener("click", () => {
      goToGateMarketing();
    });
  }

  $("zoneGateForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const choice = choiceFromGateForm();
    if (!choice) {
      $("zoneGateError").textContent = "Seleziona il comune" +
        (directoryEntry($("valComune").value)?.hasCalendar ? " e la via." : ".");
      return;
    }
    setZoneGateBusy(true);
    $("zoneGateError").textContent = "";
    try {
      saveChoice(choice);
      await applyZoneAndRender(choice);
    } catch (err) {
      console.error(err);
      $("zoneGateError").textContent =
        choice.mode === ACCESS_STATS
          ? "Impossibile aprire le statistiche."
          : "Impossibile caricare il calendario.";
      setMonthLoading(false);
      renderHero(null);
      $("weekStrip").innerHTML = "";
      $("dayDetail").classList.remove("is-loading");
      $("dayDetailLabel").textContent = "—";
      $("dayDetailChips").innerHTML = "";
      showZoneGate();
      setZoneGateBusy(false);
    }
  });

  $("btnChangeZone").addEventListener("click", () => {
    clearChoice();
    updateZoneMeta();
    state.calendarEntries = [];
    syncCalLegend();
    state.dayCache.clear();
    renderHero(null);
    openZoneGate();
    syncPushOffer();
  });

  window.addEventListener("beforeinstallprompt", onBeforeInstallPrompt);
  window.addEventListener("appinstalled", onAppInstalled);

  $("btnInstallApp").addEventListener("click", () => {
    void handleInstallAppClick();
  });

  $("btnInstallSheetClose").addEventListener("click", () => {
    closeIosInstallSheet();
  });

  $("installSheet").addEventListener("click", (ev) => {
    if (ev.target === $("installSheet")) closeIosInstallSheet();
  });

  $("btnPushOffer").addEventListener("click", async () => {
    await syncPushOffer();
    openNotifySheet();
  });

  $("btnNotifySheetClose").addEventListener("click", () => {
    closeNotifySheet();
  });

  $("notifySheet").addEventListener("click", (ev) => {
    if (ev.target === $("notifySheet")) closeNotifySheet();
  });

  $("notifyToggle").addEventListener("change", () => {
    void handleNotifyToggleChange();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") resumePushIfPermitted();
  });
  window.addEventListener("focus", () => {
    resumePushIfPermitted();
  });

  $("notifyHour").addEventListener("change", () => {
    void handleNotifyHourChange();
  });
}

initIosBar();
wireDom();
boot();
