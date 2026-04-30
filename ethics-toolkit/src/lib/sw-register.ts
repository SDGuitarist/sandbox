/**
 * Register the Service Worker on app load.
 *
 * Call this function from a client-side component (e.g., the root layout).
 * The SW caches the app shell, festival seed JSON, and rate table JSON
 * for offline deterministic tool use.
 *
 * Spec reference: Section 1 (Offline Degradation), Section 6 decision #9
 */

export function registerServiceWorker(): void {
  if (typeof window === "undefined") {
    return;
  }

  if (!("serviceWorker" in navigator)) {
    return;
  }

  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .then((registration) => {
        console.log(
          "[SW] Service Worker registered with scope:",
          registration.scope
        );
      })
      .catch((error) => {
        console.error("[SW] Service Worker registration failed:", error);
      });
  });
}
