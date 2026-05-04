import { NextRequest, NextResponse } from 'next/server';
import { validateFacilitatorPassword, setFacilitatorCookie } from '@/lib/auth/facilitator';
import { checkDefaultRateLimit } from '@/lib/rate-limit/middleware';

export async function POST(request: NextRequest) {
  // Rate limit: 60 req/min per IP (uses default tier -- brute force mitigation)
  const rateLimitResponse = checkDefaultRateLimit(request);
  if (rateLimitResponse) return rateLimitResponse;

  const body = await request.json();
  const { password } = body;

  if (!password || typeof password !== 'string') {
    return NextResponse.json(
      { error: 'Password is required' },
      { status: 400 }
    );
  }

  const valid = await validateFacilitatorPassword(password);

  if (!valid) {
    return NextResponse.json(
      { error: 'Invalid password' },
      { status: 401 }
    );
  }

  await setFacilitatorCookie();

  return NextResponse.json({ success: true });
}
