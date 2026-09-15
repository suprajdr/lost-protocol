/* THE LOST PROTOCOL — Offline service worker.
   Caches the app shell + GET /api/team/state, /api/event so operatives can still
   read their current clue while the network is down. Write requests always
   bypass the cache — completion must remain server-validated.
*/
const CACHE_VERSION = "lp-shell-v1";
const SHELL_ASSETS = ["/", "/index.html", "/manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_VERSION).then((cache) => cache.addAll(SHELL_ASSETS).catch(() => {})));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  const isMissionRead = url.pathname.includes("/api/team/state") || url.pathname.includes("/api/event");
  const isSameOrigin = url.origin === self.location.origin;
  if (!isSameOrigin && !isMissionRead) return;
  event.respondWith(
    (async () => {
      try {
        const response = await fetch(request);
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(request, clone)).catch(() => {});
        }
        return response;
      } catch (err) {
        const cached = await caches.match(request);
        if (cached) return cached;
        if (request.destination === "document") {
          const shell = await caches.match("/");
          if (shell) return shell;
        }
        throw err;
      }
    })()
  );
});
