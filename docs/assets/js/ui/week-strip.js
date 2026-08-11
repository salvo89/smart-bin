import { $ } from "../shared/dom.js";
import { state } from "../state.js";
import {
  ymdKey,
  formatDateIt,
  initialsToItems,
  dayInfo,
  rollingWeekStart,
  dowShort,
  ymdKeyFromDate,
  isKeyInRollingWeek,
  monthAbbrev,
} from "../data/calendar-model.js";

export function renderWeekStrip() {
  const strip = $("weekStrip");
  strip.removeAttribute("aria-busy");
  const detail = $("dayDetail");
  detail.classList.remove("is-loading");
  detail.removeAttribute("aria-busy");
  strip.innerHTML = "";
  const today = new Date();
  const start = rollingWeekStart(today);
  const todayKey = ymdKeyFromDate(today);
  if (!state.selectedDayKey || !isKeyInRollingWeek(state.selectedDayKey, start)) {
    state.selectedDayKey = todayKey;
  }

  for (let i = 0; i < 7; i++) {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
    const y = d.getFullYear();
    const m = d.getMonth() + 1;
    const day = d.getDate();
    const key = ymdKey(y, m, day);
    const cached = state.dayCache.get(key) || dayInfo(y, m, day);
    state.dayCache.set(key, { initials: cached.initials });
    const isToday = key === todayKey;
    const isOtherMonth =
      d.getMonth() !== today.getMonth() || d.getFullYear() !== today.getFullYear();
    const prev =
      i > 0
        ? new Date(start.getFullYear(), start.getMonth(), start.getDate() + i - 1)
        : null;
    const isMonthStart =
      !!prev &&
      (d.getMonth() !== prev.getMonth() || d.getFullYear() !== prev.getFullYear());
    const topLabel = isMonthStart ? monthAbbrev(d) : dowShort(d);

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "day-chip";
    btn.setAttribute("role", "option");
    btn.setAttribute("aria-selected", key === state.selectedDayKey ? "true" : "false");
    btn.setAttribute("aria-label", formatDateIt(y, m, day));
    if (isToday) btn.classList.add("today");
    if (isOtherMonth) btn.classList.add("other-month");
    if (isMonthStart) btn.classList.add("month-start");
    if (key === state.selectedDayKey) btn.classList.add("selected");

    const items = initialsToItems(cached.initials);
    const dots = items
      .map((it) => '<span class="dot-bin ' + it.sw + '"></span>')
      .join("");

    btn.innerHTML =
      '<span class="dow">' +
      topLabel +
      "</span>" +
      '<span class="num">' +
      day +
      "</span>" +
      '<span class="dots">' +
      dots +
      "</span>";
    btn.addEventListener("click", () => {
      state.selectedDayKey = key;
      renderWeekStrip();
      renderDayDetail(y, m, day);
    });
    strip.appendChild(btn);
  }

  const parts = state.selectedDayKey.split("-").map(Number);
  renderDayDetail(parts[0], parts[1], parts[2]);

  const selectedEl = strip.querySelector(".day-chip.selected");
  if (selectedEl) {
    selectedEl.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
  }
}

export function renderDayDetail(y, m, d) {
  const cached = state.dayCache.get(ymdKey(y, m, d)) || dayInfo(y, m, d);
  const today = new Date();
  const isToday =
    y === today.getFullYear() && m === today.getMonth() + 1 && d === today.getDate();
  const tom = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
  const isTom =
    y === tom.getFullYear() && m === tom.getMonth() + 1 && d === tom.getDate();

  let prefix = formatDateIt(y, m, d);
  if (isToday) prefix = "Oggi · " + prefix;
  else if (isTom) prefix = "Domani · " + prefix;
  $("dayDetailLabel").textContent = prefix;

  const chips = $("dayDetailChips");
  chips.innerHTML = "";

  const items = initialsToItems(cached.initials);
  items.forEach((it) => {
    const c = document.createElement("span");
    c.className = "chip " + (it.sw || "sw-x");
    c.textContent = it.icon + " " + it.name;
    chips.appendChild(c);
  });

  if (items.length === 0) {
    const p = document.createElement("p");
    p.className = "empty-day";
    p.textContent = "Nessun ritiro in questo giorno.";
    chips.appendChild(p);
  }
}
