'use client';

/**
 * /payments/pending
 *
 * Return page shown after the user completes Square checkout.
 * Displays a "Payment processing" message. The facilitator manually
 * activates the entitlement via POST /api/admin/activate.
 */
export default function PaymentPendingPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6 py-12">
      <div className="mx-auto max-w-md text-center">
        <div className="mb-6 flex justify-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-yellow-100">
            <svg
              className="h-8 w-8 text-yellow-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </div>
        </div>

        <h1 className="mb-4 text-2xl font-bold text-gray-900">
          Payment processing
        </h1>

        <p className="mb-6 text-lg text-gray-600">
          Your access will be activated shortly. We are confirming your payment
          with Square. This usually takes just a few minutes.
        </p>

        <p className="mb-8 text-base text-gray-500">
          You will receive an email once your premium access is active. In the
          meantime, you can continue using the free features.
        </p>

        <a
          href="/results"
          className="inline-block min-h-[44px] min-w-[44px] rounded-lg bg-blue-600 px-6 py-3 text-base font-semibold text-white transition-colors hover:bg-blue-700"
        >
          Back to my results
        </a>
      </div>

      <footer className="mt-12 text-center text-sm text-gray-400">
        Guidance, not legal advice. Consult an entertainment attorney for legal
        counsel.
      </footer>
    </main>
  );
}
