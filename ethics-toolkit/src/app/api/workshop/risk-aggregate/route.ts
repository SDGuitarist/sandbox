/**
 * POST /api/workshop/risk-aggregate
 *
 * Authoritative-state interaction: persists a risk scanner aggregate score
 * to workshop_risk_scores, checks processed_events for idempotency, and
 * broadcasts the result to the workshop channel.
 *
 * Request body (matches RiskAggregatePayload from types.ts):
 *   {
 *     eventId: string,
 *     workshopSessionId: string,
 *     anonymousSessionId: string,
 *     riskTier: 'low' | 'medium' | 'high' | 'critical',
 *     topRiskDepartments: string[]
 *   }
 *
 * Response:
 *   200 { success: true }                -- new event persisted and broadcast
 *   200 { success: true, duplicate: true } -- duplicate eventId, silently accepted
 *   400 Validation error
 *   500 Internal server error
 */

import { NextRequest, NextResponse } from 'next/server';
import { createServiceClient } from '@/lib/supabase/server';
import type { RiskAggregatePayload } from '@/lib/realtime/types';
import type { RiskTier } from '@/types/database';

const VALID_RISK_TIERS: readonly RiskTier[] = ['low', 'medium', 'high', 'critical'];

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

  // Validate required fields
  const { eventId, workshopSessionId, anonymousSessionId, riskTier, topRiskDepartments } = body as {
    eventId?: string;
    workshopSessionId?: string;
    anonymousSessionId?: string;
    riskTier?: string;
    topRiskDepartments?: string[];
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
  if (!riskTier || !VALID_RISK_TIERS.includes(riskTier as RiskTier)) {
    return NextResponse.json({ error: 'riskTier must be one of: low, medium, high, critical.' }, { status: 400 });
  }
  if (!Array.isArray(topRiskDepartments)) {
    return NextResponse.json({ error: 'topRiskDepartments must be an array of strings.' }, { status: 400 });
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
    // Duplicate -- return silently without error
    return NextResponse.json({ success: true, duplicate: true });
  }

  // Persist the risk score
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { error: insertError } = await (supabase
    .from('workshop_risk_scores') as any)
    .insert({
      event_id: eventId,
      workshop_session_id: workshopSessionId,
      anonymous_session_id: anonymousSessionId,
      risk_tier: riskTier,
      top_risk_departments: topRiskDepartments,
    });

  if (insertError) {
    // If it's a duplicate event_id on workshop_risk_scores, treat as idempotent
    if ((insertError as { code?: string }).code === '23505') {
      return NextResponse.json({ success: true, duplicate: true });
    }

    console.error('Failed to insert workshop risk score:', {
      route: '/api/workshop/risk-aggregate',
      error: (insertError as { message?: string }).message,
      anonymousSessionId,
    });

    return NextResponse.json(
      { error: 'Failed to persist risk aggregate.' },
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
    // Log but don't fail -- the risk score is already persisted
    console.error('Failed to record processed event:', {
      route: '/api/workshop/risk-aggregate',
      error: (processedError as { message?: string }).message,
      eventId,
    });
  }

  // Broadcast to the workshop channel via Supabase Realtime
  const broadcastPayload: RiskAggregatePayload = {
    type: 'risk.aggregate',
    eventId,
    workshopSessionId,
    anonymousSessionId,
    riskTier: riskTier as RiskTier,
    topRiskDepartments,
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

  return NextResponse.json({ success: true });
}
