/**
 * Day 14 downgrade email template.
 *
 * Subject: "Your premium trial has ended"
 * Sent when trial_ends_at is reached.
 *
 * Body: "Your trial has ended. You still have access to [free features].
 * Upgrade anytime to restore [premium features]. Subscribe for $15/mo."
 */

const APP_URL = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';

export interface Day14DowngradeEmailProps {
  userEmail: string;
  unsubscribeToken: string;
}

export function day14DowngradeSubject(): string {
  return 'Your premium trial has ended';
}

export function day14DowngradeHtml({
  unsubscribeToken,
}: Day14DowngradeEmailProps): string {
  const resultsUrl = `${APP_URL}/results`;
  const checkoutUrl = `${APP_URL}/api/payments/checkout`;
  const unsubscribeUrl = `${APP_URL}/unsubscribe?token=${unsubscribeToken}`;

  return `<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8" /><meta name="viewport" content="width=device-width,initial-scale=1" /></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;margin:0;padding:0;background-color:#f9fafb;">
  <div style="max-width:600px;margin:0 auto;padding:32px 24px;">
    <h1 style="font-size:24px;color:#111827;margin-bottom:16px;">Your premium trial has ended</h1>
    <p style="font-size:16px;color:#374151;line-height:1.6;">
      Your 14-day premium trial has ended. Thank you for trying out the full Ethics Toolkit.
    </p>
    <p style="font-size:16px;color:#374151;line-height:1.6;">
      You still have access to:
    </p>
    <ul style="margin:16px 0;padding-left:20px;color:#374151;">
      <li style="margin-bottom:8px;">AI Disclosure Generator checklists and templates</li>
      <li style="margin-bottom:8px;">Festival Policy Lookup (always free)</li>
      <li style="margin-bottom:8px;">Risk Scanner tier and department flags</li>
      <li style="margin-bottom:8px;">Provenance Chain Builder (1 project, view only)</li>
      <li style="margin-bottom:8px;">Budget Calculator cost comparisons and displacement risk</li>
    </ul>
    <p style="font-size:16px;color:#374151;line-height:1.6;">
      Upgrade anytime to restore:
    </p>
    <ul style="margin:16px 0;padding-left:20px;color:#374151;">
      <li style="margin-bottom:8px;">AI-generated disclosure language</li>
      <li style="margin-bottom:8px;">Full risk dimension breakdowns and AI recommendations</li>
      <li style="margin-bottom:8px;">AI ethical budget analysis</li>
      <li style="margin-bottom:8px;">Unlimited projects and PDF exports</li>
    </ul>
    <p style="font-size:16px;color:#374151;line-height:1.6;">
      Subscribe for <strong>$15/mo</strong>.
    </p>
    <div style="margin:24px 0;">
      <a href="${checkoutUrl}" style="display:inline-block;padding:12px 24px;background-color:#2563eb;color:#ffffff;text-decoration:none;border-radius:8px;font-size:16px;font-weight:600;">
        Subscribe now
      </a>
    </div>
    <div style="margin:16px 0;">
      <a href="${resultsUrl}" style="color:#2563eb;text-decoration:underline;font-size:14px;">
        View your results
      </a>
    </div>
    <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;" />
    <p style="font-size:12px;color:#9ca3af;line-height:1.5;">
      Guidance, not legal advice. Consult an entertainment attorney for legal counsel.
    </p>
    <p style="font-size:12px;color:#9ca3af;">
      <a href="${unsubscribeUrl}" style="color:#9ca3af;text-decoration:underline;">Unsubscribe</a>
    </p>
  </div>
</body>
</html>`;
}

export function day14DowngradePlainText({
  unsubscribeToken,
}: Day14DowngradeEmailProps): string {
  const resultsUrl = `${APP_URL}/results`;
  const checkoutUrl = `${APP_URL}/api/payments/checkout`;
  const unsubscribeUrl = `${APP_URL}/unsubscribe?token=${unsubscribeToken}`;

  return `Your premium trial has ended

Your 14-day premium trial has ended. Thank you for trying out the full Ethics Toolkit.

You still have access to:
  - AI Disclosure Generator checklists and templates
  - Festival Policy Lookup (always free)
  - Risk Scanner tier and department flags
  - Provenance Chain Builder (1 project, view only)
  - Budget Calculator cost comparisons and displacement risk

Upgrade anytime to restore:
  - AI-generated disclosure language
  - Full risk dimension breakdowns and AI recommendations
  - AI ethical budget analysis
  - Unlimited projects and PDF exports

Subscribe for $15/mo: ${checkoutUrl}

View your results: ${resultsUrl}

---
Guidance, not legal advice. Consult an entertainment attorney for legal counsel.

Unsubscribe: ${unsubscribeUrl}`;
}
