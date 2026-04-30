/**
 * POST /api/workshop/session
 *
 * Creates a new workshop session. Facilitator-only.
 *
 * Request body:
 *   { sessionCode: string, facilitatorId?: string }
 *
 * Response:
 *   201 { id, sessionCode, status, startedAt }
 *   401 Unauthorized (not a facilitator)
 *   400 Missing sessionCode
 *   409 Duplicate sessionCode
 *   500 Internal server error
 */

import { NextRequest, NextResponse } from 'next/server';
import { createServiceClient } from '@/lib/supabase/server';
import { verifyFacilitatorSession } from '@/lib/auth/facilitator';
import type { WorkshopSession } from '@/types/database';

export async function POST(request: NextRequest) {
  // Facilitator-only gate
  const isFacilitator = await verifyFacilitatorSession();
  if (!isFacilitator) {
    return NextResponse.json(
      { error: 'Unauthorized. Facilitator access required.' },
      { status: 401 }
    );
  }

  let body: { sessionCode?: string; facilitatorId?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: 'Invalid JSON body.' },
      { status: 400 }
    );
  }

  const { sessionCode, facilitatorId } = body;

  if (!sessionCode || typeof sessionCode !== 'string' || sessionCode.trim().length === 0) {
    return NextResponse.json(
      { error: 'sessionCode is required and must be a non-empty string.' },
      { status: 400 }
    );
  }

  const supabase = createServiceClient();

  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Supabase v2.49 Database generic resolves table types to never; runtime types are correct
  const { data, error } = await (supabase
    .from('workshop_sessions') as any)
    .insert({
      session_code: sessionCode.trim(),
      facilitator_id: facilitatorId ?? null,
      ended_at: null,
      status: 'active',
    })
    .select('id, session_code, status, started_at')
    .single();

  if (error) {
    // Check for unique constraint violation on session_code
    if ((error as { code?: string }).code === '23505') {
      return NextResponse.json(
        { error: 'A session with this code already exists.' },
        { status: 409 }
      );
    }

    console.error('Failed to create workshop session:', {
      route: '/api/workshop/session',
      error: (error as { message?: string }).message,
    });

    return NextResponse.json(
      { error: 'Failed to create workshop session.' },
      { status: 500 }
    );
  }

  const row = data as WorkshopSession;

  return NextResponse.json(
    {
      id: row.id,
      sessionCode: row.session_code,
      status: row.status,
      startedAt: row.started_at,
    },
    { status: 201 }
  );
}
