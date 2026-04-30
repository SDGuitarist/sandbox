import bcrypt from 'bcryptjs';
import { cookies } from 'next/headers';
import crypto from 'crypto';

const COOKIE_NAME = 'facilitator_session';
const MAX_AGE = 86400;

function getSecret(): string {
  const secret = process.env.FACILITATOR_SESSION_SECRET;
  if (!secret) {
    throw new Error('FACILITATOR_SESSION_SECRET environment variable is required');
  }
  return secret;
}

function signValue(value: string): string {
  const secret = getSecret();
  const signature = crypto
    .createHmac('sha256', secret)
    .update(value)
    .digest('hex');
  return `${value}.${signature}`;
}

function verifySignedValue(signedValue: string): string | null {
  const lastDotIndex = signedValue.lastIndexOf('.');
  if (lastDotIndex === -1) {
    return null;
  }

  const value = signedValue.substring(0, lastDotIndex);
  const signature = signedValue.substring(lastDotIndex + 1);

  const secret = getSecret();
  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(value)
    .digest('hex');

  const sigBuffer = Buffer.from(signature, 'hex');
  const expectedBuffer = Buffer.from(expectedSignature, 'hex');

  if (sigBuffer.length !== expectedBuffer.length) {
    return null;
  }

  if (!crypto.timingSafeEqual(sigBuffer, expectedBuffer)) {
    return null;
  }

  return value;
}

export async function validateFacilitatorPassword(password: string): Promise<boolean> {
  const hash = process.env.FACILITATOR_PASSWORD_HASH;
  if (!hash) {
    return false;
  }
  return bcrypt.compare(password, hash);
}

export async function setFacilitatorCookie(): Promise<void> {
  const value = crypto.randomUUID();
  const signedValue = signValue(value);

  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, signedValue, {
    httpOnly: true,
    secure: true,
    sameSite: 'lax',
    maxAge: MAX_AGE,
    path: '/',
  });
}

export async function verifyFacilitatorSession(): Promise<boolean> {
  const cookieStore = await cookies();
  const cookie = cookieStore.get(COOKIE_NAME);

  if (!cookie) {
    return false;
  }

  const value = verifySignedValue(cookie.value);
  return value !== null;
}
