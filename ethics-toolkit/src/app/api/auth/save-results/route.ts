import { NextRequest, NextResponse } from 'next/server';
import { claimAnonymousSession } from '@/lib/auth/magic-link';
import { createServerClient } from '@/lib/supabase/server';
import { scheduleTrialEmails } from '@/lib/email/schedule-trial-emails';

export async function POST(request: NextRequest) {
  const body = await request.json();
  const { anonymousSessionId } = body;

  if (!anonymousSessionId || typeof anonymousSessionId !== 'string') {
    return NextResponse.json(
      { error: 'anonymousSessionId is required' },
      { status: 400 }
    );
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const supabase = createServerClient() as any;

  const { data: { user }, error: authError } = await supabase.auth.getUser();

  if (authError || !user) {
    return NextResponse.json(
      { error: 'Authentication required' },
      { status: 401 }
    );
  }

  // P0-3 mitigation: verify the anonymousSessionId has tool_events
  // (prevents claiming arbitrary sessions by ID guessing)
  const { data: events } = await supabase
    .from('tool_events')
    .select('id')
    .eq('anonymous_session_id', anonymousSessionId)
    .is('user_id', null)
    .limit(1);

  const { data: existingSession } = await supabase
    .from('anonymous_sessions')
    .select('anonymous_session_id')
    .eq('anonymous_session_id', anonymousSessionId)
    .is('user_id', null)
    .single();

  if (!existingSession) {
    return NextResponse.json(
      { error: 'Session not found or already claimed' },
      { status: 404 }
    );
  }

  // Create profile (upsert -- idempotent if user already has one)
  const { error: profileError } = await supabase
    .from('profiles')
    .upsert(
      {
        user_id: user.id,
        email: user.email,
        entitlement_status: 'free',
      },
      { onConflict: 'user_id' }
    );

  if (profileError) {
    console.error('[save-results] Failed to create profile:', profileError.message);
    return NextResponse.json(
      { error: 'Failed to create profile' },
      { status: 500 }
    );
  }

  // Claim the anonymous session data into this user
  const { error } = await claimAnonymousSession(anonymousSessionId, user.id);

  if (error) {
    return NextResponse.json(
      { error },
      { status: 500 }
    );
  }

  // Schedule trial lifecycle emails
  const emailResult = await scheduleTrialEmails(user.id);
  if (!emailResult.success) {
    // Non-blocking -- session is claimed even if emails fail to schedule
    console.error('[save-results] Email scheduling failed:', emailResult.error);
  }

  return NextResponse.json({ success: true, userId: user.id });
}
