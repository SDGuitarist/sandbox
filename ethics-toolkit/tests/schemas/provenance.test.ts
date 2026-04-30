/**
 * Fixture test for AI Provenance Chain Builder (Tool 4).
 *
 * Verifies percentageHuman = 33 from the spec fixture.
 * Spec reference: Section 4 Tool 4
 */

import { describe, it, expect } from 'vitest';
import { ProvenanceInput, ProvenanceOutput, computeProvenance } from '../../src/lib/schemas/provenance';

describe('ProvenanceInput schema', () => {
  it('validates the spec fixture input', () => {
    const input = {
      projectTitle: 'Midnight Signal',
      entries: [
        { department: 'Music', taskDescription: 'Background score', attribution: 'ai_generated', toolUsed: 'Suno v4' },
        { department: 'Storyboard', taskDescription: 'Initial frame sketches', attribution: 'ai_assisted', toolUsed: 'Midjourney v6', humanContributor: 'Jane Park' },
        { department: 'Editing', taskDescription: 'Final cut assembly', attribution: 'human_made', humanContributor: 'Tom Rivera' },
      ],
    };

    const result = ProvenanceInput.safeParse(input);
    expect(result.success).toBe(true);
  });

  it('rejects empty projectTitle', () => {
    const input = {
      projectTitle: '',
      entries: [
        { department: 'Music', taskDescription: 'Test', attribution: 'human_made' },
      ],
    };

    const result = ProvenanceInput.safeParse(input);
    expect(result.success).toBe(false);
  });

  it('rejects empty entries array', () => {
    const input = {
      projectTitle: 'Test',
      entries: [],
    };

    const result = ProvenanceInput.safeParse(input);
    expect(result.success).toBe(false);
  });

  it('rejects invalid attribution value', () => {
    const input = {
      projectTitle: 'Test',
      entries: [
        { department: 'Music', taskDescription: 'Test', attribution: 'invalid' },
      ],
    };

    const result = ProvenanceInput.safeParse(input);
    expect(result.success).toBe(false);
  });
});

describe('ProvenanceOutput schema', () => {
  it('validates a well-formed output', () => {
    const output = {
      projectTitle: 'Test',
      entries: [
        { department: 'Music', taskDescription: 'Test', attribution: 'human_made' as const },
      ],
      summary: {
        totalEntries: 1,
        humanMade: 1,
        aiAssisted: 0,
        aiGenerated: 0,
        percentageHuman: 100,
      },
      generatedAt: new Date().toISOString(),
    };

    const result = ProvenanceOutput.safeParse(output);
    expect(result.success).toBe(true);
  });
});

describe('computeProvenance (spec fixture)', () => {
  const fixtureInput = {
    projectTitle: 'Midnight Signal',
    entries: [
      { department: 'Music', taskDescription: 'Background score', attribution: 'ai_generated' as const, toolUsed: 'Suno v4' },
      { department: 'Storyboard', taskDescription: 'Initial frame sketches', attribution: 'ai_assisted' as const, toolUsed: 'Midjourney v6', humanContributor: 'Jane Park' },
      { department: 'Editing', taskDescription: 'Final cut assembly', attribution: 'human_made' as const, humanContributor: 'Tom Rivera' },
    ],
  };

  it('produces totalEntries = 3', () => {
    const result = computeProvenance(fixtureInput);
    expect(result.summary.totalEntries).toBe(3);
  });

  it('produces humanMade = 1', () => {
    const result = computeProvenance(fixtureInput);
    expect(result.summary.humanMade).toBe(1);
  });

  it('produces aiAssisted = 1', () => {
    const result = computeProvenance(fixtureInput);
    expect(result.summary.aiAssisted).toBe(1);
  });

  it('produces aiGenerated = 1', () => {
    const result = computeProvenance(fixtureInput);
    expect(result.summary.aiGenerated).toBe(1);
  });

  it('produces percentageHuman = 33', () => {
    const result = computeProvenance(fixtureInput);
    expect(result.summary.percentageHuman).toBe(33);
  });

  it('produces exact expected summary from spec fixture', () => {
    const result = computeProvenance(fixtureInput);
    expect(result.summary).toEqual({
      totalEntries: 3,
      humanMade: 1,
      aiAssisted: 1,
      aiGenerated: 1,
      percentageHuman: 33,
    });
  });

  it('preserves projectTitle from input', () => {
    const result = computeProvenance(fixtureInput);
    expect(result.projectTitle).toBe('Midnight Signal');
  });

  it('preserves all entry fields', () => {
    const result = computeProvenance(fixtureInput);
    expect(result.entries).toHaveLength(3);
    expect(result.entries[0].department).toBe('Music');
    expect(result.entries[0].toolUsed).toBe('Suno v4');
    expect(result.entries[1].humanContributor).toBe('Jane Park');
    expect(result.entries[2].humanContributor).toBe('Tom Rivera');
  });

  it('generates a valid ISO 8601 date string', () => {
    const result = computeProvenance(fixtureInput);
    expect(() => new Date(result.generatedAt)).not.toThrow();
    expect(new Date(result.generatedAt).toISOString()).toBe(result.generatedAt);
  });

  it('validates output against ProvenanceOutput schema', () => {
    const result = computeProvenance(fixtureInput);
    const validation = ProvenanceOutput.safeParse(result);
    expect(validation.success).toBe(true);
  });

  it('produces percentageHuman = 100 when all entries are human_made', () => {
    const allHumanInput = {
      projectTitle: 'All Human',
      entries: [
        { department: 'Editing', taskDescription: 'Cut', attribution: 'human_made' as const },
        { department: 'Music', taskDescription: 'Score', attribution: 'human_made' as const },
      ],
    };
    const result = computeProvenance(allHumanInput);
    expect(result.summary.percentageHuman).toBe(100);
  });

  it('produces percentageHuman = 0 when no entries are human_made', () => {
    const noHumanInput = {
      projectTitle: 'All AI',
      entries: [
        { department: 'Music', taskDescription: 'Score', attribution: 'ai_generated' as const },
        { department: 'VFX', taskDescription: 'Effects', attribution: 'ai_assisted' as const },
      ],
    };
    const result = computeProvenance(noHumanInput);
    expect(result.summary.percentageHuman).toBe(0);
  });
});
