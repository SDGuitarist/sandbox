/**
 * AI Provenance Chain Builder -- deterministic summary + duplicate detection.
 *
 * Re-exports computeProvenance from the schema module and adds
 * duplicate detection logic.
 *
 * Spec reference: Section 4 Tool 4
 *  - percentageHuman = round((humanMade / totalEntries) * 100)
 *  - Duplicate detection: warn if same department + taskDescription exists.
 *    Do not block.
 */

export {
  computeProvenance,
  type ProvenanceInputType,
  type ProvenanceOutputType,
} from '@/lib/schemas/provenance';

import type { ProvenanceInputType } from '@/lib/schemas/provenance';

export interface DuplicateWarning {
  department: string;
  taskDescription: string;
  indices: number[];
}

/**
 * Detect duplicate entries where the same department + taskDescription
 * combination appears more than once.
 *
 * Returns an array of warnings (empty if no duplicates).
 */
export function detectDuplicates(input: ProvenanceInputType): DuplicateWarning[] {
  const seen = new Map<string, number[]>();

  input.entries.forEach((entry, index) => {
    const key = `${entry.department.toLowerCase()}::${entry.taskDescription.toLowerCase()}`;
    const existing = seen.get(key);
    if (existing) {
      existing.push(index);
    } else {
      seen.set(key, [index]);
    }
  });

  const warnings: DuplicateWarning[] = [];
  for (const [, indices] of seen) {
    if (indices.length > 1) {
      const firstEntry = input.entries[indices[0]];
      warnings.push({
        department: firstEntry.department,
        taskDescription: firstEntry.taskDescription,
        indices,
      });
    }
  }

  return warnings;
}
