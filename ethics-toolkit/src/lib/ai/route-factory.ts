/**
 * Factory for creating AI route handlers.
 *
 * All 3 AI routes (disclosure, risk, budget) share identical scaffolding:
 *   1. Rate limit check
 *   2. Zod input validation
 *   3. Preflight / mock mode check
 *   4. Anthropic API call with 15s timeout
 *   5. Extract text, parse JSON, validate output
 *   6. Fallback to mock on any failure
 *
 * This factory extracts that ~80-line pattern into a reusable function.
 * Each route becomes ~10 lines of config.
 */

import { NextRequest, NextResponse } from 'next/server';
import type { ZodType } from 'zod';
import { hasApiKey, getClient } from '@/lib/ai/client';
import { runPreflight } from '@/lib/ai/preflight';
import { LEGAL_DISCLAIMER } from '@/lib/constants';
import { checkAiRateLimit } from '@/lib/rate-limit/middleware';

interface AiRouteConfig {
  /** Zod schema for validating the request body */
  inputSchema: ZodType;
  /** Zod schema for validating the LLM output */
  outputSchema: ZodType;
  /** Anthropic model ID */
  model: string;
  /** Max tokens for the Anthropic API call */
  maxTokens: number;
  /** System prompt for the LLM */
  systemPrompt: string;
  /** Transform validated input into the user message string */
  buildUserMessage: (input: unknown) => string;
  /** Returns mock data when API is unavailable */
  getMock: () => Promise<unknown>;
  /** Route label for logging */
  routeLabel: string;
}

export function createAiRouteHandler(config: AiRouteConfig) {
  return async function POST(request: NextRequest) {
    const requestId = crypto.randomUUID();

    // Rate limit
    const rateLimitResponse = checkAiRateLimit(request);
    if (rateLimitResponse) return rateLimitResponse;

    try {
      const body = await request.json();

      // Validate input
      const parsed = config.inputSchema.safeParse(body);
      if (!parsed.success) {
        return NextResponse.json(
          { error: 'validation_error', details: parsed.error.flatten(), requestId },
          { status: 400 }
        );
      }

      // Mock mode check
      const preflight = await runPreflight();
      if (preflight.mock || !hasApiKey()) {
        const mockResult = await config.getMock();
        return NextResponse.json({
          ...(mockResult as Record<string, unknown>),
          mock: true,
          disclaimer: LEGAL_DISCLAIMER,
          requestId,
        });
      }

      // Anthropic API call with 15s timeout
      const client = getClient();
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15_000);

      let response;
      try {
        response = await client.messages.create({
          model: config.model,
          max_tokens: config.maxTokens,
          system: config.systemPrompt,
          messages: [{ role: 'user', content: config.buildUserMessage(parsed.data) }],
        }, { signal: controller.signal });
      } catch {
        clearTimeout(timeout);
        console.error(`[${requestId}] API call timed out for ${config.routeLabel}`);
        const mockResult = await config.getMock();
        return NextResponse.json({
          ...(mockResult as Record<string, unknown>),
          mock: true,
          disclaimer: LEGAL_DISCLAIMER,
          requestId,
        });
      } finally {
        clearTimeout(timeout);
      }

      // Extract text
      const textBlock = response.content.find((block) => block.type === 'text');
      if (!textBlock || textBlock.type !== 'text') {
        console.error(`[${requestId}] No text content for ${config.routeLabel}`);
        const mockResult = await config.getMock();
        return NextResponse.json({
          ...(mockResult as Record<string, unknown>),
          mock: true,
          disclaimer: LEGAL_DISCLAIMER,
          requestId,
        });
      }

      // Parse JSON
      let rawOutput: unknown;
      try {
        rawOutput = JSON.parse(textBlock.text);
      } catch {
        console.error(`[${requestId}] Invalid JSON for ${config.routeLabel}`);
        const mockResult = await config.getMock();
        return NextResponse.json({
          ...(mockResult as Record<string, unknown>),
          mock: true,
          disclaimer: LEGAL_DISCLAIMER,
          requestId,
        });
      }

      // Validate output
      const validated = config.outputSchema.safeParse(rawOutput);
      if (!validated.success) {
        console.error(`[${requestId}] Output schema validation failed for ${config.routeLabel}`, validated.error.flatten());
        const mockResult = await config.getMock();
        return NextResponse.json({
          ...(mockResult as Record<string, unknown>),
          mock: true,
          disclaimer: LEGAL_DISCLAIMER,
          requestId,
        });
      }

      return NextResponse.json({
        ...(validated.data as Record<string, unknown>),
        mock: false,
        disclaimer: LEGAL_DISCLAIMER,
        requestId,
      });
    } catch (error) {
      console.error(`[${requestId}] ${config.routeLabel} error:`, error);
      const mockResult = await config.getMock();
      return NextResponse.json({
        ...(mockResult as Record<string, unknown>),
        mock: true,
        disclaimer: LEGAL_DISCLAIMER,
        requestId,
      });
    }
  };
}
