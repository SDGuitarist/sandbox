import { NextRequest, NextResponse } from 'next/server';
import { validateFacilitatorPassword, setFacilitatorCookie } from '@/lib/auth/facilitator';

export async function POST(request: NextRequest) {
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
