/**
 * POST /api/workshop/qna/question
 *
 * Authoritative-state interaction: persists a new Q&A question to
 * qna_questions, checks processed_events for idempotency, and broadcasts
 * back with the server-assigned questionId.
 *
 * Request body (matches QnaQuestionPayload from types.ts):
 *   {
 *     eventId: string,
 *     workshopSessionId: string,
 *     anonymousSessionId: string,
 *     questionText: string
 *   }
 *
 * Response:
 *   201 { success: true, questionId: string }
 *   200 { success: true, duplicate: true, questionId: string } -- duplicate eventId
 *   400 Validation error
 *   500 Internal server error
 */

import { NextRequest, NextResponse } from 'next/server';
import { createServiceClient } from '@/lib/supabase/server';
import type { QnaQuestionBroadcast } from '@/lib/realtime/types';

export async function POST(request: NextRequest) {
  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: 'Invalid JSON body.' },
      { status: 400 }
    );
  }

  const { eventId, workshopSessionId, anonymousSessionId, questionText } = body as {
    eventId?: string;
    workshopSessionId?: string;
    anonymousSessionId?: string;
    questionText?: string;
  };

  if (!eventId || typeof eventId !== 'string') {
    return NextResponse.json({ error: 'eventId is required.' }, { status: 400 });
  }
  if (!workshopSessionId || typeof workshopSessionId !== 'string') {
    return NextResponse.json({ error: 'workshopSessionId is required.' }, { status: 400 });
  }
  if (!anonymousSessionId || typeof anonymousSessionId !== 'string') {
    return NextResponse.json({ error: 'anonymousSessionId is required.' }, { status: 400 });
  }
  if (!questionText || typeof questionText !== 'string' || questionText.trim().length === 0) {
    return NextResponse.json({ error: 'questionText is required and must be non-empty.' }, { status: 400 });
  }

  const supabase = createServiceClient();

  // Idempotency check: has this eventId already been processed?
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Supabase v2.49 Database generic resolves to never
  const { data: existing } = await (supabase
    .from('processed_events') as any)
    .select('event_id')
    .eq('event_id', eventId)
    .single();

  if (existing) {
    // Duplicate -- look up the already-created question to return its ID
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { data: existingQuestion } = await (supabase
      .from('qna_questions') as any)
      .select('id')
      .eq('event_id', eventId)
      .single();

    return NextResponse.json({
      success: true,
      duplicate: true,
      questionId: (existingQuestion as { id: string } | null)?.id ?? null,
    });
  }

  // Persist the question
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: question, error: insertError } = await (supabase
    .from('qna_questions') as any)
    .insert({
      event_id: eventId,
      workshop_session_id: workshopSessionId,
      anonymous_session_id: anonymousSessionId,
      question_text: questionText.trim(),
      upvote_count: 0,
    })
    .select('id')
    .single();

  if (insertError) {
    // If it's a duplicate event_id, treat as idempotent
    if ((insertError as { code?: string }).code === '23505') {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const { data: existingQuestion } = await (supabase
        .from('qna_questions') as any)
        .select('id')
        .eq('event_id', eventId)
        .single();

      return NextResponse.json({
        success: true,
        duplicate: true,
        questionId: (existingQuestion as { id: string } | null)?.id ?? null,
      });
    }

    console.error('Failed to insert Q&A question:', {
      route: '/api/workshop/qna/question',
      error: (insertError as { message?: string }).message,
      anonymousSessionId,
    });

    return NextResponse.json(
      { error: 'Failed to persist question.' },
      { status: 500 }
    );
  }

  // Record in processed_events for idempotency
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { error: processedError } = await (supabase
    .from('processed_events') as any)
    .insert({
      event_id: eventId,
      anonymous_session_id: anonymousSessionId,
    });

  if (processedError && (processedError as { code?: string }).code !== '23505') {
    console.error('Failed to record processed event:', {
      route: '/api/workshop/qna/question',
      error: (processedError as { message?: string }).message,
      eventId,
    });
  }

  const questionId = (question as { id: string }).id;

  // Broadcast to the workshop channel with the assigned questionId
  const broadcastPayload: QnaQuestionBroadcast = {
    type: 'qna.question',
    eventId,
    workshopSessionId,
    anonymousSessionId,
    questionText: questionText.trim(),
    questionId,
    createdAt: new Date().toISOString(),
  };

  const channelName = `workshop:${workshopSessionId}`;
  const channel = supabase.channel(channelName);

  await channel.send({
    type: 'broadcast',
    event: 'message',
    payload: broadcastPayload,
  });

  await supabase.removeChannel(channel);

  return NextResponse.json(
    { success: true, questionId },
    { status: 201 }
  );
}
