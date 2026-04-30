/**
 * Service Worker: cache app shell, festival seed JSON, and rate table JSON.
 * Serve cached responses when offline. Show "AI recommendation temporarily
 * unavailable" state for network-dependent resources.
 *
 * Spec reference: Section 1 (Offline Degradation), Section 6 decision #9
 */

const CACHE_NAME = "ethics-toolkit-v1";

/**
 * App shell URLs to cache on install.
 * These are the core assets needed for the app to render offline.
 */
const APP_SHELL = [
  "/",
  "/offline.html",
];

/**
 * API/data URLs to cache for offline deterministic tool use.
 */
const DATA_URLS = [
  "/api/tools/festival",
];

/**
 * On install, cache the app shell and data URLs.
 */
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll([...APP_SHELL, ...DATA_URLS]);
    })
  );
  self.skipWaiting();
});

/**
 * On activate, clean up old caches.
 */
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

/**
 * Fetch strategy:
 * - For navigation requests: network-first, fall back to cache, then offline.html
 * - For API data requests (festival, rate table): network-first, cache fallback
 * - For static assets: cache-first, then network
 * - For all other requests: network-first, cache fallback
 */
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Navigation requests (HTML pages)
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // Cache successful navigation responses
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, clone);
          });
          return response;
        })
        .catch(() => {
          return caches.match(event.request).then((cached) => {
            return cached || caches.match("/offline.html");
          });
        })
    );
    return;
  }

  // API data requests (festival policies, rate table data)
  if (url.pathname.startsWith("/api/tools/festival")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // Cache fresh API responses
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, clone);
          });
          return response;
        })
        .catch(() => {
          return caches.match(event.request).then((cached) => {
            if (cached) {
              return cached;
            }
            // Return a JSON response indicating data is unavailable offline
            return new Response(
              JSON.stringify({
                error: "Festival data unavailable offline.",
                offline: true,
              }),
              {
                status: 503,
                headers: { "Content-Type": "application/json" },
              }
            );
          });
        })
    );
    return;
  }

  // Budget API POST requests -- cannot be cached, return unavailable when offline
  if (url.pathname.startsWith("/api/tools/budget")) {
    event.respondWith(
      fetch(event.request).catch(() => {
        return new Response(
          JSON.stringify({
            error: "AI recommendation temporarily unavailable. Try again when online.",
            offline: true,
          }),
          {
            status: 503,
            headers: { "Content-Type": "application/json" },
          }
        );
      })
    );
    return;
  }

  // Static assets (JS, CSS, images) -- cache-first
  if (
    url.pathname.match(/\.(js|css|png|jpg|jpeg|svg|ico|woff2?)$/) ||
    url.pathname.startsWith("/_next/static/")
  ) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) {
          return cached;
        }
        return fetch(event.request).then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, clone);
          });
          return response;
        });
      })
    );
    return;
  }

  // All other requests -- network-first with cache fallback
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (event.request.method === "GET") {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, clone);
          });
        }
        return response;
      })
      .catch(() => {
        return caches.match(event.request).then((cached) => {
          return (
            cached ||
            new Response("Offline", {
              status: 503,
              headers: { "Content-Type": "text/plain" },
            })
          );
        });
      })
  );
});
