/**
 * Fixture test for Project Risk Scanner (Tool 3).
 *
 * Verifies scoring produces exact expected output from the spec fixture.
 * Spec reference: Section 4 Tool 3
 */

import { describe, it, expect } from 'vitest';
import { RiskScannerInput, RiskScannerOutput, RiskAI, computeRiskScore } from '../../src/lib/schemas/risk-scanner';

describe('RiskScannerInput schema', () => {
  it('validates the spec fixture input', () => {
    const input = {
      projectType: 'feature',
      budgetTier: 'indie',
      departments: [
        { role: 'composer', aiUsageLevel: 'generated' },
        { role: 'screenwriter', aiUsageLevel: 'assisted' },
        { role: 'vfx_artist', aiUsageLevel: 'none' },
      ],
      distributionType: 'major_festival',
      unionAffiliation: 'non_union',
    };

    const result = RiskScannerInput.safeParse(input);
    expect(result.success).toBe(true);
  });

  it('rejects empty departments array', () => {
    const input = {
      projectType: 'feature',
      budgetTier: 'indie',
      departments: [],
      distributionType: 'major_festival',
      unionAffiliation: 'non_union',
    };

    const result = RiskScannerInput.safeParse(input);
    expect(result.success).toBe(false);
  });

  it('rejects invalid role', () => {
    const input = {
      projectType: 'feature',
      budgetTier: 'indie',
      departments: [
        { role: 'invalid_role', aiUsageLevel: 'none' },
      ],
      distributionType: 'major_festival',
      unionAffiliation: 'non_union',
    };

    const result = RiskScannerInput.safeParse(input);
    expect(result.success).toBe(false);
  });
});

describe('RiskScannerOutput schema', () => {
  it('validates a well-formed output', () => {
    const output = {
      totalScore: 4,
      tier: 'medium',
      dimensions: {
        legal: { raw: 4.9, multiplied: 4.9, score: 5 },
        ethical: { raw: 4.9, multiplied: 4.9, score: 5 },
        reputational: { raw: 3.6, multiplied: 5.4, score: 5 },
        union: { raw: 4.9, multiplied: 2.45, score: 2 },
      },
      departmentFlags: [
        { role: 'composer', flag: 'critical', score: 3.6 },
        { role: 'screenwriter', flag: 'caution', score: 1.3 },
        { role: 'vfx_artist', flag: 'safe', score: 0 },
      ],
    };

    const result = RiskScannerOutput.safeParse(output);
    expect(result.success).toBe(true);
  });
});

describe('RiskAI schema', () => {
  it('validates recommendations array', () => {
    const ai = {
      recommendations: ['Consider hiring a human composer to review and approve all AI-generated music.'],
    };
    const result = RiskAI.safeParse(ai);
    expect(result.success).toBe(true);
  });

  it('rejects empty recommendations', () => {
    const ai = { recommendations: [] };
    const result = RiskAI.safeParse(ai);
    expect(result.success).toBe(false);
  });

  it('rejects recommendation under 10 characters', () => {
    const ai = { recommendations: ['Short'] };
    const result = RiskAI.safeParse(ai);
    expect(result.success).toBe(false);
  });
});

describe('computeRiskScore (spec fixture)', () => {
  const fixtureInput = {
    projectType: 'feature' as const,
    budgetTier: 'indie' as const,
    departments: [
      { role: 'composer' as const, aiUsageLevel: 'generated' as const },
      { role: 'screenwriter' as const, aiUsageLevel: 'assisted' as const },
      { role: 'vfx_artist' as const, aiUsageLevel: 'none' as const },
    ],
    distributionType: 'major_festival' as const,
    unionAffiliation: 'non_union' as const,
  };

  it('produces totalScore = 4', () => {
    const result = computeRiskScore(fixtureInput);
    expect(result.totalScore).toBe(4);
  });

  it('produces tier = medium', () => {
    const result = computeRiskScore(fixtureInput);
    expect(result.tier).toBe('medium');
  });

  it('produces exact department flags from spec fixture', () => {
    const result = computeRiskScore(fixtureInput);
    expect(result.departmentFlags).toEqual([
      { role: 'composer', flag: 'critical', score: 3.6 },
      { role: 'screenwriter', flag: 'caution', score: 1.3 },
      { role: 'vfx_artist', flag: 'safe', score: 0 },
    ]);
  });

  it('validates output against RiskScannerOutput schema', () => {
    const result = computeRiskScore(fixtureInput);
    const validation = RiskScannerOutput.safeParse(result);
    expect(validation.success).toBe(true);
  });

  it('step-by-step verification: department scores', () => {
    // composer: generated (3) * 1.2 = 3.6
    // screenwriter: assisted (1) * 1.3 = 1.3
    // vfx_artist: none (0) * 1.0 = 0
    const result = computeRiskScore(fixtureInput);
    expect(result.departmentFlags[0].score).toBe(3.6);
    expect(result.departmentFlags[1].score).toBe(1.3);
    expect(result.departmentFlags[2].score).toBe(0);
  });

  it('step-by-step verification: dimension raw scores', () => {
    const result = computeRiskScore(fixtureInput);
    // legalRaw = 3.6 + 1.3 + 0 = 4.9
    expect(result.dimensions.legal.raw).toBeCloseTo(4.9);
    // ethicalRaw = composer(3.6) + screenwriter(1.3) = 4.9 (voice_actor not present)
    expect(result.dimensions.ethical.raw).toBeCloseTo(4.9);
    // reputationalRaw = only generated departments: composer(3.6)
    expect(result.dimensions.reputational.raw).toBeCloseTo(3.6);
    // unionRaw = assisted + generated: composer(3.6) + screenwriter(1.3) = 4.9
    expect(result.dimensions.union.raw).toBeCloseTo(4.9);
  });

  it('step-by-step verification: dimension multiplied values', () => {
    const result = computeRiskScore(fixtureInput);
    // legal: no multiplier, multiplied = 4.9
    expect(result.dimensions.legal.multiplied).toBeCloseTo(4.9);
    // ethical: no multiplier, multiplied = 4.9
    expect(result.dimensions.ethical.multiplied).toBeCloseTo(4.9);
    // reputational: major_festival = 1.5x, multiplied = 3.6 * 1.5 = 5.4
    expect(result.dimensions.reputational.multiplied).toBeCloseTo(5.4);
    // union: non_union = 0.5x, multiplied = 4.9 * 0.5 = 2.45
    expect(result.dimensions.union.multiplied).toBeCloseTo(2.45);
  });

  it('step-by-step verification: dimension scores (clamped rounded)', () => {
    const result = computeRiskScore(fixtureInput);
    // legal: round(4.9) = 5, clamped to 0-10 = 5
    expect(result.dimensions.legal.score).toBe(5);
    // ethical: round(4.9) = 5
    expect(result.dimensions.ethical.score).toBe(5);
    // reputational: round(5.4) = 5
    expect(result.dimensions.reputational.score).toBe(5);
    // union: round(2.45) = 2
    expect(result.dimensions.union.score).toBe(2);
  });

  it('step-by-step verification: total score calculation', () => {
    // totalScore = round(5 * 0.30 + 5 * 0.25 + 5 * 0.25 + 2 * 0.20)
    //            = round(1.5 + 1.25 + 1.25 + 0.4)
    //            = round(4.4)
    //            = 4
    const result = computeRiskScore(fixtureInput);
    expect(result.totalScore).toBe(4);
  });

  it('produces low tier for all-none departments', () => {
    const lowInput = {
      ...fixtureInput,
      departments: [
        { role: 'composer' as const, aiUsageLevel: 'none' as const },
        { role: 'screenwriter' as const, aiUsageLevel: 'none' as const },
      ],
    };
    const result = computeRiskScore(lowInput);
    expect(result.totalScore).toBe(0);
    expect(result.tier).toBe('low');
  });
});
