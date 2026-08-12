import { initIosBar } from "./shared/ios-bar.js";

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function groupByProvider(comuni) {
  const map = new Map();
  for (const c of comuni) {
    const key = c.provider || "Altro";
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(c);
  }
  for (const list of map.values()) {
    list.sort((a, b) => String(a.name).localeCompare(String(b.name), "it"));
  }
  return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0], "it"));
}

function providerSourcePage(list) {
  const pages = [...new Set(list.map((c) => c.sourcePage).filter(Boolean))];
  return pages.length === 1 ? pages[0] : null;
}

function renderSkeleton(count) {
  const root = document.getElementById("providers");
  root.setAttribute("aria-busy", "true");
  const n = count || 5;
  let html = "";
  for (let i = 0; i < n; i++) {
    html +=
      '<div class="provider skeleton" aria-hidden="true">' +
      '<div class="provider-sk-head">' +
      '<p class="provider-name"><span class="sk-bar ' +
      (i % 2 ? "mid" : "long") +
      '"></span></p>' +
      '<p class="provider-count"><span class="sk-bar short"></span></p>' +
      "</div></div>";
  }
  root.innerHTML = html;
}

function render(data) {
  const root = document.getElementById("providers");
  root.removeAttribute("aria-busy");
  const comuni = Array.isArray(data.comuni) ? data.comuni : [];
  const groups = groupByProvider(comuni);

  root.innerHTML = groups
    .map(([provider, list], idx) => {
      const page = providerSourcePage(list);
      const linkHtml = page
        ? '<a class="provider-link ext-link" href="' +
          escapeHtml(page) +
          '" target="_blank" rel="noopener noreferrer">Pagina calendari ufficiale' +
          '<span class="visually-hidden"> (si apre in una nuova scheda)</span></a>'
        : "";
      const items = list
        .map((c) => {
          const name = c.sourcePage
            ? '<a class="ext-link" href="' +
              escapeHtml(c.sourcePage) +
              '" target="_blank" rel="noopener noreferrer">' +
              escapeHtml(c.name) +
              '<span class="visually-hidden"> (si apre in una nuova scheda)</span></a>'
            : escapeHtml(c.name);
          return "<li><span class=\"name\">" + name + "</span></li>";
        })
        .join("");

      return (
        '<details class="provider escilo-block" style="--block-i:' +
        idx +
        '"' +
        (idx === 0 ? " open" : "") +
        ">" +
        "<summary><div class=\"provider-head\">" +
        '<p class="provider-name">' +
        escapeHtml(provider) +
        "</p>" +
        '<p class="provider-count">' +
        list.length +
        (list.length === 1 ? " comune" : " comuni") +
        "</p>" +
        "</div></summary>" +
        '<div class="provider-body">' +
        linkHtml +
        '<ul class="comuni">' +
        items +
        "</ul>" +
        "</div></details>"
      );
    })
    .join("");
}

async function main() {
  const status = document.getElementById("status");
  const root = document.getElementById("providers");
  renderSkeleton(5);
  try {
    const res = await fetch("calendars/sources.json", { cache: "no-cache" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    render(data);
  } catch (err) {
    console.error(err);
    if (root) {
      root.innerHTML = "";
      root.removeAttribute("aria-busy");
    }
    if (status) {
      status.hidden = false;
      status.className = "status error";
      status.textContent = "Impossibile caricare le fonti. Ricarica la pagina.";
    }
  }
}

initIosBar();
main();
