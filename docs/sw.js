/* Escilo — service worker: cache shell + zona selezionata + Web Push */
const SHELL_CACHE = "escilo-shell-v56";
const ZONE_CACHE = "escilo-zone-v1";
const PRECACHE = [
  "./",
  "./index.html",
  "./stats.html",
  "./fonti.html",
  "./data/ispr/directory.json",
  "./data/ispr/baselines-it.json",
  "./data/ispr/comuni-by-id.json",
  "./icon-192.png",
  "./icon-512.png",
  "./icon-1024.png",
  "./badge-96.png",
  "./notify-icon-192.png",
  "./brand-mark.png",
  "./assets/img/landing/calendar.jpg",
  "./manifest.webmanifest",
  "./assets/css/tokens.css",
  "./assets/css/chrome.css?v=27",
  "./assets/css/app.css?v=27",
  "./assets/css/stats.css?v=58",
  "./assets/css/seo.css?v=18",
  "./assets/js/boot.js",
  "./assets/js/stats.js?v=66",
  "./assets/js/fonti.js?v=18",
  "./assets/js/app-core.js",
  "./assets/js/state.js",
  "./assets/js/shared/constants.js",
  "./assets/js/shared/dom.js",
  "./assets/js/shared/ios-bar.js",
  "./assets/js/shared/storage.js",
  "./assets/js/shared/share.js",
  "./assets/js/share/stats-cards.js?v=43",
  "./assets/js/share/stats-share-ui.js",
  "./assets/js/share/mix-variants.js",
  "./assets/js/share/mix-helpers.js",
  "./assets/js/share/prod-variants.js",
  "./assets/js/data/zones.js",
  "./assets/js/data/ispr.js",
  "./assets/js/data/calendar-model.js",
  "./assets/js/ui/zone-picker.js",
  "./assets/js/ui/hero.js",
  "./assets/js/ui/week-strip.js",
  "./assets/js/ui/month-calendar.js",
  "./assets/js/ui/tabs.js",
  "./assets/js/ui/install-pwa.js",
  "./assets/js/ui/push-notify.js",
  "./assets/js/ui/zone-meta.js",
];

function normalizeBins(bins) {
  if (!Array.isArray(bins)) return [];
  return [...new Set(bins.map(Number).filter((n) => Number.isInteger(n) && n >= 0 && n <= 5))].sort(
    (a, b) => a - b
  );
}

function sameOrigin(url) {
  try {
    return new URL(url, self.location.href).origin === self.location.origin;
  } catch {
    return false;
  }
}

/** Sostituisce la cache zona con le URL della zona corrente (calendari + indici). */
async function replaceZoneCache(urls) {
  const list = [...new Set((urls || []).filter((u) => typeof u === "string" && u && sameOrigin(u)))];
  await caches.delete(ZONE_CACHE);
  if (!list.length) return;
  const cache = await caches.open(ZONE_CACHE);
  await Promise.all(
    list.map(async (url) => {
      try {
        const res = await fetch(url, { cache: "no-cache" });
        if (res.ok) await cache.put(url, res);
      } catch (err) {
        console.error("zone_cache_failed", url, err);
      }
    })
  );
}

async function matchCached(request) {
  const zoneHit = await caches.match(request, { cacheName: ZONE_CACHE });
  if (zoneHit) return zoneHit;
  const shellHit = await caches.match(request, { cacheName: SHELL_CACHE });
  if (shellHit) return shellHit;
  return caches.match("./index.html", { cacheName: SHELL_CACHE });
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k !== SHELL_CACHE && k !== ZONE_CACHE)
            .map((k) => caches.delete(k))
        )
      )
      .then(() => {
        try {
          indexedDB.deleteDatabase("escilo-notify");
        } catch {
          /* ignore */
        }
      })
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  const data = event.data;
  if (!data || data.type !== "cache-zone") return;
  event.waitUntil(replaceZoneCache(data.urls));
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    fetch(event.request)
      .then((res) => res)
      .catch(() => matchCached(event.request))
  );
});

self.addEventListener("push", (event) => {
  let data = { title: "Escilo", body: "Domani c’è un ritiro", url: "./" };
  if (event.data) {
    try {
      const parsed = event.data.json();
      data = { ...data, ...parsed };
    } catch {
      const text = event.data.text();
      if (text) data.body = text;
    }
  }
  const pickupDate =
    typeof data.pickupDate === "string" && /^\d{4}-\d{2}-\d{2}$/.test(data.pickupDate)
      ? data.pickupDate
      : "";
  const bins = normalizeBins(data.bins);
  const url = data.url || "./";

  event.waitUntil(
    (async () => {
      // badge = status bar / sinistra; icon = cassonetto a destra (evita monogramma "E").
      return self.registration.showNotification(data.title || "Escilo", {
        body: data.body || "",
        badge: "./badge-96.png",
        icon: "./notify-icon-192.png",
        lang: "it",
        data: { url, pickupDate, bins },
      });
    })()
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
