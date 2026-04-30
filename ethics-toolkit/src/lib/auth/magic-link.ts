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

  // Use transactional RPC to claim session + tool_events atomically
  // Prevents partial claim data corruption (P0-2)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { error } = await (supabase as any).rpc('claim_anonymous_session', {
    p_anonymous_session_id: anonymousSessionId,
    p_user_id: userId,
  });

  if (error) {
    return { error: error.message };
  }

  return { error: null };
}
