/**
 * Project Risk Scanner schemas and deterministic scoring engine.
 *
 * Spec reference: Section 4 Tool 3
 */

import { z } from 'zod';

export const RiskScannerInput = z.object({
  projectType: z.enum(['feature', 'short', 'documentary', 'commercial', 'music_video', 'web_series']),
  budgetTier: z.enum(['student', 'indie', 'professional', 'studio']),
  departments: z.array(z.object({
    role: z.enum(['screenwriter', 'composer', 'vfx_artist', 'voice_actor', 'editor', 'sound_designer', 'colorist', 'storyboard_artist', 'director']),
    aiUsageLevel: z.enum(['none', 'assisted', 'generated']),
    description: z.string().max(500).optional(),
  })).min(1),
  distributionType: z.enum(['none', 'online', 'indie_festival', 'major_festival', 'broadcast_theatrical']),
  unionAffiliation: z.enum(['sag_aftra', 'wga', 'iatse', 'non_union', 'mixed']),
});

export type RiskScannerInputType = z.infer<typeof RiskScannerInput>;

export const RiskScannerOutput = z.object({
  totalScore: z.number().min(0).max(10),
  tier: z.enum(['low', 'medium', 'high', 'critical']),
  dimensions: z.object({
    legal: z.object({ raw: z.number(), multiplied: z.number(), score: z.number() }),
    ethical: z.object({ raw: z.number(), multiplied: z.number(), score: z.number() }),
    reputational: z.object({ raw: z.number(), multiplied: z.number(), score: z.number() }),
    union: z.object({ raw: z.number(), multiplied: z.number(), score: z.number() }),
  }),
  departmentFlags: z.array(z.object({
    role: z.string(),
    flag: z.enum(['safe', 'caution', 'warning', 'critical']),
    score: z.number(),
  })),
});

export type RiskScannerOutputType = z.infer<typeof RiskScannerOutput>;

export const RiskAI = z.object({
  recommendations: z.array(z.string().min(10).max(500)).min(1).max(10),
});

export type RiskAIType = z.infer<typeof RiskAI>;

// --- Deterministic Scoring Engine (Steps 1-7) ---

/**
 * Step 1: Per-department base points
 */
const BASE_POINTS: Record<string, number> = {
  none: 0,
  assisted: 1,
  generated: 3,
};

/**
 * Step 2: Role vulnerability multiplier
 */
const ROLE_MULTIPLIER: Record<string, number> = {
  voice_actor: 1.5,
  screenwriter: 1.3,
  composer: 1.2,
  director: 1.0,
  vfx_artist: 1.0,
  editor: 1.0,
  sound_designer: 1.0,
  colorist: 0.8,
  storyboard_artist: 0.8,
};

/**
 * Roles that contribute to the ethical dimension raw score.
 */
const ETHICAL_ROLES = new Set(['voice_actor', 'composer', 'screenwriter']);

/**
 * Round to a fixed number of decimal places to avoid floating point artifacts.
 * For example, 3 * 1.2 = 3.5999999999999996 in IEEE 754, but we want 3.6.
 */
function roundPrecision(value: number, decimals: number = 10): number {
  const factor = Math.pow(10, decimals);
  return Math.round(value * factor) / factor;
}

/**
 * Clamp a number between min and max.
 */
function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/**
 * Get the department flag label from a department score.
 * Step 7 from spec.
 */
function getDepartmentFlag(score: number): 'safe' | 'caution' | 'warning' | 'critical' {
  if (score === 0) return 'safe';
  if (score <= 1.5) return 'caution';
  if (score <= 3.0) return 'warning';
  return 'critical';
}

/**
 * Get the tier label from a total score.
 * Step 6 from spec.
 */
function getTier(totalScore: number): 'low' | 'medium' | 'high' | 'critical' {
  if (totalScore <= 2) return 'low';
  if (totalScore <= 5) return 'medium';
  if (totalScore <= 7) return 'high';
  return 'critical';
}

/**
 * Compute the full deterministic risk score from the input.
 * Implements Steps 1-7 from the spec exactly.
 */
export function computeRiskScore(input: RiskScannerInputType): RiskScannerOutputType {
  // Step 1 + 2: Compute per-department scores
  const departmentScores = input.departments.map((dept) => {
    const basePoints = BASE_POINTS[dept.aiUsageLevel];
    const multiplier = ROLE_MULTIPLIER[dept.role];
    const score = roundPrecision(basePoints * multiplier);
    return { role: dept.role, aiUsageLevel: dept.aiUsageLevel, score };
  });

  // Step 3: Dimension raw scores
  const legalRaw = departmentScores.reduce((sum, d) => sum + d.score, 0);

  const ethicalRaw = departmentScores
    .filter((d) => ETHICAL_ROLES.has(d.role))
    .reduce((sum, d) => sum + d.score, 0);

  const reputationalRaw = departmentScores
    .filter((d) => d.aiUsageLevel === 'generated')
    .reduce((sum, d) => sum + d.score, 0);

  const unionRaw = departmentScores
    .filter((d) => d.aiUsageLevel === 'assisted' || d.aiUsageLevel === 'generated')
    .reduce((sum, d) => sum + d.score, 0);

  // Step 4: Dimension multipliers
  let unionMultiplier = 1.0;
  if (input.unionAffiliation === 'sag_aftra' || input.unionAffiliation === 'wga') {
    unionMultiplier = 1.5;
  } else if (input.unionAffiliation === 'iatse' || input.unionAffiliation === 'mixed') {
    unionMultiplier = 1.3;
  } else if (input.unionAffiliation === 'non_union') {
    unionMultiplier = 0.5;
  }

  let reputationalMultiplier = 1.0;
  if (input.distributionType === 'major_festival' || input.distributionType === 'broadcast_theatrical') {
    reputationalMultiplier = 1.5;
  } else if (input.distributionType === 'indie_festival') {
    reputationalMultiplier = 1.2;
  }
  // online or none = 1.0 (default)

  // Step 5: Normalize and weight
  const legalMultiplied = legalRaw * 1.0; // no additional multiplier for legal
  const ethicalMultiplied = ethicalRaw * 1.0; // no additional multiplier for ethical
  const reputationalMultiplied = reputationalRaw * reputationalMultiplier;
  const unionMultiplied = unionRaw * unionMultiplier;

  const legalScore = clamp(Math.round(legalMultiplied), 0, 10);
  const ethicalScore = clamp(Math.round(ethicalMultiplied), 0, 10);
  const reputationalScore = clamp(Math.round(reputationalMultiplied), 0, 10);
  const unionScore = clamp(Math.round(unionMultiplied), 0, 10);

  const totalScore = Math.round(
    legalScore * 0.30 +
    ethicalScore * 0.25 +
    reputationalScore * 0.25 +
    unionScore * 0.20
  );

  // Step 6: Tier mapping
  const tier = getTier(totalScore);

  // Step 7: Per-department vulnerability flags
  const departmentFlags = departmentScores.map((d) => ({
    role: d.role,
    flag: getDepartmentFlag(d.score),
    score: d.score,
  }));

  return {
    totalScore,
    tier,
    dimensions: {
      legal: { raw: legalRaw, multiplied: legalMultiplied, score: legalScore },
      ethical: { raw: ethicalRaw, multiplied: ethicalMultiplied, score: ethicalScore },
      reputational: { raw: reputationalRaw, multiplied: reputationalMultiplied, score: reputationalScore },
      union: { raw: unionRaw, multiplied: unionMultiplied, score: unionScore },
    },
    departmentFlags,
  };
}
