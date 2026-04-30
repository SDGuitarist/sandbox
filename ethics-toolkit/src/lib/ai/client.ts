/**
 * Anthropic SDK client setup.
 *
 * Uses ANTHROPIC_API_KEY from environment. When the key is missing,
 * callers should fall back to mock mode -- this module only handles
 * client construction.
 *
 * Spec reference: Section 1 (Model Access Preflight), Section 6 #8 (LLM Routing),
 * Section 12 (Environment Variables)
 */

import Anthropic from '@anthropic-ai/sdk';

/**
 * Model IDs used across AI routes.
 * Haiku 4.5 for simple generation (Disclosure).
 * Sonnet 4.6 for complex analysis (Risk, Budget).
 */
export const MODELS = {
  HAIKU: 'claude-haiku-4-5-20250401',
  SONNET: 'claude-sonnet-4-6-20250514',
} as const;

/**
 * Returns true when the ANTHROPIC_API_KEY environment variable is set
 * and non-empty. All AI routes check this before attempting real API calls.
 */
export function hasApiKey(): boolean {
  return typeof process.env.ANTHROPIC_API_KEY === 'string' && process.env.ANTHROPIC_API_KEY.length > 0;
}

/**
 * Lazily-constructed Anthropic client singleton.
 * Only call this after confirming hasApiKey() is true.
 */
let _client: Anthropic | null = null;

export function getClient(): Anthropic {
  if (!_client) {
    _client = new Anthropic({
      apiKey: process.env.ANTHROPIC_API_KEY,
    });
  }
  return _client;
}
