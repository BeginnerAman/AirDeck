/**
 * AirDeck Pro v3.0 Service Worker
 * Provides offline caching for the PWA app shell.
 */
const CACHE_NAME = "airdeck-cache-v5";
const STATIC_ASSETS = [
  "/",
  "/static/style.css",
  "/static/app.js",
  "/static/mic-processor.js",
  "/static/icon-192.png",
  "/static/icon-512.png",
  "/static/icon.png",
  "/static/apple-touch-icon.png",
  "/manifest.json"
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((k) => {
          if (k !== CACHE_NAME) return caches.delete(k);
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // Bypass service worker for certificate downloads, REST APIs, and WebSockets
  if (
    url.pathname.startsWith("/api/") ||
    url.pathname === "/cert" ||
    url.pathname.startsWith("/ws")
  ) {
    return;
  }

  // Always go network-first for fresh dynamic assets, fallback to cache
  if (e.request.method === "GET") {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request))
    );
  }
});
