/**
 * AI Disclosure Generator schemas.
 *
 * Spec reference: Section 4 Tool 1
 */

import { z } from 'zod';

export const DisclosureInput = z.object({
  projectTitle: z.string().min(1).max(200),
  aiUsageAreas: z.array(z.object({
    department: z.enum(['writing', 'music', 'vfx', 'voice', 'storyboard', 'editing', 'sound_design', 'colorist', 'other']),
    description: z.string().min(1).max(500),
    toolsUsed: z.array(z.string().min(1)).min(1),
    usageLevel: z.enum(['assistive', 'generative']),
    humanSupervisor: z.string().max(200).optional(),
    trainingDataAcknowledged: z.boolean().default(false),
    consentDocumented: z.boolean().default(false),
    compensationNotes: z.string().max(500).optional(),
    unionComplianceChecked: z.boolean().default(false),
  })).min(1),
  distributionTargets: z.array(z.string()).optional(),
  unionStatus: z.enum(['sag_aftra', 'wga', 'iatse', 'non_union', 'unknown']),
});

export type DisclosureInputType = z.infer<typeof DisclosureInput>;

export const DisclosureOutput = z.object({
  checklist: z.array(z.object({
    item: z.string(),
    satisfied: z.boolean(),
    requirement: z.string(),
  })),
  disclosureFields: z.object({
    projectTitle: z.string(),
    departments: z.array(z.string()),
    toolsUsed: z.array(z.string()),
    unionStatus: z.string(),
    generatedAt: z.string(),
  }),
  templateText: z.string(), // deterministic template with placeholders
});

export type DisclosureOutputType = z.infer<typeof DisclosureOutput>;

export const DisclosureAI = z.object({
  disclosureText: z.string().min(50).max(2000),
});

export type DisclosureAIType = z.infer<typeof DisclosureAI>;

/**
 * Checklist item definitions with their exact requirements from the spec.
 * Order matters -- these are the 8 items in the exact spec order.
 */
export const CHECKLIST_ITEMS = [
  { item: 'AI tools identified', requirement: 'List every AI tool used by name and version' },
  { item: 'Departments disclosed', requirement: 'Identify which departments used AI (writing, music, VFX, etc.)' },
  { item: 'Usage level specified', requirement: 'For each department, state whether AI was assistive or generative' },
  { item: 'Human oversight documented', requirement: 'Name the human who supervised/approved each AI output' },
  { item: 'Training data acknowledged', requirement: 'Note whether AI models were trained on copyrighted material' },
  { item: 'Consent obtained', requirement: 'If voice/likeness AI was used, document consent from all parties' },
  { item: 'Compensation addressed', requirement: 'If AI replaced a human role, document fair compensation considerations' },
  { item: 'Union compliance checked', requirement: 'Verify AI usage complies with applicable union agreements' },
] as const;

/**
 * Compute the satisfied status for each checklist item based on the input.
 *
 * Satisfaction logic (from spec):
 * 1. "AI tools identified" -- satisfied if every item has a non-empty toolsUsed array.
 * 2. "Departments disclosed" -- satisfied if aiUsageAreas has at least one item.
 * 3. "Usage level specified" -- satisfied if every item has usageLevel set.
 * 4. "Human oversight documented" -- satisfied if every item has a non-empty humanSupervisor.
 * 5. "Training data acknowledged" -- satisfied if every item has trainingDataAcknowledged === true.
 * 6. "Consent obtained" -- satisfied if no voice department is listed, OR every voice item has consentDocumented === true.
 * 7. "Compensation addressed" -- satisfied if every item with usageLevel === 'generative' has a non-empty compensationNotes.
 * 8. "Union compliance checked" -- satisfied if unionStatus is non_union or unknown, OR every item has unionComplianceChecked === true.
 */
export function computeChecklist(input: DisclosureInputType): Array<{
  item: string;
  satisfied: boolean;
  requirement: string;
}> {
  const areas = input.aiUsageAreas;

  const satisfied: boolean[] = [
    // 1. AI tools identified -- every item has a non-empty toolsUsed array
    areas.every((a) => a.toolsUsed.length > 0),

    // 2. Departments disclosed -- aiUsageAreas has at least one item
    areas.length >= 1,

    // 3. Usage level specified -- every item has usageLevel set
    areas.every((a) => a.usageLevel !== undefined && a.usageLevel !== null),

    // 4. Human oversight documented -- every item has a non-empty humanSupervisor
    areas.every((a) => typeof a.humanSupervisor === 'string' && a.humanSupervisor.length > 0),

    // 5. Training data acknowledged -- every item has trainingDataAcknowledged === true
    areas.every((a) => a.trainingDataAcknowledged === true),

    // 6. Consent obtained -- no voice department listed, OR every voice item has consentDocumented === true
    areas.filter((a) => a.department === 'voice').length === 0 ||
    areas.filter((a) => a.department === 'voice').every((a) => a.consentDocumented === true),

    // 7. Compensation addressed -- every generative item has a non-empty compensationNotes
    areas.filter((a) => a.usageLevel === 'generative').length === 0 ||
    areas.filter((a) => a.usageLevel === 'generative').every((a) => typeof a.compensationNotes === 'string' && a.compensationNotes.length > 0),

    // 8. Union compliance checked -- unionStatus is non_union or unknown, OR every item has unionComplianceChecked === true
    input.unionStatus === 'non_union' || input.unionStatus === 'unknown' ||
    areas.every((a) => a.unionComplianceChecked === true),
  ];

  return CHECKLIST_ITEMS.map((ci, i) => ({
    item: ci.item,
    satisfied: satisfied[i],
    requirement: ci.requirement,
  }));
}
