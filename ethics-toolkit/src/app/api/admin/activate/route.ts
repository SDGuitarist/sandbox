import { NextRequest, NextResponse } from 'next/server';
import { createServiceClient } from '@/lib/supabase/server';
import { verifyFacilitatorSession } from '@/lib/auth/facilitator';
import type { Profile, SquareEntitlement } from '@/types/database';

/**
 * POST /api/admin/activate
 *
 * Facilitator-authenticated route to manually activate a user's paid
 * entitlement after confirming a Square payment.
 *
 * Body: { userEmail: string, squarePaymentId: string }
 * Action: look up profiles by email, set entitlement_status='active',
 *         create square_entitlements row with square_payment_id.
 */
export async function POST(request: NextRequest) {
  // Verify facilitator session
  const isAuthenticated = await verifyFacilitatorSession();
  if (!isAuthenticated) {
    return NextResponse.json(
      { error: 'Unauthorized. Facilitator session required.' },
      { status: 401 }
    );
  }

  // Parse and validate body
  let body: { userEmail?: string; squarePaymentId?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: 'Invalid JSON body.' },
      { status: 400 }
    );
  }

  const { userEmail, squarePaymentId } = body;

  if (!userEmail || typeof userEmail !== 'string') {
    return NextResponse.json(
      { error: 'userEmail is required and must be a string.' },
      { status: 400 }
    );
  }

  if (!squarePaymentId || typeof squarePaymentId !== 'string') {
    return NextResponse.json(
      { error: 'squarePaymentId is required and must be a string.' },
      { status: 400 }
    );
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const supabase = createServiceClient() as any;

  // Look up profile by email
  const { data: profile, error: profileError } = await supabase
    .from('profiles')
    .select('user_id, entitlement_status')
    .eq('email', userEmail)
    .single() as { data: Pick<Profile, 'user_id' | 'entitlement_status'> | null; error: Error | null };

  if (profileError || !profile) {
    return NextResponse.json(
      { error: `No profile found for email: ${userEmail}` },
      { status: 404 }
    );
  }

  // Update entitlement_status to 'active'
  const { error: updateError } = await supabase
    .from('profiles')
    .update({
      entitlement_status: 'active',
      updated_at: new Date().toISOString(),
    })
    .eq('user_id', profile.user_id);

  if (updateError) {
    return NextResponse.json(
      { error: 'Failed to update entitlement status.' },
      { status: 500 }
    );
  }

  // Create square_entitlements row (upsert on user_id)
  const { error: entitlementError } = await supabase
    .from('square_entitlements')
    .upsert(
      {
        user_id: profile.user_id,
        square_payment_id: squarePaymentId,
        updated_at: new Date().toISOString(),
      } as Partial<SquareEntitlement>,
      { onConflict: 'user_id' }
    );

  if (entitlementError) {
    return NextResponse.json(
      { error: 'Failed to create square entitlement record.' },
      { status: 500 }
    );
  }

  return NextResponse.json({
    success: true,
    userId: profile.user_id,
    entitlementStatus: 'active',
    squarePaymentId,
  });
}
