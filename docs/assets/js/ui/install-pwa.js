import { $ } from "../shared/dom.js";
import { state } from "../state.js";

export function isStandaloneDisplay() {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true
  );
}

export function isAndroidChrome() {
  const ua = navigator.userAgent || "";
  if (!/Android/i.test(ua)) return false;
  if (/EdgA|Edg\/|OPR\/|SamsungBrowser|Firefox|FxiOS|YaBrowser/i.test(ua)) {
    return false;
  }
  return /Chrome\/\d+/i.test(ua);
}

export function isIosDevice() {
  const ua = navigator.userAgent || "";
  if (/iPhone|iPad|iPod/i.test(ua)) return true;
  // iPadOS 13+ può presentarsi come Macintosh
  return navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
}

export function isIosSafari() {
  if (!isIosDevice()) return false;
  const ua = navigator.userAgent || "";
  // Solo Safari nativo: escludi Chrome/Firefox/Edge/Opera su iOS
  if (/CriOS|FxiOS|EdgiOS|OPiOS|Chrome|Firefox|Edg/i.test(ua)) return false;
  return /Safari/i.test(ua) && /WebKit/i.test(ua);
}

/** @returns {"android"|"ios"|null} */
export function getInstallOffer() {
  if (isStandaloneDisplay() || !window.isSecureContext) return null;
  if (isAndroidChrome() && state.deferredInstallPrompt) return "android";
  if (isIosSafari()) return "ios";
  return null;
}

export function syncInstallButton() {
  const btn = $("btnInstallApp");
  if (!btn) return;
  const offer = getInstallOffer();
  const show = !!offer;
  btn.hidden = !show;
  btn.classList.toggle("show", show);
  if (!show) return;
  const label = $("btnInstallAppLabel");
  const hint = $("btnInstallAppHint");
  if (offer === "ios") {
    if (label) label.textContent = "Installa app";
    if (hint) hint.textContent = "Aggiungi a Home (Safari)";
  } else {
    if (label) label.textContent = "Installa app";
    if (hint) hint.textContent = "Scorciatoia sul telefono";
  }
}

export function hideAndroidInstallOffer() {
  state.deferredInstallPrompt = null;
  syncInstallButton();
}

export function openIosInstallSheet() {
  const sheet = $("installSheet");
  if (!sheet) return;
  sheet.hidden = false;
  const closeBtn = $("btnInstallSheetClose");
  if (closeBtn) closeBtn.focus();
}

export function closeIosInstallSheet() {
  const sheet = $("installSheet");
  if (!sheet) return;
  sheet.hidden = true;
}

export function onBeforeInstallPrompt(e) {
  e.preventDefault();
  state.deferredInstallPrompt = e;
  syncInstallButton();
}

export function onAppInstalled() {
  hideAndroidInstallOffer();
  closeIosInstallSheet();
}

export async function handleInstallAppClick() {
  const offer = getInstallOffer();
  if (offer === "ios") {
    openIosInstallSheet();
    return;
  }
  if (offer !== "android") {
    syncInstallButton();
    return;
  }
  const promptEvent = state.deferredInstallPrompt;
  hideAndroidInstallOffer();
  try {
    await promptEvent.prompt();
    await promptEvent.userChoice;
  } catch (err) {
    console.error(err);
  }
}
