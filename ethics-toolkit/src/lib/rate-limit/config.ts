/**
 * Rate limit configurations for all 4 route patterns from Section 9.
 *
 * Each config defines a window (in milliseconds) and a max request count.
 * The limiter uses these to enforce per-IP or per-user limits.
 *
 * Route patterns:
 *   /api/ai/*              -> 10 req/hour (per IP) + 30 req/day (per user)
 *   /api/realtime/*        -> 120 req/minute (per IP)
 *   /api/auth/save-results -> 5 req/hour (per IP)
 *   All other /api/*       -> 60 req/minute (per IP)
 */

export interface RateLimitConfig {
  /** Maximum number of requests allowed within the window */
  limit: number;
  /** Time window in milliseconds */
  windowMs: number;
  /** Human-readable label for logging/debugging */
  label: string;
}

const ONE_MINUTE_MS = 60 * 1000;
const ONE_HOUR_MS = 60 * ONE_MINUTE_MS;
const ONE_DAY_MS = 24 * ONE_HOUR_MS;

/** /api/ai/* -- 10 requests per hour, scoped per IP */
export const AI_HOURLY: RateLimitConfig = {
  limit: 10,
  windowMs: ONE_HOUR_MS,
  label: 'ai-hourly',
};

/** /api/ai/* -- 30 requests per day, scoped per user */
export const AI_DAILY: RateLimitConfig = {
  limit: 30,
  windowMs: ONE_DAY_MS,
  label: 'ai-daily',
};

/** /api/realtime/* -- 120 requests per minute, scoped per IP */
export const REALTIME: RateLimitConfig = {
  limit: 120,
  windowMs: ONE_MINUTE_MS,
  label: 'realtime',
};

/** /api/auth/save-results -- 5 requests per hour, scoped per IP */
export const AUTH_SAVE_RESULTS: RateLimitConfig = {
  limit: 5,
  windowMs: ONE_HOUR_MS,
  label: 'auth-save-results',
};

/** All other /api/* -- 60 requests per minute, scoped per IP */
export const API_DEFAULT: RateLimitConfig = {
  limit: 60,
  windowMs: ONE_MINUTE_MS,
  label: 'api-default',
};
