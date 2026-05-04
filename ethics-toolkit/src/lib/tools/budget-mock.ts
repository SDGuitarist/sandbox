/**
 * Mock AI ethical analysis for Budget vs. Ethics Calculator.
 *
 * Returns a static string after a 500ms delay.
 * Used when Anthropic API keys are missing or the API is unreachable.
 *
 * Spec reference: Section 4 Tool 5 (Probabilistic Output), Section 1 (Model Access Preflight)
 */

import type { BudgetOutputType } from '@/lib/schemas/budget';

/**
 * Returns a mock ethical analysis string after a 500ms delay.
 * The output satisfies the BudgetAI schema (ethicalAnalysis: string, min 50, max 2000).
 */
export async function getMockBudgetAI(
  budgetOutput: BudgetOutputType
): Promise<{ ethicalAnalysis: string }> {
  await new Promise((resolve) => setTimeout(resolve, 500));

  const ethicalAnalysis =
    `Based on the ${budgetOutput.budgetTier} tier for a ${budgetOutput.roleName}, ` +
    `the market rate ranges from $${budgetOutput.humanCostRange.low.toLocaleString()} ` +
    `to $${budgetOutput.humanCostRange.high.toLocaleString()}. ` +
    `The displacement risk for this role at this budget level is ${budgetOutput.displacementRisk}. ` +
    `When considering AI tools as alternatives, filmmakers should weigh the ethical implications ` +
    `of displacing human professionals, particularly in creative roles where livelihoods depend ` +
    `on fair compensation. Even when budgets are tight, exploring hybrid approaches that ` +
    `combine AI assistance with human expertise can preserve both quality and ethical standards. ` +
    `Consider whether the cost savings from AI justify the potential impact on the professional ` +
    `community that supports the craft of filmmaking.`;

  return { ethicalAnalysis };
}
