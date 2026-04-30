import { Resend } from 'resend';

/**
 * Resend SDK client.
 *
 * Uses RESEND_API_KEY from environment. Returns null when the key is
 * missing (mock/dev mode -- callers should handle gracefully).
 */
let resendInstance: Resend | null = null;

export function getResendClient(): Resend | null {
  if (resendInstance) {
    return resendInstance;
  }

  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    return null;
  }

  resendInstance = new Resend(apiKey);
  return resendInstance;
}
