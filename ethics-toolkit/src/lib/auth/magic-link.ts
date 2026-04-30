import { createBrowserClient } from '@/lib/supabase/client';
import { createServerClient } from '@/lib/supabase/server';

export async function sendMagicLink(email: string): Promise<{ error: string | null }> {
  const supabase = createBrowserClient();

  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: {
      emailRedirectTo: `${window.location.origin}/api/auth/save-results`,
    },
  });

  if (error) {
    return { error: error.message };
  }

  return { error: null };
}

export async function claimAnonymousSession(
  anonymousSessionId: string,
  userId: string
): Promise<{ error: string | null }> {
  const supabase = createServerClient();

  const { error: sessionError } = await supabase
    .from('anonymous_sessions')
    .update({
      user_id: userId,
      claimed_at: new Date().toISOString(),
    })
    .eq('anonymous_session_id', anonymousSessionId)
    .is('user_id', null);

  if (sessionError) {
    return { error: sessionError.message };
  }

  const { error: eventsError } = await supabase
    .from('tool_events')
    .update({ user_id: userId })
    .eq('anonymous_session_id', anonymousSessionId)
    .is('user_id', null);

  if (eventsError) {
    return { error: eventsError.message };
  }

  return { error: null };
}
