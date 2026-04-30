/**
 * Budget vs. Ethics Calculator -- deterministic lookup and delta calculation.
 *
 * Spec reference: Section 4 Tool 5
 *
 * RATE_TABLE contains all 8 roles x 4 tiers from the spec.
 * Rate Selection Rule: Look up RATE_TABLE[role][budgetTier].
 * If currentBudgetForRole is provided:
 *   userBudgetDelta.low = currentBudgetForRole - humanCostRange.high
 *   userBudgetDelta.high = currentBudgetForRole - humanCostRange.low
 * Negative delta = under market rate.
 */

import {
  type BudgetInputType,
  type BudgetOutputType,
  BudgetOutput,
} from '@/lib/schemas/budget';

export const RATE_TABLE: Record<
  string,
  Record<
    string,
    {
      low: number;
      high: number;
      unionMin: number | null;
      displacementRisk: 'high' | 'medium' | 'low';
    }
  >
> = {
  composer: {
    student: { low: 1500, high: 5000, unionMin: null, displacementRisk: 'high' },
    indie: { low: 2000, high: 25000, unionMin: null, displacementRisk: 'high' },
    professional: { low: 10000, high: 100000, unionMin: null, displacementRisk: 'medium' },
    studio: { low: 50000, high: 500000, unionMin: null, displacementRisk: 'low' },
  },
  vfx_artist: {
    student: { low: 500, high: 2000, unionMin: null, displacementRisk: 'high' },
    indie: { low: 5000, high: 25000, unionMin: null, displacementRisk: 'high' },
    professional: { low: 25000, high: 100000, unionMin: null, displacementRisk: 'medium' },
    studio: { low: 100000, high: 500000, unionMin: null, displacementRisk: 'low' },
  },
  storyboard_artist: {
    student: { low: 500, high: 2500, unionMin: null, displacementRisk: 'high' },
    indie: { low: 2500, high: 15000, unionMin: null, displacementRisk: 'high' },
    professional: { low: 5000, high: 30000, unionMin: null, displacementRisk: 'medium' },
    studio: { low: 15000, high: 50000, unionMin: null, displacementRisk: 'low' },
  },
  screenwriter: {
    student: { low: 500, high: 5000, unionMin: null, displacementRisk: 'medium' },
    indie: { low: 2500, high: 15000, unionMin: null, displacementRisk: 'medium' },
    professional: { low: 10000, high: 40000, unionMin: 77495, displacementRisk: 'medium' },
    studio: { low: 50000, high: 150000, unionMin: 147920, displacementRisk: 'low' },
  },
  voice_actor: {
    student: { low: 200, high: 500, unionMin: null, displacementRisk: 'high' },
    indie: { low: 500, high: 2000, unionMin: 249, displacementRisk: 'high' },
    professional: { low: 1000, high: 5000, unionMin: 810, displacementRisk: 'high' },
    studio: { low: 2000, high: 10000, unionMin: 1246, displacementRisk: 'medium' },
  },
  editor: {
    student: { low: 500, high: 2000, unionMin: null, displacementRisk: 'medium' },
    indie: { low: 5000, high: 25000, unionMin: null, displacementRisk: 'medium' },
    professional: { low: 15000, high: 50000, unionMin: null, displacementRisk: 'low' },
    studio: { low: 50000, high: 200000, unionMin: null, displacementRisk: 'low' },
  },
  sound_designer: {
    student: { low: 500, high: 2000, unionMin: null, displacementRisk: 'medium' },
    indie: { low: 2000, high: 15000, unionMin: null, displacementRisk: 'medium' },
    professional: { low: 10000, high: 35000, unionMin: null, displacementRisk: 'medium' },
    studio: { low: 25000, high: 100000, unionMin: null, displacementRisk: 'low' },
  },
  colorist: {
    student: { low: 300, high: 1000, unionMin: null, displacementRisk: 'high' },
    indie: { low: 2000, high: 10000, unionMin: null, displacementRisk: 'high' },
    professional: { low: 5000, high: 15000, unionMin: null, displacementRisk: 'medium' },
    studio: { low: 15000, high: 50000, unionMin: null, displacementRisk: 'low' },
  },
};

/**
 * Deterministic budget lookup and delta calculation.
 *
 * Looks up RATE_TABLE[role][budgetTier] and computes the user budget delta
 * when currentBudgetForRole is provided.
 *
 * Throws if the role/tier combination is not found.
 */
export function computeBudget(input: BudgetInputType): BudgetOutputType {
  const rateData = RATE_TABLE[input.role]?.[input.budgetTier];

  if (!rateData) {
    throw new Error(
      `Rate data unavailable for role "${input.role}" and tier "${input.budgetTier}".`
    );
  }

  const userBudgetDelta =
    input.currentBudgetForRole !== undefined
      ? {
          low: input.currentBudgetForRole - rateData.high,
          high: input.currentBudgetForRole - rateData.low,
        }
      : null;

  const result: BudgetOutputType = {
    roleName: input.role,
    budgetTier: input.budgetTier,
    humanCostRange: { low: rateData.low, high: rateData.high },
    unionMinimum: rateData.unionMin,
    displacementRisk: rateData.displacementRisk,
    userBudgetDelta,
  };

  // Validate output matches schema
  BudgetOutput.parse(result);

  return result;
}
