export function initIosBar() {
  const dark = window.matchMedia("(prefers-color-scheme: dark)");
  function syncIosBar() {
    const el = document.getElementById("iosStatusBar");
    if (el) el.setAttribute("content", dark.matches ? "black-translucent" : "default");
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", syncIosBar);
  } else {
    syncIosBar();
  }
  if (dark.addEventListener) dark.addEventListener("change", syncIosBar);
  else if (dark.addListener) dark.addListener(syncIosBar);
}
