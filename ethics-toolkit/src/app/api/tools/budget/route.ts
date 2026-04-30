/**
 * POST /api/tools/budget
 *
 * Validates input with Zod, looks up rate data, computes delta,
 * persists a ToolEvent, and returns deterministic output + optional mock AI.
 *
 * Spec reference: Section 4 Tool 5
 */

import { NextRequest, NextResponse } from 'next/server';
import { BudgetInput } from '@/lib/schemas/budget';
import { computeBudget } from '@/lib/tools/budget';
import { getMockBudgetAI } from '@/lib/tools/budget-mock';
import { createServiceClient } from '@/lib/supabase/server';

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: 'Invalid JSON body' },
      { status: 400 }
    );
  }

  // Validate input with Zod
  const parsed = BudgetInput.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Validation failed', details: parsed.error.flatten() },
      { status: 400 }
    );
  }

  const input = parsed.data;

  // Deterministic lookup
  let deterministicPayload;
  try {
    deterministicPayload = computeBudget(input);
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Rate data unavailable.';
    return NextResponse.json({ error: message }, { status: 422 });
  }

  // Mock AI ethical analysis (Phase 2 uses mock; Phase 4 replaces with real API)
  let probabilisticPayload: { ethicalAnalysis: string } | null = null;
  try {
    const ethicalAnalysis = await getMockBudgetAI(deterministicPayload);
    probabilisticPayload = { ethicalAnalysis };
  } catch {
    // LLM failure: show deterministic comparison with "Ethical analysis unavailable."
    probabilisticPayload = null;
  }

  // Extract anonymous session ID and optional fields from request body
  const anonymousSessionId =
    typeof (body as Record<string, unknown>).anonymousSessionId === 'string'
      ? (body as Record<string, unknown>).anonymousSessionId as string
      : null;
  const eventId =
    typeof (body as Record<string, unknown>).eventId === 'string'
      ? (body as Record<string, unknown>).eventId as string
      : crypto.randomUUID();
  const workshopSessionId =
    typeof (body as Record<string, unknown>).workshopSessionId === 'string'
      ? ((body as Record<string, unknown>).workshopSessionId as string)
      : null;

  // Persist ToolEvent if we have an anonymousSessionId
  if (anonymousSessionId) {
    const supabase = createServiceClient();
    const toolEvent = {
      event_id: eventId,
      schema_version: 1,
      workshop_session_id: workshopSessionId,
      anonymous_session_id: anonymousSessionId,
      user_id: null,
      tool_type: 'BUDGET' as const,
      deterministic_payload: deterministicPayload as unknown as Record<string, unknown>,
      probabilistic_payload: probabilisticPayload as unknown as Record<string, unknown> | null,
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { error: insertError } = await supabase.from('tool_events').insert(toolEvent as any);

    if (insertError) {
      // Log but don't fail the request -- the user still gets their result
      console.error(
        '[budget] Failed to persist ToolEvent:',
        insertError.message,
        { eventId, anonymousSessionId }
      );
    }
  }

  return NextResponse.json({
    eventId,
    deterministicPayload,
    probabilisticPayload,
  });
}
