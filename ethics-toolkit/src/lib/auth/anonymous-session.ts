import { createBrowserClient } from '@/lib/supabase/client';

const STORAGE_KEY = 'anonymousSessionId';

function generateUUID(): string {
  return crypto.randomUUID();
}

export function getAnonymousSessionId(): string {
  if (typeof window === 'undefined') {
    throw new Error('getAnonymousSessionId must be called in the browser');
  }

  const existing = localStorage.getItem(STORAGE_KEY);
  if (existing) {
    return existing;
  }

  const anonymousSessionId = generateUUID();
  localStorage.setItem(STORAGE_KEY, anonymousSessionId);
  return anonymousSessionId;
}

export async function ensureAnonymousSession(): Promise<string> {
  const anonymousSessionId = getAnonymousSessionId();
  const supabase = createBrowserClient();

  const { data } = await supabase
    .from('anonymous_sessions')
    .select('anonymous_session_id')
    .eq('anonymous_session_id', anonymousSessionId)
    .single();

  if (!data) {
    await supabase
      .from('anonymous_sessions')
      .insert({ anonymous_session_id: anonymousSessionId });
  }

  return anonymousSessionId;
}

export function clearAnonymousSessionId(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem(STORAGE_KEY);
  }
}
