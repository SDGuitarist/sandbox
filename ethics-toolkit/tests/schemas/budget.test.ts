/**
 * Fixture test for Budget vs. Ethics Calculator (Tool 5).
 *
 * Verifies rate lookup and userBudgetDelta from the spec fixture.
 * Spec reference: Section 4 Tool 5
 */

import { describe, it, expect } from 'vitest';
import { BudgetInput, BudgetOutput, BudgetAI, RATE_TABLE, computeBudget } from '../../src/lib/schemas/budget';

describe('BudgetInput schema', () => {
  it('validates the spec fixture input', () => {
    const input = {
      role: 'composer',
      budgetTier: 'indie',
      projectScope: '10-minute short film score, 3 themes',
      currentBudgetForRole: 1500,
    };

    const result = BudgetInput.safeParse(input);
    expect(result.success).toBe(true);
  });

  it('validates input without currentBudgetForRole (optional)', () => {
    const input = {
      role: 'composer',
      budgetTier: 'indie',
      projectScope: '10-minute short film score',
    };

    const result = BudgetInput.safeParse(input);
    expect(result.success).toBe(true);
  });

  it('rejects empty projectScope', () => {
    const input = {
      role: 'composer',
      budgetTier: 'indie',
      projectScope: '',
    };

    const result = BudgetInput.safeParse(input);
    expect(result.success).toBe(false);
  });

  it('rejects negative currentBudgetForRole', () => {
    const input = {
      role: 'composer',
      budgetTier: 'indie',
      projectScope: 'Test',
      currentBudgetForRole: -100,
    };

    const result = BudgetInput.safeParse(input);
    expect(result.success).toBe(false);
  });

  it('rejects invalid role', () => {
    const input = {
      role: 'invalid_role',
      budgetTier: 'indie',
      projectScope: 'Test',
    };

    const result = BudgetInput.safeParse(input);
    expect(result.success).toBe(false);
  });
});

describe('BudgetOutput schema', () => {
  it('validates a well-formed output', () => {
    const output = {
      roleName: 'composer',
      budgetTier: 'indie',
      humanCostRange: { low: 2000, high: 25000 },
      unionMinimum: null,
      displacementRisk: 'high',
      userBudgetDelta: { low: -23500, high: -500 },
    };

    const result = BudgetOutput.safeParse(output);
    expect(result.success).toBe(true);
  });

  it('validates output with null userBudgetDelta', () => {
    const output = {
      roleName: 'composer',
      budgetTier: 'indie',
      humanCostRange: { low: 2000, high: 25000 },
      unionMinimum: null,
      displacementRisk: 'high',
      userBudgetDelta: null,
    };

    const result = BudgetOutput.safeParse(output);
    expect(result.success).toBe(true);
  });
});

describe('BudgetAI schema', () => {
  it('validates ethical analysis within bounds', () => {
    const ai = { ethicalAnalysis: 'A'.repeat(100) };
    const result = BudgetAI.safeParse(ai);
    expect(result.success).toBe(true);
  });

  it('rejects text under 50 characters', () => {
    const ai = { ethicalAnalysis: 'Too short' };
    const result = BudgetAI.safeParse(ai);
    expect(result.success).toBe(false);
  });
});

describe('RATE_TABLE', () => {
  it('has entries for all 8 roles', () => {
    const roles = ['composer', 'vfx_artist', 'storyboard_artist', 'screenwriter', 'voice_actor', 'editor', 'sound_designer', 'colorist'];
    for (const role of roles) {
      expect(RATE_TABLE[role]).toBeDefined();
    }
  });

  it('has entries for all 4 budget tiers per role', () => {
    const tiers = ['student', 'indie', 'professional', 'studio'];
    for (const role of Object.keys(RATE_TABLE)) {
      for (const tier of tiers) {
        expect(RATE_TABLE[role][tier]).toBeDefined();
      }
    }
  });

  it('has correct composer indie rates from spec', () => {
    const rate = RATE_TABLE['composer']['indie'];
    expect(rate.low).toBe(2000);
    expect(rate.high).toBe(25000);
    expect(rate.unionMin).toBeNull();
    expect(rate.displacementRisk).toBe('high');
  });

  it('has correct screenwriter professional union minimum', () => {
    const rate = RATE_TABLE['screenwriter']['professional'];
    expect(rate.unionMin).toBe(77495);
  });

  it('has correct voice_actor indie union minimum', () => {
    const rate = RATE_TABLE['voice_actor']['indie'];
    expect(rate.unionMin).toBe(249);
  });
});

describe('computeBudget (spec fixture)', () => {
  const fixtureInput = {
    role: 'composer' as const,
    budgetTier: 'indie' as const,
    projectScope: '10-minute short film score, 3 themes',
    currentBudgetForRole: 1500,
  };

  it('produces exact expected output from spec fixture', () => {
    const result = computeBudget(fixtureInput);
    expect(result).toEqual({
      roleName: 'composer',
      budgetTier: 'indie',
      humanCostRange: { low: 2000, high: 25000 },
      unionMinimum: null,
      displacementRisk: 'high',
      userBudgetDelta: { low: -23500, high: -500 },
    });
  });

  it('produces roleName = composer', () => {
    const result = computeBudget(fixtureInput);
    expect(result.roleName).toBe('composer');
  });

  it('produces budgetTier = indie', () => {
    const result = computeBudget(fixtureInput);
    expect(result.budgetTier).toBe('indie');
  });

  it('produces humanCostRange from rate table lookup', () => {
    const result = computeBudget(fixtureInput);
    expect(result.humanCostRange).toEqual({ low: 2000, high: 25000 });
  });

  it('produces unionMinimum = null for composer indie', () => {
    const result = computeBudget(fixtureInput);
    expect(result.unionMinimum).toBeNull();
  });

  it('produces displacementRisk = high', () => {
    const result = computeBudget(fixtureInput);
    expect(result.displacementRisk).toBe('high');
  });

  it('produces userBudgetDelta.low = -23500 (1500 - 25000)', () => {
    const result = computeBudget(fixtureInput);
    expect(result.userBudgetDelta!.low).toBe(-23500);
  });

  it('produces userBudgetDelta.high = -500 (1500 - 2000)', () => {
    const result = computeBudget(fixtureInput);
    expect(result.userBudgetDelta!.high).toBe(-500);
  });

  it('produces null userBudgetDelta when currentBudgetForRole not provided', () => {
    const inputWithoutBudget = {
      role: 'composer' as const,
      budgetTier: 'indie' as const,
      projectScope: '10-minute short film score',
    };
    const result = computeBudget(inputWithoutBudget);
    expect(result.userBudgetDelta).toBeNull();
  });

  it('validates output against BudgetOutput schema', () => {
    const result = computeBudget(fixtureInput);
    const validation = BudgetOutput.safeParse(result);
    expect(validation.success).toBe(true);
  });

  it('produces positive delta when budget exceeds market rate', () => {
    const overBudgetInput = {
      role: 'composer' as const,
      budgetTier: 'indie' as const,
      projectScope: 'Film score',
      currentBudgetForRole: 30000,
    };
    const result = computeBudget(overBudgetInput);
    expect(result.userBudgetDelta!.low).toBe(5000);  // 30000 - 25000
    expect(result.userBudgetDelta!.high).toBe(28000); // 30000 - 2000
  });
});
