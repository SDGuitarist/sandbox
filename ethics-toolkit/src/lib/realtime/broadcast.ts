/**
 * Client-side broadcast helpers for the 3 broadcast-first interactions.
 *
 * These interactions are NOT persisted on the server. Idempotency is handled
 * entirely by the facilitator client using an in-memory Set (see idempotency.ts).
 *
 * Broadcast-first interactions:
 *   1. poll.response
 *   2. word_cloud.submit
 *   3. confidence.submit
 */

import type { RealtimeChannel } from '@supabase/supabase-js';
import type {
  PollResponsePayload,
  WordCloudSubmitPayload,
  ConfidenceSubmitPayload,
} from './types';

// ---------------------------------------------------------------------------
// 1. Poll Response
// ---------------------------------------------------------------------------

/**
 * Broadcast a poll response to the workshop channel.
 *
 * @param channel - Subscribed Supabase Realtime channel.
 * @param params.eventId - Client-generated UUID for idempotency.
 * @param params.workshopSessionId - Active workshop session UUID.
 * @param params.anonymousSessionId - Attendee's anonymous session ID.
 * @param params.pollId - ID of the poll being responded to.
 * @param params.optionId - Selected option ID.
 */
export async function broadcastPollResponse(
  channel: RealtimeChannel,
  params: {
    eventId: string;
    workshopSessionId: string;
    anonymousSessionId: string;
    pollId: string;
    optionId: string;
  }
): Promise<void> {
  const payload: PollResponsePayload = {
    type: 'poll.response',
    eventId: params.eventId,
    workshopSessionId: params.workshopSessionId,
    anonymousSessionId: params.anonymousSessionId,
    pollId: params.pollId,
    optionId: params.optionId,
    createdAt: new Date().toISOString(),
  };

  await channel.send({
    type: 'broadcast',
    event: 'message',
    payload,
  });
}

// ---------------------------------------------------------------------------
// 2. Word Cloud Submission
// ---------------------------------------------------------------------------

/**
 * Broadcast a word cloud phrase to the workshop channel.
 *
 * @param channel - Subscribed Supabase Realtime channel.
 * @param params.eventId - Client-generated UUID.
 * @param params.workshopSessionId - Active workshop session UUID.
 * @param params.anonymousSessionId - Attendee's anonymous session ID.
 * @param params.promptId - ID of the word cloud prompt.
 * @param params.phrase - Submitted phrase (max 50 characters).
 */
export async function broadcastWordCloudSubmit(
  channel: RealtimeChannel,
  params: {
    eventId: string;
    workshopSessionId: string;
    anonymousSessionId: string;
    promptId: string;
    phrase: string;
  }
): Promise<void> {
  // Enforce max 50 chars as specified in the spec
  const truncatedPhrase = params.phrase.slice(0, 50);

  const payload: WordCloudSubmitPayload = {
    type: 'word_cloud.submit',
    eventId: params.eventId,
    workshopSessionId: params.workshopSessionId,
    anonymousSessionId: params.anonymousSessionId,
    promptId: params.promptId,
    phrase: truncatedPhrase,
    createdAt: new Date().toISOString(),
  };

  await channel.send({
    type: 'broadcast',
    event: 'message',
    payload,
  });
}

// ---------------------------------------------------------------------------
// 3. Confidence Slider
// ---------------------------------------------------------------------------

/**
 * Broadcast a confidence slider value to the workshop channel.
 *
 * @param channel - Subscribed Supabase Realtime channel.
 * @param params.eventId - Client-generated UUID.
 * @param params.workshopSessionId - Active workshop session UUID.
 * @param params.anonymousSessionId - Attendee's anonymous session ID.
 * @param params.phase - Whether this is a "before" or "after" measurement.
 * @param params.value - Integer 1-10.
 */
export async function broadcastConfidenceSubmit(
  channel: RealtimeChannel,
  params: {
    eventId: string;
    workshopSessionId: string;
    anonymousSessionId: string;
    phase: 'before' | 'after';
    value: number;
  }
): Promise<void> {
  // Clamp value to 1-10 integer range as specified in the spec
  const clampedValue = Math.max(1, Math.min(10, Math.round(params.value)));

  const payload: ConfidenceSubmitPayload = {
    type: 'confidence.submit',
    eventId: params.eventId,
    workshopSessionId: params.workshopSessionId,
    anonymousSessionId: params.anonymousSessionId,
    phase: params.phase,
    value: clampedValue,
    createdAt: new Date().toISOString(),
  };

  await channel.send({
    type: 'broadcast',
    event: 'message',
    payload,
  });
}
