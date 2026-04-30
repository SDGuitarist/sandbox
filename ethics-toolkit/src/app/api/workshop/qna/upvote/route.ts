/**
 * POST /api/workshop/qna/upvote
 *
 * Authoritative-state interaction: persists an upvote to qna_votes with a
 * UNIQUE constraint on (question_id, anonymous_session_id), increments
 * upvote_count on qna_questions, checks processed_events for idempotency,
 * and broadcasts the updated count.
 *
 * Duplicate upvote (same user + same question) returns silently -- no error.
 *
 * Request body (matches QnaUpvotePayload from types.ts):
 *   {
 *     eventId: string,
 *     workshopSessionId: string,
 *     anonymousSessionId: string,
 *     questionId: string
 *   }
 *
 * Response:
 *   200 { success: true, upvoteCount: number }
 *   200 { success: true, duplicate: true }  -- duplicate upvote, returned silently
 *   400 Validation error
 *   500 Internal server error
 */

import { NextRequest, NextResponse } from 'next/server';
import { createServiceClient } from '@/lib/supabase/server';
import type { QnaUpvoteBroadcast } from '@/lib/realtime/types';

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

  const { eventId, workshopSessionId, anonymousSessionId, questionId } = body as {
    eventId?: string;
    workshopSessionId?: string;
    anonymousSessionId?: string;
    questionId?: string;
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
  if (!questionId || typeof questionId !== 'string') {
    return NextResponse.json({ error: 'questionId is required.' }, { status: 400 });
  }

  const supabase = createServiceClient();

  // Idempotency check: has this exact eventId already been processed?
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Supabase v2.49 Database generic resolves to never
  const { data: existingEvent } = await (supabase
    .from('processed_events') as any)
    .select('event_id')
    .eq('event_id', eventId)
    .single();

  if (existingEvent) {
    // Duplicate eventId -- return silently
    return NextResponse.json({ success: true, duplicate: true });
  }

  // Try to insert the vote. The UNIQUE(question_id, anonymous_session_id)
  // constraint enforces one vote per user per question at the DB level.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { error: voteError } = await (supabase
    .from('qna_votes') as any)
    .insert({
      event_id: eventId,
      question_id: questionId,
      anonymous_session_id: anonymousSessionId,
    });

  if (voteError) {
    // Unique constraint violation = duplicate upvote (same user, same question)
    // Return silently as specified in the spec
    if ((voteError as { code?: string }).code === '23505') {
      return NextResponse.json({ success: true, duplicate: true });
    }

    console.error('Failed to insert Q&A vote:', {
      route: '/api/workshop/qna/upvote',
      error: (voteError as { message?: string }).message,
      anonymousSessionId,
      questionId,
    });

    return NextResponse.json(
      { error: 'Failed to persist upvote.' },
      { status: 500 }
    );
  }

  // Increment upvote_count on the question.
  // Supabase JS v2 doesn't have a built-in atomic increment, so we
  // fetch + update. For this low-volume workshop scenario (< 30 concurrent
  // users), this is acceptable.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: questionRow } = await (supabase
    .from('qna_questions') as any)
    .select('upvote_count')
    .eq('id', questionId)
    .single();

  const currentCount = (questionRow as { upvote_count: number } | null)?.upvote_count ?? 0;
  const newCount = currentCount + 1;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  await (supabase
    .from('qna_questions') as any)
    .update({ upvote_count: newCount })
    .eq('id', questionId);

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
      route: '/api/workshop/qna/upvote',
      error: (processedError as { message?: string }).message,
      eventId,
    });
  }

  // Broadcast the updated upvote count to the workshop channel
  const broadcastPayload: QnaUpvoteBroadcast = {
    type: 'qna.upvote',
    eventId,
    workshopSessionId,
    anonymousSessionId,
    questionId,
    upvoteCount: newCount,
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

  return NextResponse.json({ success: true, upvoteCount: newCount });
}
