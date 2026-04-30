/**
 * Fixture test for AI Disclosure Generator (Tool 1).
 *
 * Verifies satisfaction logic with the explicit fields from the spec fixture.
 * Spec reference: Section 4 Tool 1
 */

import { describe, it, expect } from 'vitest';
import { DisclosureInput, DisclosureOutput, DisclosureAI, computeChecklist } from '../../src/lib/schemas/disclosure';

describe('DisclosureInput schema', () => {
  it('validates the spec fixture input', () => {
    const input = {
      projectTitle: 'Midnight Signal',
      aiUsageAreas: [
        {
          department: 'music' as const,
          description: 'Background score generated from text prompts',
          toolsUsed: ['Suno v4'],
          usageLevel: 'generative' as const,
          trainingDataAcknowledged: false,
          consentDocumented: false,
          unionComplianceChecked: false,
        },
        {
          department: 'storyboard' as const,
          description: 'Initial frame sketches from scene descriptions',
          toolsUsed: ['Midjourney v6'],
          usageLevel: 'assistive' as const,
          humanSupervisor: 'Jane Park',
          trainingDataAcknowledged: false,
          consentDocumented: false,
          unionComplianceChecked: false,
        },
      ],
      distributionTargets: ['Sundance', 'SXSW'],
      unionStatus: 'non_union' as const,
    };

    const result = DisclosureInput.safeParse(input);
    expect(result.success).toBe(true);
  });

  it('rejects empty projectTitle', () => {
    const input = {
      projectTitle: '',
      aiUsageAreas: [
        {
          department: 'music',
          description: 'Test',
          toolsUsed: ['Tool'],
          usageLevel: 'generative',
        },
      ],
      unionStatus: 'non_union',
    };

    const result = DisclosureInput.safeParse(input);
    expect(result.success).toBe(false);
  });

  it('rejects empty aiUsageAreas', () => {
    const input = {
      projectTitle: 'Test',
      aiUsageAreas: [],
      unionStatus: 'non_union',
    };

    const result = DisclosureInput.safeParse(input);
    expect(result.success).toBe(false);
  });

  it('rejects empty toolsUsed array', () => {
    const input = {
      projectTitle: 'Test',
      aiUsageAreas: [
        {
          department: 'music',
          description: 'Test',
          toolsUsed: [],
          usageLevel: 'generative',
        },
      ],
      unionStatus: 'non_union',
    };

    const result = DisclosureInput.safeParse(input);
    expect(result.success).toBe(false);
  });
});

describe('DisclosureOutput schema', () => {
  it('validates a well-formed output', () => {
    const output = {
      checklist: [
        { item: 'AI tools identified', satisfied: true, requirement: 'List every AI tool used by name and version' },
      ],
      disclosureFields: {
        projectTitle: 'Test',
        departments: ['music'],
        toolsUsed: ['Suno v4'],
        unionStatus: 'non_union',
        generatedAt: new Date().toISOString(),
      },
      templateText: 'This project uses AI tools.',
    };

    const result = DisclosureOutput.safeParse(output);
    expect(result.success).toBe(true);
  });
});

describe('DisclosureAI schema', () => {
  it('validates a disclosure text within bounds', () => {
    const ai = { disclosureText: 'A'.repeat(100) };
    const result = DisclosureAI.safeParse(ai);
    expect(result.success).toBe(true);
  });

  it('rejects text under 50 characters', () => {
    const ai = { disclosureText: 'Too short' };
    const result = DisclosureAI.safeParse(ai);
    expect(result.success).toBe(false);
  });
});

describe('computeChecklist (spec fixture)', () => {
  const fixtureInput = {
    projectTitle: 'Midnight Signal',
    aiUsageAreas: [
      {
        department: 'music' as const,
        description: 'Background score generated from text prompts',
        toolsUsed: ['Suno v4'],
        usageLevel: 'generative' as const,
        trainingDataAcknowledged: false,
        consentDocumented: false,
        unionComplianceChecked: false,
      },
      {
        department: 'storyboard' as const,
        description: 'Initial frame sketches from scene descriptions',
        toolsUsed: ['Midjourney v6'],
        usageLevel: 'assistive' as const,
        humanSupervisor: 'Jane Park',
        trainingDataAcknowledged: false,
        consentDocumented: false,
        unionComplianceChecked: false,
      },
    ],
    distributionTargets: ['Sundance', 'SXSW'],
    unionStatus: 'non_union' as const,
  };

  const expectedChecklist = [
    { item: 'AI tools identified', satisfied: true, requirement: 'List every AI tool used by name and version' },
    { item: 'Departments disclosed', satisfied: true, requirement: 'Identify which departments used AI (writing, music, VFX, etc.)' },
    { item: 'Usage level specified', satisfied: true, requirement: 'For each department, state whether AI was assistive or generative' },
    { item: 'Human oversight documented', satisfied: false, requirement: 'Name the human who supervised/approved each AI output' },
    { item: 'Training data acknowledged', satisfied: false, requirement: 'Note whether AI models were trained on copyrighted material' },
    { item: 'Consent obtained', satisfied: true, requirement: 'If voice/likeness AI was used, document consent from all parties' },
    { item: 'Compensation addressed', satisfied: false, requirement: 'If AI replaced a human role, document fair compensation considerations' },
    { item: 'Union compliance checked', satisfied: true, requirement: 'Verify AI usage complies with applicable union agreements' },
  ];

  it('produces exact expected checklist from spec fixture', () => {
    const result = computeChecklist(fixtureInput);
    expect(result).toEqual(expectedChecklist);
  });

  it('Item 1: true -- both items have non-empty toolsUsed', () => {
    const result = computeChecklist(fixtureInput);
    expect(result[0].satisfied).toBe(true);
  });

  it('Item 2: true -- aiUsageAreas has 2 items', () => {
    const result = computeChecklist(fixtureInput);
    expect(result[1].satisfied).toBe(true);
  });

  it('Item 3: true -- both items have usageLevel set', () => {
    const result = computeChecklist(fixtureInput);
    expect(result[2].satisfied).toBe(true);
  });

  it('Item 4: false -- music item has no humanSupervisor', () => {
    const result = computeChecklist(fixtureInput);
    expect(result[3].satisfied).toBe(false);
  });

  it('Item 5: false -- both items have trainingDataAcknowledged = false', () => {
    const result = computeChecklist(fixtureInput);
    expect(result[4].satisfied).toBe(false);
  });

  it('Item 6: true -- no voice department listed', () => {
    const result = computeChecklist(fixtureInput);
    expect(result[5].satisfied).toBe(true);
  });

  it('Item 7: false -- music item has usageLevel generative but no compensationNotes', () => {
    const result = computeChecklist(fixtureInput);
    expect(result[6].satisfied).toBe(false);
  });

  it('Item 8: true -- unionStatus is non_union', () => {
    const result = computeChecklist(fixtureInput);
    expect(result[7].satisfied).toBe(true);
  });

  it('Item 6 is false when voice department present without consent', () => {
    const inputWithVoice = {
      ...fixtureInput,
      aiUsageAreas: [
        ...fixtureInput.aiUsageAreas,
        {
          department: 'voice' as const,
          description: 'AI voice cloning',
          toolsUsed: ['ElevenLabs'],
          usageLevel: 'generative' as const,
          trainingDataAcknowledged: false,
          consentDocumented: false,
          unionComplianceChecked: false,
        },
      ],
    };
    const result = computeChecklist(inputWithVoice);
    expect(result[5].satisfied).toBe(false);
  });

  it('Item 6 is true when voice department present with consent', () => {
    const inputWithVoiceConsent = {
      ...fixtureInput,
      aiUsageAreas: [
        ...fixtureInput.aiUsageAreas,
        {
          department: 'voice' as const,
          description: 'AI voice cloning',
          toolsUsed: ['ElevenLabs'],
          usageLevel: 'generative' as const,
          trainingDataAcknowledged: false,
          consentDocumented: true,
          unionComplianceChecked: false,
        },
      ],
    };
    const result = computeChecklist(inputWithVoiceConsent);
    expect(result[5].satisfied).toBe(true);
  });

  it('Item 8 is false when union affiliated and not all items checked', () => {
    const inputWithUnion = {
      ...fixtureInput,
      unionStatus: 'sag_aftra' as const,
    };
    const result = computeChecklist(inputWithUnion);
    expect(result[7].satisfied).toBe(false);
  });

  it('Item 7 is true when all generative items have compensationNotes', () => {
    const inputWithCompensation = {
      ...fixtureInput,
      aiUsageAreas: fixtureInput.aiUsageAreas.map((a) =>
        a.usageLevel === 'generative'
          ? { ...a, compensationNotes: 'Fair compensation provided' }
          : a
      ),
    };
    const result = computeChecklist(inputWithCompensation);
    expect(result[6].satisfied).toBe(true);
  });
});
