import { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';

const COOKIE_NAME = 'facilitator_session';

function verifySignedValue(signedValue: string, secret: string): boolean {
  const lastDotIndex = signedValue.lastIndexOf('.');
  if (lastDotIndex === -1) {
    return false;
  }

  const value = signedValue.substring(0, lastDotIndex);
  const signature = signedValue.substring(lastDotIndex + 1);

  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(value)
    .digest('hex');

  const sigBuffer = Buffer.from(signature, 'hex');
  const expectedBuffer = Buffer.from(expectedSignature, 'hex');

  if (sigBuffer.length !== expectedBuffer.length) {
    return false;
  }

  return crypto.timingSafeEqual(sigBuffer, expectedBuffer);
}

export function middleware(request: NextRequest) {
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

  const valid = verifySignedValue(cookie.value, secret);
  if (!valid) {
    const loginUrl = new URL('/facilitator/login', request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/facilitator/:path*'],
};
