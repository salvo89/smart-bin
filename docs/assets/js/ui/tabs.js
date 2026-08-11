import { state } from "../state.js";

export function setTab(tab) {
  state.activeTab = tab;
  document.querySelectorAll(".panel").forEach((p) => {
    const on = p.dataset.panel === tab;
    p.classList.toggle("active", on);
    p.hidden = !on;
  });
  document.querySelectorAll("#bottomNav [data-tab]").forEach((btn) => {
    const on = btn.dataset.tab === tab;
    btn.classList.toggle("active", on);
    if (on) btn.setAttribute("aria-current", "page");
    else btn.removeAttribute("aria-current");
  });
  window.scrollTo(0, 0);
}
