/**
 * Welcome email template.
 *
 * Subject: "Your Ethics Toolkit results are saved"
 * Sent immediately on user conversion (magic link auth).
 *
 * Body: "Here's what you created today: [list of tools used with links].
 * Your premium access is active for 14 days."
 */

const APP_URL = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';

export interface WelcomeEmailProps {
  userEmail: string;
  unsubscribeToken: string;
  toolsUsed?: string[];
}

export function welcomeSubject(): string {
  return 'Your Ethics Toolkit results are saved';
}

export function welcomeHtml({
  unsubscribeToken,
  toolsUsed = [],
}: WelcomeEmailProps): string {
  const resultsUrl = `${APP_URL}/results`;
  const unsubscribeUrl = `${APP_URL}/unsubscribe?token=${unsubscribeToken}`;

  const toolList =
    toolsUsed.length > 0
      ? `<ul style="margin:16px 0;padding-left:20px;">${toolsUsed
          .map(
            (tool) =>
              `<li style="margin-bottom:8px;"><a href="${resultsUrl}" style="color:#2563eb;text-decoration:underline;">${tool}</a></li>`
          )
          .join('')}</ul>`
      : `<p style="margin:16px 0;"><a href="${resultsUrl}" style="color:#2563eb;text-decoration:underline;">View your results</a></p>`;

  return `<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8" /><meta name="viewport" content="width=device-width,initial-scale=1" /></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;margin:0;padding:0;background-color:#f9fafb;">
  <div style="max-width:600px;margin:0 auto;padding:32px 24px;">
    <h1 style="font-size:24px;color:#111827;margin-bottom:16px;">Your Ethics Toolkit results are saved</h1>
    <p style="font-size:16px;color:#374151;line-height:1.6;">
      Here's what you created today:
    </p>
    ${toolList}
    <p style="font-size:16px;color:#374151;line-height:1.6;">
      Your premium access is active for 14 days. During this time you have full access to
      AI-generated disclosure language, detailed risk breakdowns, ethical analysis, and PDF exports.
    </p>
    <div style="margin:24px 0;">
      <a href="${resultsUrl}" style="display:inline-block;padding:12px 24px;background-color:#2563eb;color:#ffffff;text-decoration:none;border-radius:8px;font-size:16px;font-weight:600;">
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

export function welcomePlainText({
  unsubscribeToken,
  toolsUsed = [],
}: WelcomeEmailProps): string {
  const resultsUrl = `${APP_URL}/results`;
  const unsubscribeUrl = `${APP_URL}/unsubscribe?token=${unsubscribeToken}`;

  const toolListText =
    toolsUsed.length > 0
      ? toolsUsed.map((tool) => `  - ${tool}`).join('\n')
      : '  View your results';

  return `Your Ethics Toolkit results are saved

Here's what you created today:
${toolListText}

View your results: ${resultsUrl}

Your premium access is active for 14 days. During this time you have full access to AI-generated disclosure language, detailed risk breakdowns, ethical analysis, and PDF exports.

---
Guidance, not legal advice. Consult an entertainment attorney for legal counsel.

Unsubscribe: ${unsubscribeUrl}`;
}
