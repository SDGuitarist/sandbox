/**
 * POST /api/tools/provenance
 *
 * Validates input with ProvenanceInput Zod schema, computes the
 * deterministic provenance summary, detects duplicates, persists
 * a ToolEvent, and returns the result.
 *
 * Spec reference: Section 4 Tool 4
 */

import { NextRequest, NextResponse } from 'next/server';
import { ProvenanceInput } from '@/lib/schemas/provenance';
import { computeProvenance, detectDuplicates } from '@/lib/tools/provenance';
import { createServiceClient } from '@/lib/supabase/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Validate input
    const parseResult = ProvenanceInput.safeParse(body.input);
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

    // Compute deterministic provenance summary
    const deterministicPayload = computeProvenance(parseResult.data);

    // Detect duplicates (warn, do not block)
    const duplicateWarnings = detectDuplicates(parseResult.data);

    // Persist ToolEvent (no probabilistic payload -- Tool 4 has no LLM)
    const supabase = createServiceClient();
    const toolEvent = {
      event_id: eventId as string,
      schema_version: 1,
      workshop_session_id: (workshopSessionId as string) || null,
      anonymous_session_id: anonymousSessionId as string,
      user_id: null,
      tool_type: 'PROVENANCE' as const,
      deterministic_payload: deterministicPayload as unknown as Record<string, unknown>,
      probabilistic_payload: null,
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { error: insertError } = await (supabase.from('tool_events') as any).insert(toolEvent);

    if (insertError) {
      // If it's a duplicate eventId, return the existing result silently
      if (insertError.code === '23505') {
        return NextResponse.json({
          deterministicPayload,
          duplicateWarnings,
          deduplicated: true,
        });
      }

      console.error('Failed to persist provenance ToolEvent:', {
        requestId: eventId,
        route: '/api/tools/provenance',
        anonymousSessionId,
        error: insertError.message,
      });

      // Still return the computed result even if persistence fails
    }

    return NextResponse.json({
      deterministicPayload,
      duplicateWarnings,
    });
  } catch (error) {
    console.error('Provenance API error:', {
      route: '/api/tools/provenance',
      error: error instanceof Error ? error.message : 'Unknown error',
    });

    return NextResponse.json(
      { error: 'internal_error', message: 'An unexpected error occurred' },
      { status: 500 }
    );
  }
}
