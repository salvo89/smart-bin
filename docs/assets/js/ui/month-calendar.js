import { contactMailto } from "../shared/constants.js";
import { $ } from "../shared/dom.js";
import { state } from "../state.js";
import {
  ymdKey,
  daysInMonth,
  weekdayMondayFirst,
  badgesFromInitialsString,
  cacheMonth,
  monthHasData,
  MONTH_IT,
} from "../data/calendar-model.js";
import { renderWeekStrip } from "./week-strip.js";
import { setTab } from "./tabs.js";

export function renderMonthGrid(y, m, dayDataArray) {
  const grid = $("calGrid");
  grid.innerHTML = "";
  const D = daysInMonth(y, m);
  const lead = weekdayMondayFirst(y, m, 1);
  const today = new Date();
  const isThisMonth = today.getFullYear() === y && today.getMonth() + 1 === m;
  const todayD = isThisMonth ? today.getDate() : -1;

  for (let i = 0; i < lead; i++) {
    const pad = document.createElement("div");
    pad.className = "cal-cell pad";
    pad.setAttribute("aria-hidden", "true");
    grid.appendChild(pad);
  }

  for (let d = 1; d <= D; d++) {
    const cell = document.createElement("div");
    cell.className = "cal-cell";
    cell.setAttribute("role", "gridcell");
    if (d === todayD) cell.classList.add("today");

    const data = dayDataArray[d];

    const num = document.createElement("div");
    num.className = "num";
    num.textContent = String(d);
    cell.appendChild(num);

    const tags = document.createElement("div");
    tags.className = "tags";

    let hasWasteBadge = false;
    if (data) {
      const fromIni = badgesFromInitialsString(data.initials || "");
      if (fromIni) {
        fromIni.forEach((n) => tags.appendChild(n));
        hasWasteBadge = true;
      }
    }

    if (!hasWasteBadge) {
      const none = document.createElement("span");
      none.className = "none";
      none.textContent = "—";
      tags.appendChild(none);
    }
    cell.appendChild(tags);
    grid.appendChild(cell);
  }
}

export function renderSkeletonMonth(y, m) {
  const grid = $("calGrid");
  grid.innerHTML = "";
  const D = daysInMonth(y, m);
  const lead = weekdayMondayFirst(y, m, 1);

  for (let i = 0; i < lead; i++) {
    const pad = document.createElement("div");
    pad.className = "cal-cell pad";
    pad.setAttribute("aria-hidden", "true");
    grid.appendChild(pad);
  }

  for (let d = 1; d <= D; d++) {
    const cell = document.createElement("div");
    cell.className = "cal-cell skeleton";
    cell.setAttribute("aria-hidden", "true");
    const num = document.createElement("div");
    num.className = "num";
    num.textContent = String(d);
    cell.appendChild(num);
    const tags = document.createElement("div");
    tags.className = "tags";
    const bar1 = document.createElement("span");
    bar1.className = "sk-bar short";
    const bar2 = document.createElement("span");
    bar2.className = "sk-bar mid";
    tags.appendChild(bar1);
    tags.appendChild(bar2);
    cell.appendChild(tags);
    grid.appendChild(cell);
  }
}

function setCalMonthTitle(y, m) {
  const title = $("calTitle");
  if (title) title.textContent = MONTH_IT[m - 1] + " " + y;
}

export function setMonthLoading(on) {
  const wrap = $("calWrap");
  const body = $("calBody");
  if (!wrap || !body) return;
  if (on) {
    wrap.classList.add("loading");
    wrap.classList.remove("is-empty-month");
    body.classList.remove("is-empty");
    body.setAttribute("aria-busy", "true");
    setCalMonthTitle(state.viewYear, state.viewMonth);
    renderSkeletonMonth(state.viewYear, state.viewMonth);
  } else {
    wrap.classList.remove("loading");
    body.removeAttribute("aria-busy");
  }
}

export function loadMonth() {
  setMonthLoading(false);
  const title = MONTH_IT[state.viewMonth - 1] + " " + state.viewYear;
  setCalMonthTitle(state.viewYear, state.viewMonth);
  const hasData = monthHasData(state.viewYear, state.viewMonth);
  const body = $("calBody");
  const wrap = $("calWrap");
  body.classList.toggle("is-empty", !hasData);
  wrap.classList.toggle("is-empty-month", !hasData);

  if (!hasData) {
    renderSkeletonMonth(state.viewYear, state.viewMonth);
    const now = new Date();
    const curY = now.getFullYear();
    const curM = now.getMonth() + 1;
    const isPast =
      state.viewYear < curY || (state.viewYear === curY && state.viewMonth < curM);
    const shareRow = $("calEmptyShare");
    const zoneBit = state.zoneChoice
      ? state.zoneChoice.comuneName + " · " + state.zoneChoice.via
      : null;

    if (isPast) {
      $("calEmptyTitle").textContent = "Storico non disponibile";
      $("calEmptyMsg").textContent =
        "Escilo non conserva lo storico completo dei calendari. Per " +
        title +
        " i dati di ritiro non sono più disponibili qui.";
      shareRow.hidden = true;
    } else {
      $("calEmptyTitle").textContent = "Dati non disponibili";
      $("calEmptyMsg").textContent = zoneBit
        ? "Per " + title + " non abbiamo ancora il calendario dei ritiri di " + zoneBit + "."
        : "Per " + title + " non abbiamo ancora il calendario dei ritiri.";
      shareRow.hidden = false;
      $("calEmptyMail").href = contactMailto(
        "Escilo — dati calendario " + title + (zoneBit ? " (" + zoneBit + ")" : "")
      );
    }
  } else {
    const dataByDay = cacheMonth(state.viewYear, state.viewMonth);
    renderMonthGrid(state.viewYear, state.viewMonth, dataByDay);
  }
  renderWeekStrip();
}

export function shiftMonth(delta) {
  state.viewMonth += delta;
  if (state.viewMonth > 12) {
    state.viewMonth = 1;
    state.viewYear++;
  } else if (state.viewMonth < 1) {
    state.viewMonth = 12;
    state.viewYear--;
  }
}

const prefersReducedMotion = () =>
  window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function resetCalSlide() {
  const slide = $("calSlide");
  slide.classList.remove("is-animating");
  slide.style.transition = "";
  slide.style.transform = "";
  slide.style.opacity = "";
}

export function waitCalTransition(slide, ms) {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      slide.removeEventListener("transitionend", onEnd);
      resolve();
    };
    const onEnd = (ev) => {
      if (ev.target !== slide) return;
      if (ev.propertyName !== "transform" && ev.propertyName !== "opacity") return;
      finish();
    };
    slide.addEventListener("transitionend", onEnd);
    setTimeout(finish, ms);
  });
}

export async function animateCalSlide(fromXpx, toXpx, fromOp, toOp, durationMs) {
  const slide = $("calSlide");
  slide.classList.add("is-animating");
  slide.style.transition = "none";
  slide.style.transform = "translate3d(" + fromXpx + "px,0,0)";
  slide.style.opacity = String(fromOp);
  void slide.offsetWidth;
  if (prefersReducedMotion()) {
    slide.style.transform = "translate3d(" + toXpx + "px,0,0)";
    slide.style.opacity = String(toOp);
    return;
  }
  slide.style.transition =
    "transform " +
    durationMs +
    "ms cubic-bezier(0.22, 0.82, 0.2, 1), opacity " +
    Math.round(durationMs * 0.85) +
    "ms ease";
  slide.style.transform = "translate3d(" + toXpx + "px,0,0)";
  slide.style.opacity = String(toOp);
  await waitCalTransition(slide, durationMs + 80);
}

export async function navigateMonth(delta, opts) {
  if (!delta || state.monthNavBusy) return;
  state.monthNavBusy = true;
  const slide = $("calSlide");
  const dir = delta > 0 ? 1 : -1;
  const width = ($("calViewport") && $("calViewport").offsetWidth) || 280;
  const outDist = Math.round(width * 0.42);
  const startX = opts && typeof opts.startX === "number" ? opts.startX : 0;
  const startOp =
    opts && typeof opts.startOp === "number"
      ? opts.startOp
      : Math.max(0.45, 1 - Math.abs(startX) / (width * 0.9));

  try {
    await animateCalSlide(startX, -dir * outDist, startOp, 0, 220);
    shiftMonth(delta);
    loadMonth();
    await animateCalSlide(dir * outDist, 0, 0, 1, 260);
  } finally {
    resetCalSlide();
    state.monthNavBusy = false;
  }
}

export function bindCalSwipe() {
  const viewport = $("calViewport");
  const slide = $("calSlide");
  if (!viewport || !slide) return;

  let touch = null;

  viewport.addEventListener(
    "touchstart",
    (e) => {
      if (state.monthNavBusy || !e.changedTouches || !e.changedTouches.length) return;
      const t = e.changedTouches[0];
      touch = {
        id: t.identifier,
        x: t.clientX,
        y: t.clientY,
        dx: 0,
        tracking: false,
      };
    },
    { passive: true }
  );

  viewport.addEventListener(
    "touchmove",
    (e) => {
      if (!touch || state.monthNavBusy || !e.changedTouches) return;
      let t = null;
      for (let i = 0; i < e.changedTouches.length; i++) {
        if (e.changedTouches[i].identifier === touch.id) {
          t = e.changedTouches[i];
          break;
        }
      }
      if (!t) return;
      const dx = t.clientX - touch.x;
      const dy = t.clientY - touch.y;
      if (!touch.tracking) {
        if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
        if (Math.abs(dy) >= Math.abs(dx)) {
          touch = null;
          return;
        }
        touch.tracking = true;
      }
      touch.dx = dx;
      const width = viewport.offsetWidth || 280;
      slide.style.transition = "none";
      slide.style.transform = "translate3d(" + dx + "px,0,0)";
      slide.style.opacity = String(Math.max(0.42, 1 - Math.abs(dx) / (width * 1.05)));
    },
    { passive: true }
  );

  const endTouch = async (e) => {
    if (!touch || !e.changedTouches) return;
    let ended = false;
    for (let i = 0; i < e.changedTouches.length; i++) {
      if (e.changedTouches[i].identifier === touch.id) {
        ended = true;
        break;
      }
    }
    if (!ended) return;
    const dx = touch.tracking ? touch.dx : 0;
    const wasTracking = touch.tracking;
    touch = null;
    if (!wasTracking) return;

    const width = viewport.offsetWidth || 280;
    const threshold = Math.min(72, width * 0.18);
    if (dx <= -threshold) {
      await navigateMonth(1, {
        startX: dx,
        startOp: Math.max(0.42, 1 - Math.abs(dx) / (width * 1.05)),
      });
    } else if (dx >= threshold) {
      await navigateMonth(-1, {
        startX: dx,
        startOp: Math.max(0.42, 1 - Math.abs(dx) / (width * 1.05)),
      });
    } else {
      state.monthNavBusy = true;
      try {
        await animateCalSlide(
          dx,
          0,
          Math.max(0.42, 1 - Math.abs(dx) / (width * 1.05)),
          1,
          200
        );
      } finally {
        resetCalSlide();
        state.monthNavBusy = false;
      }
    }
  };

  viewport.addEventListener("touchend", endTouch, { passive: true });
  viewport.addEventListener("touchcancel", endTouch, { passive: true });
}

export function openCalendarDay(y, m, d) {
  state.selectedDayKey = ymdKey(y, m, d);
  state.viewYear = y;
  state.viewMonth = m;
  loadMonth();
  setTab("cal");
}

export async function jumpToTodayMonth() {
  const t = new Date();
  const ty = t.getFullYear();
  const tm = t.getMonth() + 1;
  if (ty === state.viewYear && tm === state.viewMonth) {
    loadMonth();
    return;
  }
  const delta = ty * 12 + tm - (state.viewYear * 12 + state.viewMonth);
  const step = delta > 0 ? 1 : -1;
  state.viewYear = ty;
  state.viewMonth = tm;
  if (state.monthNavBusy) return;
  state.monthNavBusy = true;
  const width = ($("calViewport") && $("calViewport").offsetWidth) || 280;
  const outDist = Math.round(width * 0.42);
  try {
    await animateCalSlide(0, -step * outDist, 1, 0, 180);
    loadMonth();
    await animateCalSlide(step * outDist, 0, 0, 1, 220);
  } finally {
    resetCalSlide();
    state.monthNavBusy = false;
  }
}
