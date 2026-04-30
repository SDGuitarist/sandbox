/**
 * POST /api/ai/risk
 *
 * Calls Sonnet 4.6 to generate contextual mitigation recommendations
 * based on a project's risk scanner results.
 * Validates the LLM output against the RiskAI Zod schema.
 * Falls back to mock mode when the API key is missing or the model is unreachable.
 *
 * Spec reference:
 *   Section 4 Tool 3 (Probabilistic Output -- Sonnet 4.6)
 *   Section 6 #8 (LLM Routing)
 *   Section 1 (Model Access Preflight, mock mode, Legal Disclaimer, Logging)
 */

import { NextRequest, NextResponse } from 'next/server';
import { RiskScannerInput, RiskAI } from '@/lib/schemas/risk-scanner';
import { hasApiKey, getClient, MODELS } from '@/lib/ai/client';
import { runPreflight } from '@/lib/ai/preflight';
import { getMockRiskAI } from '@/lib/ai/mock';
import { LEGAL_DISCLAIMER } from '@/lib/constants';
import { withAiRateLimit } from '../middleware';

export async function POST(request: NextRequest) {
  const requestId = crypto.randomUUID();

  // Enforce rate limits (Section 9: 10 req/hr per IP, 30 req/day per user)
  const rateLimitResponse = withAiRateLimit(request);
  if (rateLimitResponse) return rateLimitResponse;

  try {
    const body = await request.json();

    // Validate input against the RiskScannerInput schema
    const parsed = RiskScannerInput.safeParse(body);
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
      const mockResult = await getMockRiskAI();
      return NextResponse.json({
        ...mockResult,
        mock: true,
        disclaimer: LEGAL_DISCLAIMER,
        requestId,
      });
    }

    // Call Sonnet 4.6 for risk mitigation recommendations
    const client = getClient();

    const systemPrompt =
      'You are an AI filmmaking ethics risk advisor. ' +
      'Given the project risk profile below, provide actionable mitigation recommendations. ' +
      'Consider the project type, budget tier, department-level AI usage, distribution targets, ' +
      'and union affiliations. Each recommendation should be specific, practical, and directly ' +
      'address a risk dimension (legal, ethical, reputational, or union compliance). ' +
      'Return ONLY a JSON object with a single key "recommendations" containing an array of strings. ' +
      'Each recommendation must be between 10 and 500 characters. ' +
      'Provide between 1 and 10 recommendations, prioritized by risk severity.';

    const userMessage = JSON.stringify({
      projectType: input.projectType,
      budgetTier: input.budgetTier,
      departments: input.departments,
      distributionType: input.distributionType,
      unionAffiliation: input.unionAffiliation,
    });

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15_000);

    let response;
    try {
      response = await client.messages.create({
        model: MODELS.SONNET,
        max_tokens: 2048,
        system: systemPrompt,
        messages: [{ role: 'user', content: userMessage }],
      }, { signal: controller.signal });
    } catch (abortErr) {
      clearTimeout(timeout);
      console.error(`[${requestId}] Sonnet call timed out or aborted for risk route`);
      const mockResult = await getMockRiskAI();
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
      console.error(`[${requestId}] Sonnet returned no text content for risk route`);
      const mockResult = await getMockRiskAI();
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
      console.error(`[${requestId}] Sonnet returned invalid JSON for risk route`);
      const mockResult = await getMockRiskAI();
      return NextResponse.json({
        ...mockResult,
        mock: true,
        disclaimer: LEGAL_DISCLAIMER,
        requestId,
      });
    }

    // Validate against the RiskAI Zod schema
    const validated = RiskAI.safeParse(rawOutput);
    if (!validated.success) {
      console.error(
        `[${requestId}] Sonnet output failed RiskAI schema validation`,
        validated.error.flatten()
      );
      const mockResult = await getMockRiskAI();
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
    console.error(`[${requestId}] Risk AI route error:`, error);
    // Fallback to mock on any unexpected error
    const mockResult = await getMockRiskAI();
    return NextResponse.json({
      ...mockResult,
      mock: true,
      disclaimer: LEGAL_DISCLAIMER,
      requestId,
    });
  }
}
