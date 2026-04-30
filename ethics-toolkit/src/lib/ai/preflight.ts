/**
 * Model Access Preflight check.
 *
 * At startup (or first AI route hit), verifies that Haiku 4.5 and Sonnet 4.6
 * are reachable via the Anthropic API. If either is unreachable, the app falls
 * back to mock mode automatically.
 *
 * Spec reference: Section 1 (Model Access Preflight -- mock mode fallback)
 */

import { hasApiKey, getClient, MODELS } from './client';

/**
 * Preflight result cached after the first check so we do not re-check
 * on every request. Reset by calling resetPreflight() (useful in tests).
 */
let preflightResult: PreflightResult | null = null;

export interface PreflightResult {
  haiku: boolean;
  sonnet: boolean;
  mock: boolean;        // true when either model is unreachable or key is missing
  checkedAt: string;    // ISO 8601 timestamp
}

/**
 * Ping a single model by sending a minimal request.
 * Returns true if the model responds, false on any error.
 */
async function pingModel(modelId: string): Promise<boolean> {
  try {
    const client = getClient();
    await client.messages.create({
      model: modelId,
      max_tokens: 1,
      messages: [{ role: 'user', content: 'ping' }],
    });
    return true;
  } catch {
    return false;
  }
}

/**
 * Run the preflight check. Results are cached for the lifetime of the
 * server process. Call resetPreflight() to force a re-check.
 *
 * When ANTHROPIC_API_KEY is missing, returns mock mode immediately
 * without making any network requests.
 */
export async function runPreflight(): Promise<PreflightResult> {
  if (preflightResult) return preflightResult;

  // No API key => mock mode, no network calls needed
  if (!hasApiKey()) {
    preflightResult = {
      haiku: false,
      sonnet: false,
      mock: true,
      checkedAt: new Date().toISOString(),
    };
    return preflightResult;
  }

  // Check both models in parallel
  const [haiku, sonnet] = await Promise.all([
    pingModel(MODELS.HAIKU),
    pingModel(MODELS.SONNET),
  ]);

  preflightResult = {
    haiku,
    sonnet,
    mock: !haiku || !sonnet,
    checkedAt: new Date().toISOString(),
  };

  return preflightResult;
}

/**
 * Returns the cached preflight result, or null if preflight has not run yet.
 * Use this for synchronous checks after the initial preflight has completed.
 */
export function getPreflightResult(): PreflightResult | null {
  return preflightResult;
}

/**
 * Clear the cached preflight result so the next call to runPreflight()
 * performs a fresh check. Primarily useful in tests.
 */
export function resetPreflight(): void {
  preflightResult = null;
}
