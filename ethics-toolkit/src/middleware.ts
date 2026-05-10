import { NextRequest, NextResponse } from 'next/server';

const COOKIE_NAME = 'facilitator_session';

async function verifySignedValue(signedValue: string, secret: string): Promise<boolean> {
  const lastDotIndex = signedValue.lastIndexOf('.');
  if (lastDotIndex === -1) return false;

  const value = signedValue.substring(0, lastDotIndex);
  const signature = signedValue.substring(lastDotIndex + 1);

  // Web Crypto API HMAC (Edge Runtime compatible)
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const sigBytes = await crypto.subtle.sign('HMAC', key, encoder.encode(value));
  const expectedSignature = Array.from(new Uint8Array(sigBytes))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');

  // Constant-time comparison
  if (signature.length !== expectedSignature.length) return false;
  let mismatch = 0;
  for (let i = 0; i < signature.length; i++) {
    mismatch |= signature.charCodeAt(i) ^ expectedSignature.charCodeAt(i);
  }
  return mismatch === 0;
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (!pathname.startsWith('/facilitator')) {
    return NextResponse.next();
  }

  if (pathname === '/facilitator/login') {
    return NextResponse.next();
  }

  const cookie = request.cookies.get(COOKIE_NAME);

  if (!cookie) {
    const loginUrl = new URL('/facilitator/login', request.url);
    return NextResponse.redirect(loginUrl);
  }

  const secret = process.env.FACILITATOR_SESSION_SECRET;
  if (!secret) {
    const loginUrl = new URL('/facilitator/login', request.url);
    return NextResponse.redirect(loginUrl);
  }

  const valid = await verifySignedValue(cookie.value, secret);
  if (!valid) {
    const loginUrl = new URL('/facilitator/login', request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/facilitator/:path*'],
};
