/**
 * Budget vs. Ethics Calculator schemas.
 *
 * Spec reference: Section 4 Tool 5
 */

import { z } from 'zod';

export const BudgetInput = z.object({
  role: z.enum(['composer', 'vfx_artist', 'storyboard_artist', 'screenwriter', 'voice_actor', 'editor', 'sound_designer', 'colorist']),
  budgetTier: z.enum(['student', 'indie', 'professional', 'studio']),
  projectScope: z.string().min(1).max(500),
  currentBudgetForRole: z.number().min(0).optional(),
});

export type BudgetInputType = z.infer<typeof BudgetInput>;

export const BudgetOutput = z.object({
  roleName: z.string(),
  budgetTier: z.string(),
  humanCostRange: z.object({ low: z.number(), high: z.number() }),
  unionMinimum: z.number().nullable(),
  displacementRisk: z.enum(['high', 'medium', 'low']),
  userBudgetDelta: z.object({ low: z.number(), high: z.number() }).nullable(),
});

export type BudgetOutputType = z.infer<typeof BudgetOutput>;

export const BudgetAI = z.object({
  ethicalAnalysis: z.string().min(50).max(2000),
});

export type BudgetAIType = z.infer<typeof BudgetAI>;

/**
 * Inline Rate Table normalized from docs/reports/031-film-crew-rates-ai-comparison.md
 */
export const RATE_TABLE: Record<string, Record<string, { low: number; high: number; unionMin: number | null; displacementRisk: 'high' | 'medium' | 'low' }>> = {
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
 * Compute the budget output from the input.
 *
 * Rate Selection Rule: Look up RATE_TABLE[role][budgetTier].
 * If currentBudgetForRole is provided:
 *   userBudgetDelta = { low: currentBudgetForRole - humanCostRange.high, high: currentBudgetForRole - humanCostRange.low }
 * Negative delta = under market rate.
 */
export function computeBudget(input: BudgetInputType): BudgetOutputType {
  const rateData = RATE_TABLE[input.role]?.[input.budgetTier];

  if (!rateData) {
    throw new Error(`Rate data unavailable for role "${input.role}" and tier "${input.budgetTier}".`);
  }

  const userBudgetDelta = input.currentBudgetForRole !== undefined
    ? {
        low: input.currentBudgetForRole - rateData.high,
        high: input.currentBudgetForRole - rateData.low,
      }
    : null;

  return {
    roleName: input.role,
    budgetTier: input.budgetTier,
    humanCostRange: { low: rateData.low, high: rateData.high },
    unionMinimum: rateData.unionMin,
    displacementRisk: rateData.displacementRisk,
    userBudgetDelta,
  };
}
