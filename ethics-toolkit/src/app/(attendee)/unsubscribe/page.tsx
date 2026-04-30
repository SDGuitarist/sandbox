import { createServiceClient } from '@/lib/supabase/server';

/**
 * /unsubscribe?token=<base64url-encoded-userId>
 *
 * Server-rendered unsubscribe page. Validates the token (base64url-encoded
 * userId), sets email_opt_out=true on the user's profile, and displays
 * the result. No extra API route needed -- runs server-side.
 */

interface UnsubscribePageProps {
  searchParams: Promise<{ token?: string }>;
}

export default async function UnsubscribePage({ searchParams }: UnsubscribePageProps) {
  const params = await searchParams;
  const token = params.token;

  let status: 'success' | 'error' | 'invalid' = 'invalid';
  let message = 'Invalid unsubscribe link. No token provided.';

  if (token) {
    // Decode the token to get the userId
    let userId: string | null = null;
    try {
      // base64url decode
      const base64 = token.replace(/-/g, '+').replace(/_/g, '/');
      userId = Buffer.from(base64, 'base64').toString('utf-8');
    } catch {
      status = 'invalid';
      message = 'Invalid unsubscribe token.';
    }

    if (userId) {
      // Validate it looks like a UUID
      const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
      if (!uuidRegex.test(userId)) {
        status = 'invalid';
        message = 'Invalid unsubscribe token format.';
      } else {
        // Set email_opt_out = true
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const supabase = createServiceClient() as any;
        const { error } = await supabase
          .from('profiles')
          .update({
            email_opt_out: true,
            updated_at: new Date().toISOString(),
          })
          .eq('user_id', userId);

        if (error) {
          status = 'error';
          message = 'Failed to process your unsubscribe request. Please try again later.';
        } else {
          status = 'success';
          message = 'You have been unsubscribed from Ethics Toolkit emails.';
        }
      }
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6 py-12">
      <div className="mx-auto max-w-md text-center">
        <div className="mb-6 flex justify-center">
          {status === 'success' && (
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
              <svg
                className="h-8 w-8 text-green-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
          )}
          {(status === 'error' || status === 'invalid') && (
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
              <svg
                className="h-8 w-8 text-red-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
          )}
        </div>

        <h1 className="mb-4 text-2xl font-bold text-gray-900">
          {status === 'success' && 'Unsubscribed'}
          {status === 'error' && 'Something went wrong'}
          {status === 'invalid' && 'Invalid link'}
        </h1>

        <p className="mb-8 text-lg text-gray-600">{message}</p>

        {status === 'success' && (
          <p className="mb-8 text-base text-gray-500">
            You will no longer receive lifecycle emails from Ethics Toolkit.
            You can still use the app and your data is safe.
          </p>
        )}

        <a
          href="/"
          className="inline-block min-h-[44px] min-w-[44px] rounded-lg bg-blue-600 px-6 py-3 text-base font-semibold text-white transition-colors hover:bg-blue-700"
        >
          Back to Ethics Toolkit
        </a>
      </div>

      <footer className="mt-12 text-center text-sm text-gray-400">
        Guidance, not legal advice. Consult an entertainment attorney for legal
        counsel.
      </footer>
    </main>
  );
}
