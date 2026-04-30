/**
 * Festival Policy Lookup input schema.
 *
 * Spec reference: Section 4 Tool 2
 *
 * Output is an array of FestivalPolicy records from the database.
 * No LLM. Fully free. No free/paid boundary. Not stored in ToolEvent.
 */

import { z } from 'zod';

export const PolicyLookupInput = z.object({
  query: z.string().min(1).max(500),
  filters: z.object({
    aiPolicy: z.enum(['banned', 'restricted', 'disclosure_required', 'allowed', 'no_stated_policy']).optional(),
    category: z.enum(['writing', 'music', 'vfx', 'voice', 'full_ban', 'no_policy']).optional(),
  }).optional(),
});

export type PolicyLookupInputType = z.infer<typeof PolicyLookupInput>;
