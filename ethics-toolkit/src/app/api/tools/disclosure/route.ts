/**
 * POST /api/tools/disclosure
 *
 * Validate input with Zod, compute deterministic checklist + template,
 * persist ToolEvent, return deterministic output + optional mock AI.
 *
 * Request body: { input: DisclosureInput, eventId: string, anonymousSessionId: string, workshopSessionId?: string }
 *
 * Spec reference: Section 4 Tool 1
 */

import { NextRequest, NextResponse } from 'next/server';
import { DisclosureInput } from '@/lib/schemas/disclosure';
import { generateDisclosure } from '@/lib/tools/disclosure';
import { getMockDisclosureAI } from '@/lib/tools/disclosure-mock';
import { createServiceClient } from '@/lib/supabase/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Validate input (nested under body.input)
    const parseResult = DisclosureInput.safeParse(body.input);
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

    // Compute deterministic output
    const deterministicPayload = generateDisclosure(parseResult.data);

    // Get mock AI response (Phase 2 -- will be replaced with real AI in Phase 4)
    let probabilisticPayload: { disclosureText: string } | null = null;
    try {
      probabilisticPayload = await getMockDisclosureAI();
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
      tool_type: 'DISCLOSURE' as const,
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
      console.error('Failed to persist disclosure ToolEvent:', insertError.message, { requestId: eventId });
    }

    return NextResponse.json({
      deterministicPayload,
      probabilisticPayload,
    });
  } catch (error) {
    console.error('Disclosure API error:', {
      route: '/api/tools/disclosure',
      error: error instanceof Error ? error.message : 'Unknown error',
    });

    return NextResponse.json(
      { error: 'internal_error', message: 'An unexpected error occurred' },
      { status: 500 }
    );
  }
}
