import {
  CONTACT_MAILTO,
  contactMailto,
  ACCESS_CALENDAR,
  ACCESS_STATS,
} from "../shared/constants.js";
import { $ } from "../shared/dom.js";
import { matchAndRankItems, normalizeSearch } from "../shared/search.js";
import { state } from "../state.js";
import { normalizeCalendarBase, ensureZonesIndex } from "../data/zones.js";
import { ensureIsprDirectory } from "../data/ispr.js";

/** @typedef {{ value: string, label: string, name?: string, calendar?: string, hasCalendar?: boolean, provincia?: string, istat?: string }} ZonePickerItem */

/**
 * @typedef {{
 *   setItems: Function,
 *   clearSelection: Function,
 *   setDisabled: Function,
 *   selectByValue: Function,
 *   focus: Function,
 *   getValue: Function,
 * }} ZonePickerApi
 */

export function syncGateSteps() {
  const gate = $("zoneGate");
  if (!gate) return;
  const showPicker = !!state.gateShowPicker;
  gate.classList.toggle("is-picker", showPicker);
  gate.classList.toggle("is-marketing", !showPicker);
  const form = $("zoneGateForm");
  if (form) form.hidden = !showPicker;
  if (!showPicker) {
    const scroll = $("gateStoryScroll");
    if (scroll) scroll.scrollTop = 0;
  }
}

export function setGateCover(on) {
  document.documentElement.classList.toggle("is-gated", !!on);
}

export function goToGatePicker() {
  state.gateShowPicker = true;
  syncGateSteps();
  if (state.comunePicker) state.comunePicker.focus();
}

export function goToGateMarketing() {
  state.gateShowPicker = false;
  $("zoneGateError").textContent = "";
  syncGateSteps();
}

export function bindGateStoryScroll() {
  const scroll = $("gateStoryScroll");
  if (!scroll || scroll.dataset.bound) return;
  scroll.dataset.bound = "1";
  const btnTop = $("btnGateScrollTop");
  if (btnTop && !btnTop.dataset.bound) {
    btnTop.dataset.bound = "1";
    btnTop.addEventListener("click", () => {
      scroll.scrollTo({ top: 0, behavior: "smooth" });
    });
  }
}

export function createZonePicker(config) {
  const input = $(config.inputId);
  const list = $(config.listId);
  const hidden = $(config.hiddenId);
  const picker = input.closest(".zone-picker");
  /** @type {ZonePickerItem[]} */
  let items = [];
  let activeIdx = -1;

  function matchingItems(filter) {
    return matchAndRankItems(items, filter);
  }

  function visibleOptions() {
    return list.querySelectorAll(".zone-picker-item");
  }

  function setActive(idx) {
    const opts = visibleOptions();
    activeIdx = idx;
    opts.forEach((el, i) => el.classList.toggle("active", i === idx));
    if (idx >= 0 && opts[idx]) {
      opts[idx].scrollIntoView({ block: "nearest" });
    }
  }

  function setOpen(on) {
    list.hidden = !on;
    input.setAttribute("aria-expanded", on ? "true" : "false");
    picker.classList.toggle("open", on);
    if (!on) setActive(-1);
  }

  function selectItem(it) {
    hidden.value = it.value;
    input.value = it.label;
    if (config.extraId && it.calendar) {
      $(config.extraId).value = it.calendar;
    } else if (config.extraId) {
      $(config.extraId).value = "";
    }
    setOpen(false);
    if (config.onSelect) config.onSelect(it);
  }

  function renderList(filter) {
    const filtered = matchingItems(filter);
    list.innerHTML = "";
    if (filtered.length === 0) {
      const li = document.createElement("li");
      li.className = "zone-picker-empty";
      if (normalizeSearch(filter)) {
        li.append("Nessun risultato. ");
        const a = document.createElement("a");
        a.href = CONTACT_MAILTO;
        a.textContent = "Segnala la zona";
        li.appendChild(a);
      } else {
        li.textContent = config.emptyLabel || "Nessuna voce";
      }
      list.appendChild(li);
    } else {
      filtered.forEach((it) => {
        const li = document.createElement("li");
        li.className = "zone-picker-item";
        li.setAttribute("role", "option");
        li.textContent = it.label;
        li.addEventListener("mousedown", (ev) => {
          ev.preventDefault();
          selectItem(it);
        });
        list.appendChild(li);
      });
    }
    setOpen(true);
    setActive(filtered.length === 1 ? 0 : -1);
  }

  function clearSelection() {
    hidden.value = "";
    input.value = "";
    if (config.extraId) $(config.extraId).value = "";
    list.innerHTML = "";
    setOpen(false);
  }

  function setItems(newItems, opts = {}) {
    items = newItems;
    if (opts.reset !== false) clearSelection();
    else setOpen(false);
  }

  function setDisabled(dis) {
    input.disabled = dis;
    if (dis) {
      clearSelection();
      input.placeholder = config.disabledPlaceholder || config.placeholder || "";
    } else {
      input.placeholder = config.placeholder || "";
    }
  }

  input.addEventListener("focus", () => {
    if (!input.disabled) renderList(input.value);
  });

  input.addEventListener("input", () => {
    hidden.value = "";
    if (config.extraId) $(config.extraId).value = "";
    renderList(input.value);
    if (config.onChange) config.onChange();
  });

  input.addEventListener("blur", () => {
    window.setTimeout(() => setOpen(false), 120);
  });

  input.addEventListener("keydown", (ev) => {
    const opts = visibleOptions();
    if (ev.key === "ArrowDown") {
      ev.preventDefault();
      if (list.hidden) renderList(input.value);
      else if (opts.length) setActive(Math.min(activeIdx + 1, opts.length - 1));
    } else if (ev.key === "ArrowUp") {
      ev.preventDefault();
      if (opts.length) setActive(Math.max(activeIdx - 1, 0));
    } else if (ev.key === "Enter") {
      if (!list.hidden && activeIdx >= 0 && opts[activeIdx]) {
        ev.preventDefault();
        const label = opts[activeIdx].textContent;
        const it = matchingItems(input.value).find((x) => x.label === label);
        if (it) selectItem(it);
      }
    } else if (ev.key === "Escape") {
      setOpen(false);
    }
  });

  return {
    setItems,
    clearSelection,
    setDisabled,
    selectByValue: (value) => {
      const it = items.find((x) => x.value === value);
      if (it) selectItem(it);
    },
    focus: () => input.focus(),
    getValue: () => hidden.value,
    getSelectedItem: () => items.find((x) => x.value === hidden.value) || null,
  };
}

export function directoryEntry(comuneId) {
  if (!state.isprDirectory || !comuneId) return null;
  return state.isprDirectory.find((c) => c.id === comuneId) || null;
}

/** Vie caricate per il comune corrente; 0 = nessuna / in caricamento. */
let loadedViaCount = 0;

export function updateGateSubmitState() {
  const btn = $("zoneGateSubmit");
  if (!btn) return;
  const comuneId = state.comunePicker && state.comunePicker.getValue();
  const entry = directoryEntry(comuneId);
  const hasCal = !!(entry && entry.hasCalendar);
  const viaField = $("zoneFieldVia");
  // Una sola via: niente step — il campo resta nascosto come per i comuni solo-stats.
  if (viaField) viaField.hidden = !hasCal || loadedViaCount <= 1;

  const viaOk = hasCal
    ? !!(state.viaPicker && state.viaPicker.getValue())
    : true;
  btn.disabled = !(comuneId && viaOk);

  const label = hasCal ? "Mostra calendario" : "Vedi le statistiche";
  if (!btn.classList.contains("is-busy")) {
    btn.textContent = label;
    btn.dataset.label = label;
  }

  const hint = $("gateStatsHint");
  if (hint) {
    hint.hidden = !comuneId || hasCal;
    if (comuneId && !hasCal && entry) {
      const a = hint.querySelector("a");
      if (a) {
        a.href = contactMailto("Escilo — proponi calendario " + entry.name);
      }
    }
  }
}

export function populateComuneSelect() {
  const comuni = [...(state.isprDirectory || [])]
    .sort((a, b) => a.name.localeCompare(b.name, "it"))
    .map((c) => ({
      value: c.id,
      name: c.name,
      label: c.provincia ? c.name + " (" + c.provincia + ")" : c.name,
      hasCalendar: !!c.hasCalendar,
      provincia: c.provincia,
      istat: c.istat,
    }));
  state.comunePicker.setItems(comuni);
}

export async function populateViaSelect(comuneId) {
  loadedViaCount = 0;
  const entry = directoryEntry(comuneId);
  if (state.viaPicker) state.viaPicker.setDisabled(true);
  if (!comuneId || !entry || !entry.hasCalendar) {
    updateGateSubmitState();
    return;
  }
  updateGateSubmitState();
  try {
    await ensureZonesIndex();
  } catch (err) {
    console.error(err);
    if (state.viaPicker) state.viaPicker.setDisabled(true);
    updateGateSubmitState();
    return;
  }
  const comune = state.zonesIndex.comuni.find((c) => c.id === comuneId);
  if (!comune) {
    state.viaPicker.setDisabled(true);
    updateGateSubmitState();
    return;
  }
  const vie = [...comune.vie]
    .sort((a, b) => a.name.localeCompare(b.name, "it"))
    .map((v) => ({
      value: v.name,
      label: v.name,
      calendar: normalizeCalendarBase(v.calendar),
    }));
  loadedViaCount = vie.length;
  state.viaPicker.setDisabled(false);
  state.viaPicker.setItems(vie);
  if (vie.length === 1) {
    state.viaPicker.selectByValue(vie[0].value);
  }
  updateGateSubmitState();
}

/** Se il comune ha calendario ed esattamente una via/zona, restituisce la choice pronta. */
export async function calendarChoiceIfSingleVia(comuneId) {
  if (!comuneId) return null;
  try {
    await ensureZonesIndex();
  } catch (err) {
    console.error(err);
    return null;
  }
  if (!state.zonesIndex || !Array.isArray(state.zonesIndex.comuni)) return null;
  const comune = state.zonesIndex.comuni.find((c) => c.id === comuneId);
  if (!comune || !Array.isArray(comune.vie) || comune.vie.length !== 1) {
    return null;
  }
  const v = comune.vie[0];
  const calendar = normalizeCalendarBase(v && v.calendar);
  if (!v || !v.name || !calendar) return null;
  const entry = directoryEntry(comuneId);
  return {
    mode: ACCESS_CALENDAR,
    comuneId: (entry && entry.id) || comune.id,
    comuneName: (entry && entry.name) || comune.name,
    via: v.name,
    calendar,
    istat: (entry && entry.istat) || "",
  };
}

export function showZoneGate(prefillComuneId) {
  $("zoneGateError").textContent = "";
  setZoneGateBusy(false);
  bindGateStoryScroll();
  state.gateShowPicker = !!prefillComuneId;
  setGateCover(true);
  syncGateSteps();
  populateComuneSelect();
  $("zoneGate").hidden = false;
  if (prefillComuneId && directoryEntry(prefillComuneId)) {
    state.gateShowPicker = true;
    syncGateSteps();
    state.comunePicker.selectByValue(prefillComuneId);
    return;
  }
  populateViaSelect("");
  if (state.gateShowPicker && state.comunePicker) state.comunePicker.focus();
}

/** Apre il gate caricando directory (+ index se serve). */
export async function openZoneGate(prefillComuneId) {
  try {
    setGateCover(true);
    if (!prefillComuneId) {
      // Story di marketing solo al primo ingresso, non dai deep-link /comuni.
      $("zoneGate").hidden = false;
      bindGateStoryScroll();
      state.gateShowPicker = false;
      syncGateSteps();
    }
    await ensureIsprDirectory();
    showZoneGate(prefillComuneId || null);
  } catch (err) {
    console.error(err);
    $("liveLine").textContent = "Elenco comuni non disponibile";
    $("zoneGate").hidden = true;
    setGateCover(false);
  }
}

export function hideZoneGate() {
  $("zoneGate").hidden = true;
  setGateCover(false);
}

export function choiceFromGateForm() {
  const comuneId = $("valComune").value;
  const entry = directoryEntry(comuneId);
  if (!entry) return null;

  if (!entry.hasCalendar) {
    return {
      mode: ACCESS_STATS,
      comuneId: entry.id,
      comuneName: entry.name,
      istat: entry.istat || "",
      via: "",
      calendar: "",
    };
  }

  const via = $("valVia").value;
  const calendar = normalizeCalendarBase($("valViaCalendar").value);
  if (!via || !calendar) return null;
  return {
    mode: ACCESS_CALENDAR,
    comuneId: entry.id,
    comuneName: entry.name,
    via,
    calendar,
    istat: entry.istat || "",
  };
}

export function setZoneGateBusy(on) {
  const btn = $("zoneGateSubmit");
  if (!btn) return;
  if (on) {
    if (!btn.dataset.label) btn.dataset.label = btn.textContent.trim() || "Continua";
    btn.disabled = true;
    btn.classList.add("is-busy");
    btn.setAttribute("aria-busy", "true");
    btn.innerHTML =
      '<span class="btn-spinner" aria-hidden="true"></span> Caricamento…';
    $("inpComune").disabled = true;
    if ($("inpVia")) $("inpVia").disabled = true;
  } else {
    btn.classList.remove("is-busy");
    btn.removeAttribute("aria-busy");
    btn.textContent = btn.dataset.label || "Continua";
    $("inpComune").disabled = false;
    populateViaSelect($("valComune").value);
    updateGateSubmitState();
  }
}
