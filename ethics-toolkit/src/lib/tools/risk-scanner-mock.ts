/**
 * Mock AI recommendations for the Project Risk Scanner.
 *
 * Returns a static string array after a 500ms delay.
 * Used when Anthropic API keys are missing or the API is unreachable.
 *
 * Spec reference: Section 4 Tool 3 -- Probabilistic Output (Sonnet 4.6)
 */

import type { RiskAIType } from '@/lib/schemas/risk-scanner';

const MOCK_RECOMMENDATIONS: string[] = [
  'Consider documenting all AI-assisted workflows with clear attribution chains before festival submission deadlines.',
  'Review union guidelines for each department using AI tools -- SAG-AFTRA and WGA have specific provisions that may apply.',
  'Establish a human oversight protocol where a named supervisor reviews and approves every AI-generated output.',
  'Create a training data acknowledgment log that records which AI models were used and their known training data sources.',
  'Prepare a public-facing disclosure statement that proactively addresses AI usage before distribution partners request it.',
];

export async function getMockRiskRecommendations(): Promise<RiskAIType> {
  await new Promise((resolve) => setTimeout(resolve, 500));
  return { recommendations: MOCK_RECOMMENDATIONS };
}
