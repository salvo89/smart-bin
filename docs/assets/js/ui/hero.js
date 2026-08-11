import { $ } from "../shared/dom.js";
import {
  formatDateIt,
  initialsToItems,
  dayInfo,
} from "../data/calendar-model.js";

export function renderHero(t) {
  const hero = $("hero");
  hero.classList.remove("empty", "is-loading");
  hero.removeAttribute("aria-busy");

  if (!t || !t.year) {
    $("heroTitle").textContent = "Dati non disponibili";
    $("heroWhen").textContent = "—";
    $("heroPickups").innerHTML = "";
    hero.classList.add("empty");
    return;
  }

  $("heroWhen").textContent = formatDateIt(t.year, t.month, t.day);

  const items = initialsToItems(t.initials || "");
  if (items.length === 0) {
    hero.classList.add("empty");
    $("heroTitle").textContent = "Niente da esporre";
    $("heroPickups").innerHTML = "";
    $("liveLine").textContent = "Nessun ritiro domani";
    return;
  }

  $("heroTitle").textContent =
    items.length === 1
      ? "Metti fuori 1 cassonetto"
      : "Metti fuori " + items.length + " cassonetti";
  $("liveLine").textContent = "Domani: " + items.map((x) => x.name).join(", ");

  const root = $("heroPickups");
  root.innerHTML = "";
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "pickup";
    row.innerHTML =
      '<span class="swatch ' +
      item.sw +
      '" aria-hidden="true"></span>' +
      '<span class="name">' +
      item.icon +
      " " +
      item.name +
      "</span>";
    root.appendChild(row);
  });
}

export function loadTomorrowHero() {
  const tom = new Date();
  tom.setDate(tom.getDate() + 1);
  const y = tom.getFullYear();
  const m = tom.getMonth() + 1;
  const d = tom.getDate();
  const info = dayInfo(y, m, d);
  renderHero({
    year: y,
    month: m,
    day: d,
    initials: info.initials,
    bins: info.bins,
  });
}

export function showHomeSkeleton() {
  const hero = $("hero");
  hero.classList.remove("empty");
  hero.classList.add("is-loading");
  hero.setAttribute("aria-busy", "true");
  $("heroTitle").innerHTML = '<span class="sk-bar on-dark long"></span>';
  $("heroWhen").innerHTML = '<span class="sk-bar on-dark mid"></span>';
  $("heroPickups").innerHTML =
    '<div class="pickup sk-pickup" aria-hidden="true"><span class="sk-bar on-dark long"></span></div>' +
    '<div class="pickup sk-pickup" aria-hidden="true"><span class="sk-bar on-dark mid"></span></div>';

  const strip = $("weekStrip");
  strip.innerHTML = "";
  strip.setAttribute("aria-busy", "true");
  for (let i = 0; i < 7; i++) {
    const el = document.createElement("div");
    el.className = "day-chip skeleton";
    el.setAttribute("aria-hidden", "true");
    el.innerHTML =
      '<span class="sk-bar short"></span>' +
      '<span class="sk-bar mid"></span>' +
      '<span class="sk-bar short"></span>';
    strip.appendChild(el);
  }

  const detail = $("dayDetail");
  detail.classList.add("is-loading");
  detail.setAttribute("aria-busy", "true");
  $("dayDetailLabel").innerHTML = '<span class="sk-bar mid"></span>';
  $("dayDetailChips").innerHTML =
    '<span class="sk-bar long"></span><span class="sk-bar mid"></span>';
}
