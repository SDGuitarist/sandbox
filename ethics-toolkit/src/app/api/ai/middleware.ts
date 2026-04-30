/**
 * Rate limiting middleware for /api/ai/* routes.
 *
 * Enforces Section 9 limits:
 *   - 10 requests/hour per IP
 *   - 30 requests/day per user
 *
 * Usage in an AI route handler:
 *   import { withAiRateLimit } from './middleware';
 *
 *   export async function POST(request: NextRequest) {
 *     const rateLimitResponse = withAiRateLimit(request);
 *     if (rateLimitResponse) return rateLimitResponse;
 *     // ... proceed with AI call
 *   }
 *
 * The userId parameter is optional. When provided (e.g. from an auth check
 * earlier in the handler), the daily limit is scoped to that user. When
 * omitted, the daily limit falls back to per-IP scoping.
 *
 * Mock mode note: "Mock mode bypasses Anthropic API but still enforces
 * rate limits and input validation." (Section 9)
 */

import { NextRequest, NextResponse } from 'next/server';
import { checkAiRateLimit } from '@/lib/rate-limit/middleware';

/**
 * Apply AI rate limiting to a request.
 *
 * @param request - The incoming NextRequest
 * @param userId  - Optional authenticated user ID for daily per-user limit
 * @returns A 429 NextResponse if rate limited, or null if the request is allowed
 */
export function withAiRateLimit(
  request: NextRequest,
  userId?: string
): NextResponse | null {
  return checkAiRateLimit(request, userId);
}
