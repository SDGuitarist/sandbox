/**
 * Mock AI response functions for all three LLM-backed tools.
 *
 * Used when ANTHROPIC_API_KEY is missing or when the Anthropic API is
 * unreachable. Each function returns data that satisfies its corresponding
 * Zod schema (DisclosureAI, RiskAI, BudgetAI).
 *
 * These mirror the existing Phase 2 mock tools but are consolidated here
 * for the AI route layer. The mock tools in src/lib/tools/*-mock.ts are
 * the authoritative Phase 2 implementations; these wrappers re-export
 * their behaviour in a consistent shape for the API routes.
 *
 * Spec reference: Section 1 (Model Access Preflight -- mock mode),
 * Section 4 (DisclosureAI, RiskAI, BudgetAI Zod shapes)
 */

import type { DisclosureAIType } from '@/lib/schemas/disclosure';
import type { RiskAIType } from '@/lib/schemas/risk-scanner';
import type { BudgetAIType } from '@/lib/schemas/budget';

// ---------------------------------------------------------------------------
// Disclosure mock (matches DisclosureAI: { disclosureText: string })
// ---------------------------------------------------------------------------

const MOCK_DISCLOSURE_TEXT =
  'This project utilized artificial intelligence tools during production. ' +
  'AI was employed in specific creative departments as detailed in the disclosure checklist above. ' +
  'All AI-generated content was reviewed and approved by human supervisors where applicable. ' +
  'The production team acknowledges the use of AI models that may have been trained on copyrighted material ' +
  'and has documented consent where voice or likeness AI was involved. ' +
  'This disclosure is provided in the spirit of transparency and ethical filmmaking practices. ' +
  'For questions regarding the specific AI tools and methodologies used, ' +
  'please contact the production team directly.';

export async function getMockDisclosureAI(): Promise<DisclosureAIType> {
  await new Promise((resolve) => setTimeout(resolve, 500));
  return { disclosureText: MOCK_DISCLOSURE_TEXT };
}

// ---------------------------------------------------------------------------
// Risk mock (matches RiskAI: { recommendations: string[] })
// ---------------------------------------------------------------------------

const MOCK_RECOMMENDATIONS: string[] = [
  'Consider documenting all AI-assisted workflows with clear attribution chains before festival submission deadlines.',
  'Review union guidelines for each department using AI tools -- SAG-AFTRA and WGA have specific provisions that may apply.',
  'Establish a human oversight protocol where a named supervisor reviews and approves every AI-generated output.',
  'Create a training data acknowledgment log that records which AI models were used and their known training data sources.',
  'Prepare a public-facing disclosure statement that proactively addresses AI usage before distribution partners request it.',
];

export async function getMockRiskAI(): Promise<RiskAIType> {
  await new Promise((resolve) => setTimeout(resolve, 500));
  return { recommendations: MOCK_RECOMMENDATIONS };
}

// ---------------------------------------------------------------------------
// Budget mock (matches BudgetAI: { ethicalAnalysis: string })
// ---------------------------------------------------------------------------

const MOCK_ETHICAL_ANALYSIS =
  'When considering AI tools as alternatives to human professionals, filmmakers should weigh ' +
  'the ethical implications of displacing skilled workers, particularly in creative roles where ' +
  'livelihoods depend on fair compensation. Even when budgets are tight, exploring hybrid ' +
  'approaches that combine AI assistance with human expertise can preserve both quality and ' +
  'ethical standards. Consider whether the cost savings from AI justify the potential impact ' +
  'on the professional community that supports the craft of filmmaking. ' +
  'Transparent disclosure of AI usage in your production helps maintain trust with audiences, ' +
  'collaborators, and festival selection committees alike.';

export async function getMockBudgetAI(): Promise<BudgetAIType> {
  await new Promise((resolve) => setTimeout(resolve, 500));
  return { ethicalAnalysis: MOCK_ETHICAL_ANALYSIS };
}
