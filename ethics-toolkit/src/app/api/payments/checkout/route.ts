import { NextResponse } from 'next/server';

/**
 * GET /api/payments/checkout
 *
 * Redirects the user to the Square-hosted checkout page (sandbox mode).
 * The checkout URL is configured via the SQUARE_CHECKOUT_URL env var.
 *
 * After payment, Square redirects the user back to /payments/pending.
 */
export async function GET() {
  const checkoutUrl = process.env.SQUARE_CHECKOUT_URL;

  if (!checkoutUrl) {
    return NextResponse.json(
      { error: 'Payment checkout is not configured. Please contact the facilitator.' },
      { status: 503 }
    );
  }

  return NextResponse.redirect(checkoutUrl);
}
