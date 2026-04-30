/**
 * Mock AI response for the Disclosure Generator.
 *
 * Returns a static disclosure text string after a 500ms delay.
 * Used in mock mode (no API keys) and for Phase 2 deterministic-first development.
 *
 * Spec reference: Section 4 Tool 1 -- Probabilistic Output
 */

const MOCK_DISCLOSURE_TEXT =
  'This project utilized artificial intelligence tools during production. ' +
  'AI was employed in specific creative departments as detailed in the disclosure checklist above. ' +
  'All AI-generated content was reviewed and approved by human supervisors where applicable. ' +
  'The production team acknowledges the use of AI models that may have been trained on copyrighted material ' +
  'and has documented consent where voice or likeness AI was involved. ' +
  'This disclosure is provided in the spirit of transparency and ethical filmmaking practices. ' +
  'For questions regarding the specific AI tools and methodologies used, ' +
  'please contact the production team directly.';

/**
 * Simulates an AI-generated disclosure statement.
 * Returns after a 500ms delay to mimic API latency.
 */
export async function getMockDisclosureAI(): Promise<{ disclosureText: string }> {
  await new Promise((resolve) => setTimeout(resolve, 500));
  return { disclosureText: MOCK_DISCLOSURE_TEXT };
}
