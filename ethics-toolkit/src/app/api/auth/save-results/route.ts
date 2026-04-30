import { NextRequest, NextResponse } from 'next/server';
import { claimAnonymousSession } from '@/lib/auth/magic-link';
import { createServerClient } from '@/lib/supabase/server';

export async function POST(request: NextRequest) {
  const body = await request.json();
  const { anonymousSessionId } = body;

  if (!anonymousSessionId || typeof anonymousSessionId !== 'string') {
    return NextResponse.json(
      { error: 'anonymousSessionId is required' },
      { status: 400 }
    );
  }

  const supabase = createServerClient();

  const { data: { user }, error: authError } = await supabase.auth.getUser();

  if (authError || !user) {
    return NextResponse.json(
      { error: 'Authentication required' },
      { status: 401 }
    );
  }

  const { error } = await claimAnonymousSession(anonymousSessionId, user.id);

  if (error) {
    return NextResponse.json(
      { error },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true, userId: user.id });
}
