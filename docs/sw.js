/* Escilo — service worker: cache shell + Web Push + storico locale */
const CACHE = "escilo-shell-v5";
const PRECACHE = [
  "./",
  "./index.html",
  "./icon-192.png",
  "./icon-512.png",
  "./icon-1024.png",
  "./brand-mark.png",
  "./manifest.webmanifest",
];

const NOTIFY_HISTORY_DB = "escilo-notify";
const NOTIFY_HISTORY_STORE = "history";
const NOTIFY_HISTORY_MAX_DAYS = 30;

function notifyHistoryCutoffIso() {
  const d = new Date();
  d.setDate(d.getDate() - NOTIFY_HISTORY_MAX_DAYS);
  return d.toISOString();
}

function openNotifyHistoryDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(NOTIFY_HISTORY_DB, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(NOTIFY_HISTORY_STORE)) {
        db.createObjectStore(NOTIFY_HISTORY_STORE, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function idbGetAll(store) {
  return new Promise((resolve, reject) => {
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

async function pruneNotifyHistory(db) {
  const cutoff = notifyHistoryCutoffIso();
  const tx = db.transaction(NOTIFY_HISTORY_STORE, "readwrite");
  const store = tx.objectStore(NOTIFY_HISTORY_STORE);
  const all = await idbGetAll(store);
  for (const item of all) {
    if (!item.at || item.at < cutoff) store.delete(item.id);
  }
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function appendNotifyHistory(entry) {
  const at = entry.at || new Date().toISOString();
  const record = {
    id: entry.id || at,
    at,
    title: entry.title || "Escilo",
    body: entry.body || "",
  };
  const db = await openNotifyHistoryDb();
  await new Promise((resolve, reject) => {
    const tx = db.transaction(NOTIFY_HISTORY_STORE, "readwrite");
    tx.objectStore(NOTIFY_HISTORY_STORE).put(record);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  await pruneNotifyHistory(db);
  db.close();
}

async function notifyClientsHistoryUpdated() {
  const clients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  for (const client of clients) {
    client.postMessage({ type: "notify-history-updated" });
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    fetch(event.request)
      .then((res) => {
        const copy = res.clone();
        if (res.ok && new URL(event.request.url).origin === self.location.origin) {
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return res;
      })
      .catch(() => caches.match(event.request).then((hit) => hit || caches.match("./index.html")))
  );
});

self.addEventListener("push", (event) => {
  let data = { title: "Escilo", body: "Non dimenticartene!", url: "./" };
  if (event.data) {
    try {
      const parsed = event.data.json();
      data = { ...data, ...parsed };
    } catch {
      const text = event.data.text();
      if (text) data.body = text;
    }
  }
  event.waitUntil(
    appendNotifyHistory({ title: data.title, body: data.body })
      .then(() => notifyClientsHistoryUpdated())
      .catch((err) => console.error("notify_history_failed", err))
      .then(() =>
        self.registration.showNotification(data.title || "Escilo", {
          body: data.body || "",
          icon: "./icon-192.png",
          badge: "./icon-192.png",
          lang: "it",
          data: { url: data.url || "./" },
        })
      )
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "./";
  const abs = new URL(target, self.registration.scope).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ("focus" in client) {
          client.navigate(abs);
          return client.focus();
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(abs);
    })
  );
});
