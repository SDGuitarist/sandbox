/**
 * POST /api/tools/disclosure
 *
 * Validate input with Zod, compute deterministic checklist + template,
 * persist ToolEvent, return deterministic output + optional mock AI.
 *
 * Spec reference: Section 4 Tool 1
 */

import { NextRequest, NextResponse } from 'next/server';
import { DisclosureInput } from '@/lib/schemas/disclosure';
import { generateDisclosure } from '@/lib/tools/disclosure';
import { getMockDisclosureAI } from '@/lib/tools/disclosure-mock';
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

  // Extract metadata from body (not part of Zod schema)
  const {
    eventId,
    anonymousSessionId,
    workshopSessionId,
    userId,
    ...inputData
  } = body as Record<string, unknown>;

  // Validate required metadata
  if (!eventId || typeof eventId !== 'string') {
    return NextResponse.json(
      { error: 'Missing or invalid eventId' },
      { status: 400 }
    );
  }
  if (!anonymousSessionId || typeof anonymousSessionId !== 'string') {
    return NextResponse.json(
      { error: 'Missing or invalid anonymousSessionId' },
      { status: 400 }
    );
  }

  // Validate input with Zod
  const parsed = DisclosureInput.safeParse(inputData);
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Validation failed', details: parsed.error.flatten() },
      { status: 400 }
    );
  }

  // Compute deterministic output
  const deterministicPayload = generateDisclosure(parsed.data);

  // Get mock AI response (Phase 2 -- will be replaced with real AI in Phase 4)
  let probabilisticPayload: { disclosureText: string } | null = null;
  try {
    probabilisticPayload = await getMockDisclosureAI();
  } catch {
    // AI unavailable -- deterministic output still returned
    probabilisticPayload = null;
  }

  // Persist ToolEvent to Supabase
  // Note: type assertion needed because Database['public']['Tables']['tool_events']['Insert']
  // resolves to never due to a known Supabase codegen issue with complex Omit types.
  const supabase = createServiceClient();
  const insertRow = {
    event_id: eventId as string,
    schema_version: 1,
    workshop_session_id: (workshopSessionId as string) || null,
    anonymous_session_id: anonymousSessionId as string,
    user_id: (userId as string) || null,
    tool_type: 'DISCLOSURE' as const,
    deterministic_payload: deterministicPayload as unknown as Record<string, unknown>,
    probabilistic_payload: probabilisticPayload as unknown as Record<string, unknown> | null,
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { error: insertError } = await supabase.from('tool_events').insert(insertRow as any);

  if (insertError) {
    // Log error but don't block the response -- user still gets their output
    console.error(
      'Failed to persist disclosure ToolEvent:',
      insertError.message,
      { requestId: eventId }
    );
  }

  return NextResponse.json({
    deterministic: deterministicPayload,
    probabilistic: probabilisticPayload,
  });
}
