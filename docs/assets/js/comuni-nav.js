/** Search/filter for /comuni/ hub, region and province lists. Progressive enhancement only. */

import { matchAndRankItems, normalizeSearch } from "./shared/search.js";

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function badge(hasCal) {
  return hasCal ? '<span class="badge">Calendario Escilo</span>' : "";
}

function initial(name) {
  const s = String(name || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
  const ch = s.match(/[A-Za-z]/);
  return ch ? ch[0].toUpperCase() : "#";
}

function comuneHref(root, id) {
  const base = root.getAttribute("data-comune-base") || "";
  return base + encodeURIComponent(id) + ".html";
}

function bindSearch(root) {
  const input = root.querySelector("[data-comuni-q]");
  const out = root.querySelector("[data-comuni-results]");
  const src = root.getAttribute("data-directory");
  const browse = document.querySelectorAll("[data-comuni-browse]");
  if (!input || !out || !src) return;

  let comuni = null;
  let loading = null;

  function setBrowseHidden(hidden) {
    browse.forEach((el) => {
      el.hidden = hidden;
    });
  }

  function render(q) {
    const needle = normalizeSearch(q);
    if (needle.length < 2) {
      out.hidden = true;
      out.innerHTML = "";
      setBrowseHidden(false);
      return;
    }
    if (!comuni) return;
    const hits = matchAndRankItems(comuni, needle);
    setBrowseHidden(true);
    out.hidden = false;
    if (!hits.length) {
      out.innerHTML = "<li class=\"search-empty\">Nessun comune trovato.</li>";
      return;
    }
    out.innerHTML = hits
      .map((c) => {
        const meta = [c.provincia, c.regione].filter(Boolean).join(", ");
        return (
          "<li><a class=\"geo-row\" href=\"" +
          comuneHref(root, c.id) +
          '">' +
          '<span class="geo-mark">' +
          escapeHtml(initial(c.name)) +
          "</span><span><span class=\"geo-name\">" +
          escapeHtml(c.name) +
          "</span>" +
          (meta ? '<span class="geo-meta">' + escapeHtml(meta) + "</span>" : "") +
          "</span> " +
          badge(!!c.hasCalendar) +
          "</a></li>"
        );
      })
      .join("");
  }

  function ensureData() {
    if (comuni) return Promise.resolve();
    if (loading) return loading;
    out.hidden = false;
    out.innerHTML = "<li class=\"search-empty\">Caricamento elenco…</li>";
    loading = fetch(src)
      .then((res) => {
        if (!res.ok) throw new Error("HTTP");
        return res.json();
      })
      .then((data) => {
        comuni = Array.isArray(data.comuni) ? data.comuni : [];
        loading = null;
      })
      .catch(() => {
        loading = null;
        comuni = [];
        out.innerHTML = "<li class=\"search-empty\">Elenco non disponibile. Scegli una regione.</li>";
      });
    return loading;
  }

  input.addEventListener("focus", () => {
    ensureData();
  });
  root.addEventListener("submit", (e) => {
    e.preventDefault();
  });
  input.addEventListener("input", () => {
    const q = input.value;
    ensureData().then(() => render(q));
  });
}

document.querySelectorAll("[data-comuni-search]").forEach(bindSearch);
