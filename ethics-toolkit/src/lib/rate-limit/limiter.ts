/**
 * In-memory rate limiter using Map<string, { count: number; resetAt: number }>.
 *
 * Acceptable for the May 30 single-process deployment and testable without
 * external dependencies. Do NOT add Upstash, Redis, or any new infrastructure.
 *
 * How it works:
 *   - Each unique key (e.g. "ai-hourly:192.168.1.1") gets an entry in the map.
 *   - On each check, if the entry has expired (Date.now() >= resetAt), it resets.
 *   - If the entry is within the window and count >= limit, the request is rejected.
 *   - Expired entries are cleaned up periodically to prevent memory leaks.
 *
 * Spec reference: Section 9
 */

import type { RateLimitConfig } from './config';

interface RateLimitEntry {
  count: number;
  resetAt: number;
}

export interface RateLimitResult {
  limited: boolean;
  /** Seconds until the window resets. Only meaningful when limited === true. */
  retryAfter: number;
  /** Current request count after this check (useful for headers/debugging) */
  current: number;
  /** The configured limit */
  limit: number;
}

/**
 * Creates a rate limiter backed by an in-memory Map.
 *
 * Usage:
 *   const limiter = createRateLimiter({ limit: 10, windowMs: 60_000, label: 'demo' });
 *   const result = limiter.check('user-123');
 *   if (result.limited) { /* return 429 * / }
 */
export function createRateLimiter(config: RateLimitConfig) {
  const store = new Map<string, RateLimitEntry>();

  // Auto-cleanup interval: runs every 60 seconds to purge expired entries.
  // Uses unref() so it does not keep the Node process alive.
  const cleanupInterval = setInterval(() => {
    const now = Date.now();
    const expiredKeys: string[] = [];
    store.forEach((entry, key) => {
      if (now >= entry.resetAt) {
        expiredKeys.push(key);
      }
    });
    for (const key of expiredKeys) {
      store.delete(key);
    }
  }, 60_000);

  if (typeof cleanupInterval === 'object' && 'unref' in cleanupInterval) {
    cleanupInterval.unref();
  }

  function check(key: string): RateLimitResult {
    const now = Date.now();
    const existing = store.get(key);

    // If there is no entry or the window has expired, start a fresh window.
    if (!existing || now >= existing.resetAt) {
      store.set(key, {
        count: 1,
        resetAt: now + config.windowMs,
      });
      return {
        limited: false,
        retryAfter: 0,
        current: 1,
        limit: config.limit,
      };
    }

    // Window is still active. Increment the count.
    existing.count += 1;

    if (existing.count > config.limit) {
      const retryAfterMs = existing.resetAt - now;
      const retryAfterSeconds = Math.ceil(retryAfterMs / 1000);
      return {
        limited: true,
        retryAfter: retryAfterSeconds,
        current: existing.count,
        limit: config.limit,
      };
    }

    return {
      limited: false,
      retryAfter: 0,
      current: existing.count,
      limit: config.limit,
    };
  }

  /** Reset a specific key. Useful for testing. */
  function reset(key: string): void {
    store.delete(key);
  }

  /** Clear all entries. Useful for testing. */
  function clear(): void {
    store.clear();
  }

  /** Stop the background cleanup interval. Call during graceful shutdown. */
  function destroy(): void {
    clearInterval(cleanupInterval);
    store.clear();
  }

  return { check, reset, clear, destroy };
}

export type RateLimiter = ReturnType<typeof createRateLimiter>;
