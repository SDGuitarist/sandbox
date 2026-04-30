import { createServiceClient } from '@/lib/supabase/server';
import { getResendClient } from '@/lib/email/resend-client';
import {
  welcomeSubject,
  welcomeHtml,
  welcomePlainText,
} from '@/lib/email/templates/welcome';
import {
  day12WarningSubject,
  day12WarningHtml,
  day12WarningPlainText,
} from '@/lib/email/templates/day12-warning';
import {
  day14DowngradeSubject,
  day14DowngradeHtml,
  day14DowngradePlainText,
} from '@/lib/email/templates/day14-downgrade';
import type { EmailType } from '@/types/database';

const FROM_ADDRESS = 'Ethics Toolkit <noreply@ethicstoolkit.app>';

/**
 * Generates a simple unsubscribe token from userId.
 * In production, this would be a signed JWT or HMAC token.
 * For v1, we use a base64url-encoded userId as the token.
 */
function generateUnsubscribeToken(userId: string): string {
  return Buffer.from(userId).toString('base64url');
}

/**
 * Helper to pause execution for a given number of milliseconds.
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

interface SendEmailOptions {
  userId: string;
  userEmail: string;
  emailType: EmailType;
  trialEndsAt?: string | null;
  toolsUsed?: string[];
}

interface SendResult {
  success: boolean;
  status: 'sent' | 'skipped' | 'failed';
  reason?: string;
}

/**
 * Send an email for a given user and email type.
 *
 * - Checks email_opt_out first. If true, returns status='skipped'.
 * - Retries once on 5xx after 60 seconds.
 * - Returns status='failed' if still failing after retry.
 */
export async function sendEmail(options: SendEmailOptions): Promise<SendResult> {
  const { userId, userEmail, emailType, trialEndsAt, toolsUsed } = options;

  // Check email_opt_out
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const supabase = createServiceClient() as any;
  const { data: profile } = await supabase
    .from('profiles')
    .select('email_opt_out')
    .eq('user_id', userId)
    .single() as { data: { email_opt_out: boolean } | null };

  if (profile?.email_opt_out) {
    return { success: true, status: 'skipped', reason: 'User opted out of emails' };
  }

  // Get Resend client
  const resend = getResendClient();
  if (!resend) {
    return { success: false, status: 'failed', reason: 'Resend API key not configured' };
  }

  // Build email content based on type
  const unsubscribeToken = generateUnsubscribeToken(userId);
  let subject: string;
  let html: string;
  let text: string;

  switch (emailType) {
    case 'welcome': {
      subject = welcomeSubject();
      html = welcomeHtml({ userEmail, unsubscribeToken, toolsUsed });
      text = welcomePlainText({ userEmail, unsubscribeToken, toolsUsed });
      break;
    }
    case 'day12_warning': {
      subject = day12WarningSubject();
      html = day12WarningHtml({
        userEmail,
        unsubscribeToken,
        trialEndsAt: trialEndsAt || '',
        toolsUsed,
      });
      text = day12WarningPlainText({
        userEmail,
        unsubscribeToken,
        trialEndsAt: trialEndsAt || '',
        toolsUsed,
      });
      break;
    }
    case 'day14_downgrade': {
      subject = day14DowngradeSubject();
      html = day14DowngradeHtml({ userEmail, unsubscribeToken });
      text = day14DowngradePlainText({ userEmail, unsubscribeToken });
      break;
    }
    default: {
      return { success: false, status: 'failed', reason: `Unknown email type: ${emailType}` };
    }
  }

  // Attempt to send with one retry on 5xx
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const { error } = await resend.emails.send({
        from: FROM_ADDRESS,
        to: userEmail,
        subject,
        html,
        text,
      });

      if (!error) {
        return { success: true, status: 'sent' };
      }

      // Retry on first failure (treat any Resend error as potentially transient)
      if (attempt === 0) {
        console.error(
          `[email] Attempt ${attempt + 1} failed for ${emailType} to ${userEmail}:`,
          error.message
        );
        await sleep(60_000); // Wait 60 seconds before retry
        continue;
      }

      // Second attempt also failed
      console.error(
        `[email] Attempt ${attempt + 1} failed for ${emailType} to ${userEmail}:`,
        error.message
      );
      return {
        success: false,
        status: 'failed',
        reason: `Resend error after retry: ${error.message}`,
      };
    } catch (err) {
      if (attempt === 0) {
        console.error(
          `[email] Attempt ${attempt + 1} threw for ${emailType} to ${userEmail}:`,
          err
        );
        await sleep(60_000);
        continue;
      }

      console.error(
        `[email] Attempt ${attempt + 1} threw for ${emailType} to ${userEmail}:`,
        err
      );
      return {
        success: false,
        status: 'failed',
        reason: `Exception after retry: ${err instanceof Error ? err.message : String(err)}`,
      };
    }
  }

  // Should not reach here, but just in case
  return { success: false, status: 'failed', reason: 'Unexpected send loop exit' };
}
