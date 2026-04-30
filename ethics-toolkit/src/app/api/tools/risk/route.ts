/**
 * POST /api/tools/risk
 *
 * Validates input with RiskScannerInput Zod schema, computes the
 * deterministic risk score (Steps 1-7), persists a ToolEvent, and
 * returns the result.
 *
 * Spec reference: Section 4 Tool 3
 */

import { NextRequest, NextResponse } from 'next/server';
import { RiskScannerInput } from '@/lib/schemas/risk-scanner';
import { computeRiskScore } from '@/lib/tools/risk-scanner';
import { getMockRiskRecommendations } from '@/lib/tools/risk-scanner-mock';
import { createServiceClient } from '@/lib/supabase/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Validate input
    const parseResult = RiskScannerInput.safeParse(body.input);
    if (!parseResult.success) {
      return NextResponse.json(
        { error: 'validation_error', details: parseResult.error.flatten() },
        { status: 400 }
      );
    }

    const { anonymousSessionId, eventId, workshopSessionId } = body;

    if (!anonymousSessionId || typeof anonymousSessionId !== 'string') {
      return NextResponse.json(
        { error: 'validation_error', details: 'anonymousSessionId is required' },
        { status: 400 }
      );
    }

    if (!eventId || typeof eventId !== 'string') {
      return NextResponse.json(
        { error: 'validation_error', details: 'eventId is required' },
        { status: 400 }
      );
    }

    // Compute deterministic score
    const deterministicPayload = computeRiskScore(parseResult.data);

    // Get mock AI recommendations (Phase 4 replaces with real Sonnet 4.6 call)
    let probabilisticPayload = null;
    try {
      probabilisticPayload = await getMockRiskRecommendations();
    } catch {
      // AI recommendations unavailable -- continue with deterministic only
    }

    // Persist ToolEvent
    const supabase = createServiceClient();
    const toolEvent = {
      event_id: eventId as string,
      schema_version: 1,
      workshop_session_id: (workshopSessionId as string) || null,
      anonymous_session_id: anonymousSessionId as string,
      user_id: null,
      tool_type: 'RISK' as const,
      deterministic_payload: deterministicPayload as unknown as Record<string, unknown>,
      probabilistic_payload: probabilisticPayload as unknown as Record<string, unknown> | null,
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { error: insertError } = await (supabase.from('tool_events') as any).insert(toolEvent);

    if (insertError) {
      // If it's a duplicate eventId, return the existing result silently
      if (insertError.code === '23505') {
        return NextResponse.json({
          deterministicPayload,
          probabilisticPayload,
          deduplicated: true,
        });
      }

      console.error('Failed to persist risk scanner ToolEvent:', {
        requestId: eventId,
        route: '/api/tools/risk',
        anonymousSessionId,
        error: insertError.message,
      });

      // Still return the computed result even if persistence fails
    }

    return NextResponse.json({
      deterministicPayload,
      probabilisticPayload,
    });
  } catch (error) {
    console.error('Risk scanner API error:', {
      route: '/api/tools/risk',
      error: error instanceof Error ? error.message : 'Unknown error',
    });

    return NextResponse.json(
      { error: 'internal_error', message: 'An unexpected error occurred' },
      { status: 500 }
    );
  }
}
