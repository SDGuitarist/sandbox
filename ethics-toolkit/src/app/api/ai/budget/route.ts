/**
 * POST /api/ai/budget
 *
 * Calls Sonnet 4.6 to generate an ethical analysis of AI vs. human budget
 * trade-offs for a specific film production role.
 * Validates the LLM output against the BudgetAI Zod schema.
 * Falls back to mock mode when the API key is missing or the model is unreachable.
 *
 * Spec reference:
 *   Section 4 Tool 5 (Probabilistic Output -- Sonnet 4.6)
 *   Section 6 #8 (LLM Routing)
 *   Section 1 (Model Access Preflight, mock mode, Legal Disclaimer, Logging)
 */

import { NextRequest, NextResponse } from 'next/server';
import { BudgetInput, BudgetAI } from '@/lib/schemas/budget';
import { hasApiKey, getClient, MODELS } from '@/lib/ai/client';
import { runPreflight } from '@/lib/ai/preflight';
import { getMockBudgetAI } from '@/lib/ai/mock';
import { LEGAL_DISCLAIMER } from '@/lib/constants';
import { withAiRateLimit } from '../middleware';

export async function POST(request: NextRequest) {
  const requestId = crypto.randomUUID();

  // Enforce rate limits (Section 9: 10 req/hr per IP, 30 req/day per user)
  const rateLimitResponse = withAiRateLimit(request);
  if (rateLimitResponse) return rateLimitResponse;

  try {
    const body = await request.json();

    // Validate input against the BudgetInput schema
    const parsed = BudgetInput.safeParse(body);
    if (!parsed.success) {
      return NextResponse.json(
        { error: 'validation_error', details: parsed.error.flatten(), requestId },
        { status: 400 }
      );
    }

    const input = parsed.data;

    // Check if we should use mock mode
    const preflight = await runPreflight();
    if (preflight.mock || !hasApiKey()) {
      const mockResult = await getMockBudgetAI();
      return NextResponse.json({
        ...mockResult,
        mock: true,
        disclaimer: LEGAL_DISCLAIMER,
        requestId,
      });
    }

    // Call Sonnet 4.6 for ethical budget analysis
    const client = getClient();

    const systemPrompt =
      'You are an AI filmmaking ethics budget advisor. ' +
      'Given the role, budget tier, and project scope below, provide a thoughtful ethical analysis ' +
      'of the trade-offs between using AI tools versus hiring human professionals for this role. ' +
      'Consider displacement risk, fair compensation, union standards, creative integrity, ' +
      'and the broader impact on the filmmaking community. ' +
      'Return ONLY a JSON object with a single key "ethicalAnalysis" containing the analysis as a string. ' +
      'The ethicalAnalysis must be between 50 and 2000 characters.';

    const userMessage = JSON.stringify({
      role: input.role,
      budgetTier: input.budgetTier,
      projectScope: input.projectScope,
      currentBudgetForRole: input.currentBudgetForRole,
    });

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15_000);

    let response;
    try {
      response = await client.messages.create({
        model: MODELS.SONNET,
        max_tokens: 1024,
        system: systemPrompt,
        messages: [{ role: 'user', content: userMessage }],
      }, { signal: controller.signal });
    } catch (abortErr) {
      clearTimeout(timeout);
      console.error(`[${requestId}] Sonnet call timed out or aborted for budget route`);
      const mockResult = await getMockBudgetAI();
      return NextResponse.json({
        ...mockResult,
        mock: true,
        disclaimer: LEGAL_DISCLAIMER,
        requestId,
      });
    } finally {
      clearTimeout(timeout);
    }

    // Extract text content from the response
    const textBlock = response.content.find((block) => block.type === 'text');
    if (!textBlock || textBlock.type !== 'text') {
      console.error(`[${requestId}] Sonnet returned no text content for budget route`);
      const mockResult = await getMockBudgetAI();
      return NextResponse.json({
        ...mockResult,
        mock: true,
        disclaimer: LEGAL_DISCLAIMER,
        requestId,
      });
    }

    // Parse the JSON from the LLM response
    let rawOutput: unknown;
    try {
      rawOutput = JSON.parse(textBlock.text);
    } catch {
      console.error(`[${requestId}] Sonnet returned invalid JSON for budget route`);
      const mockResult = await getMockBudgetAI();
      return NextResponse.json({
        ...mockResult,
        mock: true,
        disclaimer: LEGAL_DISCLAIMER,
        requestId,
      });
    }

    // Validate against the BudgetAI Zod schema
    const validated = BudgetAI.safeParse(rawOutput);
    if (!validated.success) {
      console.error(
        `[${requestId}] Sonnet output failed BudgetAI schema validation`,
        validated.error.flatten()
      );
      const mockResult = await getMockBudgetAI();
      return NextResponse.json({
        ...mockResult,
        mock: true,
        disclaimer: LEGAL_DISCLAIMER,
        requestId,
      });
    }

    return NextResponse.json({
      ...validated.data,
      mock: false,
      disclaimer: LEGAL_DISCLAIMER,
      requestId,
    });
  } catch (error) {
    console.error(`[${requestId}] Budget AI route error:`, error);
    // Fallback to mock on any unexpected error
    const mockResult = await getMockBudgetAI();
    return NextResponse.json({
      ...mockResult,
      mock: true,
      disclaimer: LEGAL_DISCLAIMER,
      requestId,
    });
  }
}
