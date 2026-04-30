/**
 * AI Provenance Chain Builder schemas.
 *
 * Spec reference: Section 4 Tool 4
 *
 * No LLM integration for this tool.
 */

import { z } from 'zod';

export const ProvenanceInput = z.object({
  projectTitle: z.string().min(1).max(200),
  entries: z.array(z.object({
    department: z.string().min(1).max(100),
    taskDescription: z.string().min(1).max(500),
    attribution: z.enum(['human_made', 'ai_assisted', 'ai_generated']),
    toolUsed: z.string().max(200).optional(),
    humanContributor: z.string().max(200).optional(),
    notes: z.string().max(500).optional(),
  })).min(1),
});

export type ProvenanceInputType = z.infer<typeof ProvenanceInput>;

export const ProvenanceOutput = z.object({
  projectTitle: z.string(),
  entries: z.array(z.object({
    department: z.string(),
    taskDescription: z.string(),
    attribution: z.enum(['human_made', 'ai_assisted', 'ai_generated']),
    toolUsed: z.string().optional(),
    humanContributor: z.string().optional(),
    notes: z.string().optional(),
  })),
  summary: z.object({
    totalEntries: z.number(),
    humanMade: z.number(),
    aiAssisted: z.number(),
    aiGenerated: z.number(),
    percentageHuman: z.number(),
  }),
  generatedAt: z.string(),
});

export type ProvenanceOutputType = z.infer<typeof ProvenanceOutput>;

/**
 * Compute the provenance output from the input.
 * percentageHuman = round((humanMade / totalEntries) * 100)
 */
export function computeProvenance(input: ProvenanceInputType): ProvenanceOutputType {
  const totalEntries = input.entries.length;
  const humanMade = input.entries.filter((e) => e.attribution === 'human_made').length;
  const aiAssisted = input.entries.filter((e) => e.attribution === 'ai_assisted').length;
  const aiGenerated = input.entries.filter((e) => e.attribution === 'ai_generated').length;
  const percentageHuman = Math.round((humanMade / totalEntries) * 100);

  return {
    projectTitle: input.projectTitle,
    entries: input.entries.map((e) => ({
      department: e.department,
      taskDescription: e.taskDescription,
      attribution: e.attribution,
      toolUsed: e.toolUsed,
      humanContributor: e.humanContributor,
      notes: e.notes,
    })),
    summary: {
      totalEntries,
      humanMade,
      aiAssisted,
      aiGenerated,
      percentageHuman,
    },
    generatedAt: new Date().toISOString(),
  };
}
