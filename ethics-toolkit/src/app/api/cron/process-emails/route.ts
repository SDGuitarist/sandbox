import { NextRequest, NextResponse } from 'next/server';
import { createServiceClient } from '@/lib/supabase/server';
import { sendEmail } from '@/lib/email/send';
import type { EmailJob, EmailType } from '@/types/database';

/**
 * GET /api/cron/process-emails
 *
 * Vercel Cron job that runs daily.
 * Protected by CRON_SECRET (Vercel cron authorization header).
 *
 * Query: SELECT * FROM email_jobs WHERE status = 'pending' AND scheduled_for <= now()
 * For each job: check email_opt_out, send via Resend, update status.
 */
export async function GET(request: NextRequest) {
  // Validate CRON_SECRET header
  const authHeader = request.headers.get('authorization');
  const cronSecret = process.env.CRON_SECRET;

  if (!cronSecret) {
    console.error('[cron/process-emails] CRON_SECRET not configured');
    return NextResponse.json(
      { error: 'Cron job not configured.' },
      { status: 500 }
    );
  }

  if (authHeader !== `Bearer ${cronSecret}`) {
    return NextResponse.json(
      { error: 'Unauthorized.' },
      { status: 401 }
    );
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const supabase = createServiceClient() as any;

  // Query pending jobs where scheduled_for <= now()
  const { data: pendingJobs, error: queryError } = await supabase
    .from('email_jobs')
    .select('*')
    .eq('status', 'pending')
    .lte('scheduled_for', new Date().toISOString())
    .order('scheduled_for', { ascending: true }) as {
      data: EmailJob[] | null;
      error: Error | null;
    };

  if (queryError) {
    console.error('[cron/process-emails] Failed to query pending jobs:', queryError.message);
    return NextResponse.json(
      { error: 'Failed to query email jobs.' },
      { status: 500 }
    );
  }

  if (!pendingJobs || pendingJobs.length === 0) {
    return NextResponse.json({ processed: 0, results: [] });
  }

  const results: Array<{
    jobId: string;
    emailType: string;
    status: string;
    reason?: string;
  }> = [];

  for (const job of pendingJobs) {
    // Concurrency guard: atomically claim this job by setting status='processing'.
    // If another cron invocation already claimed it, the WHERE won't match.
    const { data: claimed } = await supabase
      .from('email_jobs')
      .update({ status: 'processing' })
      .eq('id', job.id)
      .eq('status', 'pending')
      .select('id')
      .single() as { data: { id: string } | null };

    if (!claimed) {
      // Another worker already claimed this job -- skip
      results.push({
        jobId: job.id,
        emailType: job.email_type,
        status: 'skipped',
        reason: 'Already claimed by another worker',
      });
      continue;
    }

    // Look up user email and trial info
    const { data: profile } = await supabase
      .from('profiles')
      .select('email, trial_ends_at, email_opt_out')
      .eq('user_id', job.user_id)
      .single() as {
        data: { email: string; trial_ends_at: string | null; email_opt_out: boolean } | null;
      };

    if (!profile) {
      // User no longer exists -- mark job as failed
      await supabase
        .from('email_jobs')
        .update({ status: 'failed' })
        .eq('id', job.id);

      results.push({
        jobId: job.id,
        emailType: job.email_type,
        status: 'failed',
        reason: 'Profile not found',
      });
      continue;
    }

    // Check email_opt_out -- set status='skipped' if opted out
    if (profile.email_opt_out) {
      await supabase
        .from('email_jobs')
        .update({ status: 'skipped' })
        .eq('id', job.id);

      results.push({
        jobId: job.id,
        emailType: job.email_type,
        status: 'skipped',
        reason: 'User opted out',
      });
      continue;
    }

    // Send the email
    const sendResult = await sendEmail({
      userId: job.user_id,
      userEmail: profile.email,
      emailType: job.email_type as EmailType,
      trialEndsAt: profile.trial_ends_at,
    });

    // Update job status
    const now = new Date().toISOString();
    await supabase
      .from('email_jobs')
      .update({
        status: sendResult.status,
        sent_at: sendResult.status === 'sent' ? now : null,
      })
      .eq('id', job.id);

    results.push({
      jobId: job.id,
      emailType: job.email_type,
      status: sendResult.status,
      reason: sendResult.reason,
    });
  }

  return NextResponse.json({
    processed: results.length,
    results,
  });
}
