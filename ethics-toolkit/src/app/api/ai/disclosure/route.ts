/**
 * POST /api/ai/disclosure
 *
 * Calls Haiku 4.5 to generate a natural-language disclosure statement.
 * Validates the LLM output against the DisclosureAI Zod schema.
 * Falls back to mock mode when the API key is missing or the model is unreachable.
 *
 * Spec reference:
 *   Section 4 Tool 1 (Probabilistic Output -- Haiku 4.5)
 *   Section 6 #8 (LLM Routing)
 *   Section 1 (Model Access Preflight, mock mode, Legal Disclaimer, Logging)
 */

import { NextRequest, NextResponse } from 'next/server';
import { DisclosureInput, DisclosureAI } from '@/lib/schemas/disclosure';
import { hasApiKey, getClient, MODELS } from '@/lib/ai/client';
import { runPreflight } from '@/lib/ai/preflight';
import { getMockDisclosureAI } from '@/lib/ai/mock';
import { LEGAL_DISCLAIMER } from '@/lib/constants';
import { withAiRateLimit } from '../middleware';

export async function POST(request: NextRequest) {
  const requestId = crypto.randomUUID();

  // Enforce rate limits (Section 9: 10 req/hr per IP, 30 req/day per user)
  const rateLimitResponse = withAiRateLimit(request);
  if (rateLimitResponse) return rateLimitResponse;

  try {
    const body = await request.json();

    // Validate input against the DisclosureInput schema
    const parsed = DisclosureInput.safeParse(body);
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
      const mockResult = await getMockDisclosureAI();
      return NextResponse.json({
        ...mockResult,
        mock: true,
        disclaimer: LEGAL_DISCLAIMER,
        requestId,
      });
    }

    // Call Haiku 4.5 for disclosure text generation
    const client = getClient();

    const systemPrompt =
      'You are an AI filmmaking ethics disclosure writer. ' +
      'Given the project details below, write a clear, professional disclosure statement ' +
      'that a filmmaker can include with their festival submission or distribution materials. ' +
      'The statement should cover: which departments used AI, what tools were used, ' +
      'whether usage was assistive or generative, human oversight details, and any ' +
      'relevant consent or compensation notes. Keep the tone transparent and constructive. ' +
      'Return ONLY a JSON object with a single key "disclosureText" containing the statement as a string. ' +
      'The disclosureText must be between 50 and 2000 characters.';

    const userMessage = JSON.stringify({
      projectTitle: input.projectTitle,
      aiUsageAreas: input.aiUsageAreas,
      distributionTargets: input.distributionTargets,
      unionStatus: input.unionStatus,
    });

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15_000);

    let response;
    try {
      response = await client.messages.create({
        model: MODELS.HAIKU,
        max_tokens: 1024,
        system: systemPrompt,
        messages: [{ role: 'user', content: userMessage }],
      }, { signal: controller.signal });
    } catch (abortErr) {
      clearTimeout(timeout);
      console.error(`[${requestId}] Haiku call timed out or aborted for disclosure route`);
      const mockResult = await getMockDisclosureAI();
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
      console.error(`[${requestId}] Haiku returned no text content for disclosure route`);
      const mockResult = await getMockDisclosureAI();
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
      console.error(`[${requestId}] Haiku returned invalid JSON for disclosure route`);
      const mockResult = await getMockDisclosureAI();
      return NextResponse.json({
        ...mockResult,
        mock: true,
        disclaimer: LEGAL_DISCLAIMER,
        requestId,
      });
    }

    // Validate against the DisclosureAI Zod schema
    const validated = DisclosureAI.safeParse(rawOutput);
    if (!validated.success) {
      console.error(
        `[${requestId}] Haiku output failed DisclosureAI schema validation`,
        validated.error.flatten()
      );
      const mockResult = await getMockDisclosureAI();
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
    console.error(`[${requestId}] Disclosure AI route error:`, error);
    // Fallback to mock on any unexpected error
    const mockResult = await getMockDisclosureAI();
    return NextResponse.json({
      ...mockResult,
      mock: true,
      disclaimer: LEGAL_DISCLAIMER,
      requestId,
    });
  }
}
