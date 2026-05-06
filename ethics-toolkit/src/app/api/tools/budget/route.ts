/**
 * POST /api/tools/budget
 *
 * Validates input with Zod, looks up rate data, computes delta,
 * persists a ToolEvent, and returns deterministic output + optional mock AI.
 *
 * Request body: { input: BudgetInput, eventId: string, anonymousSessionId: string, workshopSessionId?: string }
 *
 * Spec reference: Section 4 Tool 5
 */

import { NextRequest, NextResponse } from 'next/server';
import { BudgetInput } from '@/lib/schemas/budget';
import { computeBudget } from '@/lib/tools/budget';
import { getMockBudgetAI } from '@/lib/tools/budget-mock';
import { createServiceClient } from '@/lib/supabase/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Validate input (nested under body.input)
    const parseResult = BudgetInput.safeParse(body.input);
    if (!parseResult.success) {
      return NextResponse.json(
        { error: 'validation_error', details: parseResult.error.flatten() },
        { status: 400 }
      );
    }

    const { anonymousSessionId, eventId, workshopSessionId } = body;

    if (!eventId || typeof eventId !== 'string') {
      return NextResponse.json(
        { error: 'validation_error', details: 'eventId is required' },
        { status: 400 }
      );
    }
    if (!anonymousSessionId || typeof anonymousSessionId !== 'string') {
      return NextResponse.json(
        { error: 'validation_error', details: 'anonymousSessionId is required' },
        { status: 400 }
      );
    }

    // Deterministic lookup
    let deterministicPayload;
    try {
      deterministicPayload = computeBudget(parseResult.data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Rate data unavailable.';
      return NextResponse.json({ error: message }, { status: 422 });
    }

    // Mock AI ethical analysis (Phase 2 uses mock; Phase 4 replaces with real API)
    let probabilisticPayload: { ethicalAnalysis: string } | null = null;
    try {
      probabilisticPayload = await getMockBudgetAI(deterministicPayload);
    } catch {
      probabilisticPayload = null;
    }

    // Persist ToolEvent
    const supabase = createServiceClient();
    const toolEvent = {
      event_id: eventId as string,
      schema_version: 1,
      workshop_session_id: (workshopSessionId as string) || null,
      anonymous_session_id: anonymousSessionId as string,
      user_id: null,
      tool_type: 'BUDGET' as const,
      deterministic_payload: deterministicPayload as unknown as Record<string, unknown>,
      probabilistic_payload: probabilisticPayload as unknown as Record<string, unknown> | null,
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { error: insertError } = await supabase.from('tool_events').insert(toolEvent as any);

    if (insertError) {
      if (insertError.code === '23505') {
        return NextResponse.json({
          deterministicPayload,
          probabilisticPayload,
          deduplicated: true,
        });
      }
      console.error('[budget] Failed to persist ToolEvent:', insertError.message, { eventId, anonymousSessionId });
    }

    return NextResponse.json({
      deterministicPayload,
      probabilisticPayload,
    });
  } catch (error) {
    console.error('Budget API error:', {
      route: '/api/tools/budget',
      error: error instanceof Error ? error.message : 'Unknown error',
    });

    return NextResponse.json(
      { error: 'internal_error', message: 'An unexpected error occurred' },
      { status: 500 }
    );
  }
}
