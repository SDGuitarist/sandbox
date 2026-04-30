/**
 * Day 12 warning email template.
 *
 * Subject: "Your premium trial ends in 2 days"
 * Sent 2 days before trial_ends_at.
 *
 * Body: "Your trial ends on {date}. Here's what you've used: [tool usage summary].
 * After your trial, you'll keep your data but lose [premium features].
 * Subscribe for $15/mo to keep full access."
 */

const APP_URL = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';

export interface Day12WarningEmailProps {
  userEmail: string;
  unsubscribeToken: string;
  trialEndsAt: string; // ISO 8601 date string
  toolsUsed?: string[];
}

export function day12WarningSubject(): string {
  return 'Your premium trial ends in 2 days';
}

export function day12WarningHtml({
  unsubscribeToken,
  trialEndsAt,
  toolsUsed = [],
}: Day12WarningEmailProps): string {
  const resultsUrl = `${APP_URL}/results`;
  const checkoutUrl = `${APP_URL}/api/payments/checkout`;
  const unsubscribeUrl = `${APP_URL}/unsubscribe?token=${unsubscribeToken}`;
  const endDate = new Date(trialEndsAt).toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });

  const toolList =
    toolsUsed.length > 0
      ? `<ul style="margin:16px 0;padding-left:20px;">${toolsUsed
          .map(
            (tool) =>
              `<li style="margin-bottom:8px;">${tool}</li>`
          )
          .join('')}</ul>`
      : '';

  return `<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8" /><meta name="viewport" content="width=device-width,initial-scale=1" /></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;margin:0;padding:0;background-color:#f9fafb;">
  <div style="max-width:600px;margin:0 auto;padding:32px 24px;">
    <h1 style="font-size:24px;color:#111827;margin-bottom:16px;">Your premium trial ends in 2 days</h1>
    <p style="font-size:16px;color:#374151;line-height:1.6;">
      Your trial ends on <strong>${endDate}</strong>.
    </p>
    ${toolsUsed.length > 0 ? `<p style="font-size:16px;color:#374151;line-height:1.6;">Here's what you've used:</p>${toolList}` : ''}
    <p style="font-size:16px;color:#374151;line-height:1.6;">
      After your trial, you'll keep your data but lose access to:
    </p>
    <ul style="margin:16px 0;padding-left:20px;color:#374151;">
      <li style="margin-bottom:8px;">AI-generated disclosure language</li>
      <li style="margin-bottom:8px;">Detailed risk dimension breakdowns and AI recommendations</li>
      <li style="margin-bottom:8px;">AI ethical budget analysis</li>
      <li style="margin-bottom:8px;">PDF provenance chain exports</li>
    </ul>
    <p style="font-size:16px;color:#374151;line-height:1.6;">
      Subscribe for <strong>$15/mo</strong> to keep full access.
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

export function day12WarningPlainText({
  unsubscribeToken,
  trialEndsAt,
  toolsUsed = [],
}: Day12WarningEmailProps): string {
  const resultsUrl = `${APP_URL}/results`;
  const checkoutUrl = `${APP_URL}/api/payments/checkout`;
  const unsubscribeUrl = `${APP_URL}/unsubscribe?token=${unsubscribeToken}`;
  const endDate = new Date(trialEndsAt).toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });

  const toolListText =
    toolsUsed.length > 0
      ? `\nHere's what you've used:\n${toolsUsed.map((t) => `  - ${t}`).join('\n')}\n`
      : '';

  return `Your premium trial ends in 2 days

Your trial ends on ${endDate}.
${toolListText}
After your trial, you'll keep your data but lose access to:
  - AI-generated disclosure language
  - Detailed risk dimension breakdowns and AI recommendations
  - AI ethical budget analysis
  - PDF provenance chain exports

Subscribe for $15/mo to keep full access: ${checkoutUrl}

View your results: ${resultsUrl}

---
Guidance, not legal advice. Consult an entertainment attorney for legal counsel.

Unsubscribe: ${unsubscribeUrl}`;
}
