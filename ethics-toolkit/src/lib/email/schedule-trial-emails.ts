import { createServiceClient } from '@/lib/supabase/server';
import crypto from 'crypto';

/**
 * Schedule trial lifecycle emails on user conversion.
 *
 * On magic link auth conversion:
 * 1. Generate a new UUID and set profiles.current_trial_id
 * 2. Set profiles.trial_started_at = now()
 * 3. Set profiles.trial_ends_at = now() + 14 days
 * 4. Create 3 email_jobs rows with idempotency keys: {userId}:{emailType}:{trialId}
 *
 * Email schedule:
 * - Welcome: immediately (scheduled_for = now)
 * - Day 12 Warning: trial_ends_at - 2 days
 * - Day 14 Downgrade: trial_ends_at
 */
export async function scheduleTrialEmails(userId: string): Promise<{
  success: boolean;
  trialId: string | null;
  error?: string;
}> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const supabase = createServiceClient() as any;

  // Generate a new trial ID
  const trialId = crypto.randomUUID();

  const now = new Date();
  const trialEndsAt = new Date(now.getTime() + 14 * 24 * 60 * 60 * 1000); // 14 days from now
  const day12 = new Date(trialEndsAt.getTime() - 2 * 24 * 60 * 60 * 1000); // trial_ends_at - 2 days

  // Update profile with trial info
  const { error: profileError } = await supabase
    .from('profiles')
    .update({
      current_trial_id: trialId,
      trial_started_at: now.toISOString(),
      trial_ends_at: trialEndsAt.toISOString(),
      entitlement_status: 'trial',
      updated_at: now.toISOString(),
    })
    .eq('user_id', userId);

  if (profileError) {
    console.error('[schedule-trial-emails] Failed to update profile:', profileError.message);
    return { success: false, trialId: null, error: profileError.message };
  }

  // Create 3 email_jobs rows with idempotency keys
  const emailJobs = [
    {
      user_id: userId,
      email_type: 'welcome' as const,
      trial_id: trialId,
      scheduled_for: now.toISOString(),
      status: 'pending' as const,
      idempotency_key: `${userId}:welcome:${trialId}`,
    },
    {
      user_id: userId,
      email_type: 'day12_warning' as const,
      trial_id: trialId,
      scheduled_for: day12.toISOString(),
      status: 'pending' as const,
      idempotency_key: `${userId}:day12_warning:${trialId}`,
    },
    {
      user_id: userId,
      email_type: 'day14_downgrade' as const,
      trial_id: trialId,
      scheduled_for: trialEndsAt.toISOString(),
      status: 'pending' as const,
      idempotency_key: `${userId}:day14_downgrade:${trialId}`,
    },
  ];

  const { error: jobsError } = await supabase
    .from('email_jobs')
    .insert(emailJobs);

  if (jobsError) {
    // If it's a unique constraint violation, the jobs already exist (idempotent).
    if (jobsError.code === '23505') {
      console.log('[schedule-trial-emails] Email jobs already exist for this trial (idempotent).');
      return { success: true, trialId };
    }

    console.error('[schedule-trial-emails] Failed to create email jobs:', jobsError.message);
    return { success: false, trialId, error: jobsError.message };
  }

  return { success: true, trialId };
}
