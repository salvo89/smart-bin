import {
  LS_PUSH_HOUR,
  LS_PUSH_HOUR_USER,
  LS_PUSH_REGISTERED,
  PUSH_API,
} from "../shared/constants.js";
import { $ } from "../shared/dom.js";
import { state } from "../state.js";
import { isIosDevice, isStandaloneDisplay } from "./install-pwa.js";

export function migratePushHourDefault() {
  if (localStorage.getItem(LS_PUSH_HOUR_USER) === "1") return;
  localStorage.removeItem(LS_PUSH_HOUR);
}

export function savePushHour(hour) {
  localStorage.setItem(LS_PUSH_HOUR, String(hour));
  localStorage.setItem(LS_PUSH_HOUR_USER, "1");
}

export function pushSupported() {
  return (
    window.isSecureContext &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

export function readPushHour() {
  if (localStorage.getItem(LS_PUSH_HOUR_USER) !== "1") return 20;
  const raw = localStorage.getItem(LS_PUSH_HOUR);
  if (raw === null || raw === "") return 20;
  const n = Number(raw);
  // Solo ore intere 01–23 (niente mezz'ore, né 00/24 limite giornata).
  if (Number.isInteger(n) && n >= 1 && n <= 23) return n;
  return 20;
}

export function formatPushHourLabel(hour) {
  return String(hour).padStart(2, "0") + ":00";
}

export function fillNotifyHourSelect() {
  const sel = $("notifyHour");
  if (!sel) return;
  if (!sel.options.length) {
    for (let h = 1; h <= 23; h++) {
      const opt = document.createElement("option");
      opt.value = String(h);
      opt.textContent = String(h).padStart(2, "0") + ":00";
      if (h === 20) opt.selected = true;
      sel.appendChild(opt);
    }
  }
  sel.value = String(readPushHour());
}

export function setNotifyHint(msg) {
  const el = $("notifyHint");
  if (!el) return;
  if (msg) {
    el.hidden = false;
    el.textContent = msg;
  } else {
    el.hidden = true;
    el.textContent = "";
  }
}

export function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

export async function fetchVapidPublicKey() {
  const urls = [PUSH_API.vapid, "/.netlify/functions/push-vapid-public"];
  for (const url of urls) {
    try {
      const res = await fetch(url, { cache: "no-cache" });
      if (!res.ok) continue;
      const data = await res.json();
      if (data && data.publicKey) return data.publicKey;
    } catch (err) {
      console.error(err);
    }
  }
  throw new Error("vapid_unavailable");
}

export async function getPushSubscription() {
  const reg = await navigator.serviceWorker.ready;
  return reg.pushManager.getSubscription();
}

export function markPushRegistered() {
  localStorage.setItem(LS_PUSH_REGISTERED, "1");
}

export function clearPushRegistered() {
  localStorage.removeItem(LS_PUSH_REGISTERED);
}

export function isPushRegisteredLocally() {
  return localStorage.getItem(LS_PUSH_REGISTERED) === "1";
}

export async function reconcilePushState() {
  if (!pushSupported()) {
    clearPushRegistered();
    return;
  }
  let sub = null;
  try {
    sub = await getPushSubscription();
  } catch {
    sub = null;
  }

  if (isPushRegisteredLocally()) {
    if (Notification.permission !== "granted" || !sub) {
      clearPushRegistered();
      if (sub) {
        try {
          await sub.unsubscribe();
        } catch (err) {
          console.error(err);
        }
      }
    }
    return;
  }

  if (sub) {
    try {
      await sub.unsubscribe();
    } catch (err) {
      console.error(err);
    }
  }
}

export async function isPushActive() {
  if (!isPushRegisteredLocally()) return false;
  if (!pushSupported()) return false;
  if (Notification.permission !== "granted") return false;
  try {
    const sub = await getPushSubscription();
    return !!sub;
  } catch {
    return false;
  }
}

export function openNotifySheet() {
  const sheet = $("notifySheet");
  if (!sheet) return;
  sheet.hidden = false;
  const closeBtn = $("btnNotifySheetClose");
  if (closeBtn) closeBtn.focus();
}

export function closeNotifySheet() {
  const sheet = $("notifySheet");
  if (!sheet) return;
  sheet.hidden = true;
}

export async function syncPushOffer(opts) {
  const keepHint = !!(opts && opts.keepHint);
  const btn = $("btnPushOffer");
  const toggle = $("notifyToggle");
  const hourRow = $("notifyHourRow");
  if (!btn || !toggle) return;

  fillNotifyHourSelect();

  const label = $("btnPushOfferLabel");
  const hint = $("btnPushOfferHint");
  const canOffer = !!state.zoneChoice && (pushSupported() || isIosDevice());

  if (!canOffer) {
    btn.hidden = true;
    btn.classList.remove("show", "is-on");
    toggle.checked = false;
    toggle.disabled = true;
    if (hourRow) hourRow.hidden = true;
    return;
  }

  btn.hidden = false;
  btn.classList.add("show");

  if (!state.zoneChoice) {
    toggle.checked = false;
    toggle.disabled = true;
    if (hourRow) hourRow.hidden = true;
    setNotifyHint("Scegli comune e via per attivare gli avvisi.");
    btn.classList.remove("is-on");
    if (label) label.textContent = "Notifiche";
    if (hint) hint.textContent = "Scegli prima la zona";
    return;
  }

  if (!pushSupported()) {
    toggle.checked = false;
    toggle.disabled = true;
    if (hourRow) hourRow.hidden = true;
    setNotifyHint("Questo browser non supporta le notifiche push.");
    btn.classList.remove("is-on");
    if (label) label.textContent = "Notifiche";
    if (hint) hint.textContent = "Non disponibili qui";
    return;
  }

  if (isIosDevice() && !isStandaloneDisplay()) {
    toggle.checked = false;
    toggle.disabled = true;
    if (hourRow) hourRow.hidden = true;
    setNotifyHint(
      "Su iPhone/iPad: apri Escilo da Safari → Condividi → Aggiungi a Home, poi riapri l’app dalla Home e abilita le notifiche."
    );
    btn.classList.remove("is-on");
    if (label) label.textContent = "Notifiche";
    if (hint) hint.textContent = "Serve l’app sulla Home";
    return;
  }

  toggle.disabled = state.notifyToggleBusy;
  if (hourRow) hourRow.hidden = false;
  if (!keepHint) setNotifyHint("");
  await reconcilePushState();

  let enabled = false;
  try {
    enabled = await isPushActive();
    if (!state.notifyToggleBusy) toggle.checked = enabled;
  } catch (err) {
    console.error(err);
    enabled = false;
    if (!state.notifyToggleBusy) toggle.checked = false;
    if (!keepHint) setNotifyHint("Stato notifiche non disponibile");
  }

  btn.classList.toggle("is-on", enabled);
  if (label) label.textContent = "Notifiche";
  if (enabled) {
    if (hint) hint.textContent = "Attive · " + formatPushHourLabel(readPushHour());
  } else {
    if (hint) hint.textContent = "Attivale e Escilo te lo ricorda.";
  }
}

export async function requestNotificationPermission() {
  if (!("Notification" in window)) {
    throw new Error("permission_denied");
  }
  // Ogni attivazione richiama il prompt di sistema finché il permesso
  // resta "default". Se è già "denied" il browser non mostra più il
  // dialogo: la chiamata risolve subito e l'UI guida alle impostazioni.
  const permission = await Notification.requestPermission();
  if (permission === "granted") return permission;
  throw new Error(
    Notification.permission === "denied" ? "permission_blocked" : "permission_denied"
  );
}

export async function subscribePush() {
  await requestNotificationPermission();
  const publicKey = await fetchVapidPublicKey();
  const reg = await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    });
  }
  const hour = readPushHour();
  try {
    const res = await fetch(PUSH_API.subscribe, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subscription: sub.toJSON(),
        calendarId: state.zoneChoice.calendar,
        hour,
      }),
    });
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.error || "subscribe_failed");
    }
    markPushRegistered();
    state.pushEnableWanted = false;
    return sub;
  } catch (err) {
    clearPushRegistered();
    try {
      await sub.unsubscribe();
    } catch (unsubErr) {
      console.error(unsubErr);
    }
    throw err;
  }
}

export async function resumePushIfPermitted() {
  if (!state.pushEnableWanted || !state.zoneChoice || state.notifyToggleBusy) return;
  if (!pushSupported() || Notification.permission !== "granted") return;
  if (await isPushActive()) {
    state.pushEnableWanted = false;
    await syncPushOffer();
    return;
  }
  const toggle = $("notifyToggle");
  const sw = toggle && toggle.closest(".notify-switch");
  state.notifyToggleBusy = true;
  if (toggle) toggle.disabled = true;
  if (sw) sw.classList.add("is-busy");
  setNotifyHint("Attivazione…");
  try {
    await subscribePush();
    setNotifyHint("");
  } catch (err) {
    console.error(err);
  } finally {
    state.notifyToggleBusy = false;
    if (sw) sw.classList.remove("is-busy");
    await syncPushOffer({ keepHint: true });
  }
}

export function watchNotificationPermission() {
  if (
    state.notifyPermissionWatch ||
    !navigator.permissions ||
    !navigator.permissions.query
  ) {
    return;
  }
  navigator.permissions
    .query({ name: "notifications" })
    .then((status) => {
      state.notifyPermissionWatch = status;
      status.addEventListener("change", () => {
        resumePushIfPermitted();
      });
    })
    .catch(() => {});
}

export async function unsubscribePush() {
  clearPushRegistered();
  const sub = await getPushSubscription();
  if (sub) {
    try {
      await fetch(PUSH_API.unsubscribe, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint: sub.endpoint }),
      });
    } catch (err) {
      console.error(err);
    }
    await sub.unsubscribe();
  }
}

export async function refreshPushRegistration() {
  if (!state.zoneChoice || Notification.permission !== "granted") return;
  if (!isPushRegisteredLocally()) return;
  const sub = await getPushSubscription();
  if (!sub) return;
  const res = await fetch(PUSH_API.subscribe, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      subscription: sub.toJSON(),
      calendarId: state.zoneChoice.calendar,
      hour: readPushHour(),
    }),
  });
  if (res.ok) markPushRegistered();
}

export async function handleNotifyToggleChange() {
  const toggle = $("notifyToggle");
  const sw = toggle.closest(".notify-switch");
  if (state.notifyToggleBusy) {
    toggle.checked = !toggle.checked;
    return;
  }
  state.notifyToggleBusy = true;
  toggle.disabled = true;
  if (sw) sw.classList.add("is-busy");
  let keepHint = true;
  setNotifyHint(toggle.checked ? "Attivazione…" : "Disattivazione…");
  try {
    if (toggle.checked) {
      if (!state.zoneChoice) {
        toggle.checked = false;
        setNotifyHint("Scegli prima una zona");
        return;
      }
      state.pushEnableWanted = true;
      watchNotificationPermission();
      // Ogni ON richiama il consenso di sistema; lo switch resta ON
      // solo se il permesso è granted e la subscribe va a buon fine.
      await subscribePush();
      setNotifyHint("");
      keepHint = false;
    } else {
      state.pushEnableWanted = false;
      await unsubscribePush();
      setNotifyHint("");
      keepHint = false;
    }
  } catch (err) {
    console.error(err);
    toggle.checked = false;
    try {
      await unsubscribePush();
    } catch (cleanupErr) {
      console.error(cleanupErr);
    }
    keepHint = true;
    if (err && err.message === "permission_blocked") {
      setNotifyHint(
        "Notifiche bloccate dal dispositivo. Abilitale nelle impostazioni del browser/sito, poi riprova con lo switch."
      );
    } else if (err && err.message === "permission_denied") {
      setNotifyHint("Permesso non concesso. Riprova e accetta per attivarle.");
    } else if (err && err.message === "vapid_unavailable") {
      setNotifyHint("Server push non configurato");
    } else {
      setNotifyHint("Attivazione non riuscita");
    }
  } finally {
    state.notifyToggleBusy = false;
    if (sw) sw.classList.remove("is-busy");
    await syncPushOffer({ keepHint });
  }
}

export async function handleNotifyHourChange() {
  const hour = Number($("notifyHour").value);
  if (!Number.isInteger(hour) || hour < 1 || hour > 23) return;
  savePushHour(hour);
  const sel = $("notifyHour");
  sel.disabled = true;
  setNotifyHint("Aggiornamento…");
  try {
    await refreshPushRegistration();
    setNotifyHint("");
    await syncPushOffer();
  } catch (err) {
    console.error(err);
    setNotifyHint("Ora salvata in locale; sync server fallito");
    await syncPushOffer({ keepHint: true });
  } finally {
    sel.disabled = false;
  }
}
