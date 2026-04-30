/**
 * Rate limit middleware for Next.js API routes.
 *
 * Extracts the client IP from request headers, checks the rate limiter,
 * and returns a 429 response when the limit is exceeded.
 *
 * Response shape on limit: { "error": "rate_limited", "retryAfter": <seconds> }
 *
 * Spec reference: Section 9
 */

import { NextRequest, NextResponse } from 'next/server';
import { createRateLimiter, type RateLimiter } from './limiter';
import {
  AI_HOURLY,
  AI_DAILY,
  REALTIME,
  AUTH_SAVE_RESULTS,
  API_DEFAULT,
  type RateLimitConfig,
} from './config';

// ---------------------------------------------------------------------------
// Singleton limiters -- one per route pattern. Created once, shared across
// all requests within the same serverless function instance.
// ---------------------------------------------------------------------------

const limiters = new Map<string, RateLimiter>();

/** Get or create a singleton limiter for the given config. */
function getLimiter(config: RateLimitConfig): RateLimiter {
  let limiter = limiters.get(config.label);
  if (!limiter) {
    limiter = createRateLimiter(config);
    limiters.set(config.label, limiter);
  }
  return limiter;
}

// ---------------------------------------------------------------------------
// IP extraction
// ---------------------------------------------------------------------------

/**
 * Extract the client IP address from request headers.
 *
 * Checks (in order):
 *   1. x-forwarded-for (first value -- the original client IP)
 *   2. x-real-ip
 *   3. Falls back to "unknown" (still rate-limited so we don't bypass)
 */
export function extractIp(request: NextRequest): string {
  const forwarded = request.headers.get('x-forwarded-for');
  if (forwarded) {
    // x-forwarded-for can be "client, proxy1, proxy2"
    const first = forwarded.split(',')[0].trim();
    if (first) return first;
  }

  const realIp = request.headers.get('x-real-ip');
  if (realIp) return realIp.trim();

  return 'unknown';
}

// ---------------------------------------------------------------------------
// 429 response helper
// ---------------------------------------------------------------------------

function rateLimitedResponse(retryAfter: number): NextResponse {
  return NextResponse.json(
    { error: 'rate_limited', retryAfter },
    {
      status: 429,
      headers: { 'Retry-After': String(retryAfter) },
    }
  );
}

// ---------------------------------------------------------------------------
// Route-specific check functions
// ---------------------------------------------------------------------------

/**
 * Check rate limits for /api/ai/* routes.
 *
 * Enforces TWO limits:
 *   - 10 requests/hour per IP
 *   - 30 requests/day per user (falls back to IP if no userId)
 *
 * Returns a 429 NextResponse if either limit is exceeded, or null if OK.
 */
export function checkAiRateLimit(
  request: NextRequest,
  userId?: string
): NextResponse | null {
  const ip = extractIp(request);

  // Check hourly per-IP limit
  const hourlyLimiter = getLimiter(AI_HOURLY);
  const hourlyResult = hourlyLimiter.check(`${AI_HOURLY.label}:${ip}`);
  if (hourlyResult.limited) {
    return rateLimitedResponse(hourlyResult.retryAfter);
  }

  // Check daily per-user limit (falls back to IP if no userId)
  const userKey = userId ?? ip;
  const dailyLimiter = getLimiter(AI_DAILY);
  const dailyResult = dailyLimiter.check(`${AI_DAILY.label}:${userKey}`);
  if (dailyResult.limited) {
    return rateLimitedResponse(dailyResult.retryAfter);
  }

  return null;
}

/**
 * Check rate limits for /api/realtime/* routes.
 * 120 requests/minute per IP.
 */
export function checkRealtimeRateLimit(
  request: NextRequest
): NextResponse | null {
  const ip = extractIp(request);
  const limiter = getLimiter(REALTIME);
  const result = limiter.check(`${REALTIME.label}:${ip}`);
  if (result.limited) {
    return rateLimitedResponse(result.retryAfter);
  }
  return null;
}

/**
 * Check rate limits for /api/auth/save-results.
 * 5 requests/hour per IP.
 */
export function checkSaveResultsRateLimit(
  request: NextRequest
): NextResponse | null {
  const ip = extractIp(request);
  const limiter = getLimiter(AUTH_SAVE_RESULTS);
  const result = limiter.check(`${AUTH_SAVE_RESULTS.label}:${ip}`);
  if (result.limited) {
    return rateLimitedResponse(result.retryAfter);
  }
  return null;
}

/**
 * Check rate limits for all other /api/* routes.
 * 60 requests/minute per IP.
 */
export function checkDefaultRateLimit(
  request: NextRequest
): NextResponse | null {
  const ip = extractIp(request);
  const limiter = getLimiter(API_DEFAULT);
  const result = limiter.check(`${API_DEFAULT.label}:${ip}`);
  if (result.limited) {
    return rateLimitedResponse(result.retryAfter);
  }
  return null;
}
