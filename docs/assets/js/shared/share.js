import { state } from "../state.js";

export async function shareAppLink() {
  const comuneId = state.zoneChoice && state.zoneChoice.comuneId;
  const comuneName = state.zoneChoice && state.zoneChoice.comuneName;
  const url = comuneId
    ? location.origin + "/?comune=" + encodeURIComponent(comuneId)
    : location.origin + "/";
  const text = comuneName
    ? "Calendario ritiri rifiuti a " + comuneName + " — Escilo"
    : "Calendario ritiri rifiuti — Escilo";
  const shareData = {
    title: "Escilo",
    text,
    url,
  };
  try {
    if (navigator.share && (!navigator.canShare || navigator.canShare(shareData))) {
      await navigator.share(shareData);
      return;
    }
    await navigator.clipboard.writeText(url);
  } catch (e) {
    if (e && e.name === "AbortError") return;
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      /* ignore */
    }
  }
}

/**
 * @param {File[]} files
 * @param {{ title?: string, text?: string, url?: string }} [opts]
 * @returns {Promise<"shared" | "downloaded" | "aborted">}
 */
export async function shareFiles(files, opts) {
  const list = Array.isArray(files) ? files.filter(Boolean) : [];
  if (!list.length) return "downloaded";

  const title = (opts && opts.title) || "Escilo";
  const text = (opts && opts.text) || "";
  const url = (opts && opts.url) || "";

  const candidates = [
    { title, text, url, files: list },
    { title, text, files: list },
    { files: list },
  ];

  try {
    if (navigator.share && navigator.canShare) {
      for (let i = 0; i < candidates.length; i++) {
        const shareData = candidates[i];
        try {
          if (!navigator.canShare(shareData)) continue;
          await navigator.share(shareData);
          return "shared";
        } catch (e) {
          if (e && e.name === "AbortError") return "aborted";
          /* try next payload shape */
        }
      }
    }
  } catch (e) {
    if (e && e.name === "AbortError") return "aborted";
  }

  for (const file of list) {
    downloadBlob(file, file.name || "escilo-stats.png");
  }
  return "downloaded";
}

/** @param {Blob} blob @param {string} filename */
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "escilo-stats.png";
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(function () {
    URL.revokeObjectURL(url);
  }, 2500);
}
