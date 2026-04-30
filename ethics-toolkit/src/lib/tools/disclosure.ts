/**
 * AI Disclosure Generator -- deterministic checklist + template generation.
 *
 * Spec reference: Section 4 Tool 1
 *
 * Takes validated DisclosureInput data and produces:
 * - An 8-item checklist with satisfaction logic
 * - Disclosure fields summary
 * - A deterministic template text string
 */

import {
  type DisclosureInputType,
  type DisclosureOutputType,
  computeChecklist,
} from '@/lib/schemas/disclosure';

/**
 * Generate the deterministic disclosure output from validated input.
 *
 * This function:
 * 1. Computes the 8-item checklist using the shared computeChecklist function
 * 2. Extracts disclosure fields (project title, departments, tools, union status)
 * 3. Builds a deterministic template text with placeholders filled in
 */
export function generateDisclosure(input: DisclosureInputType): DisclosureOutputType {
  const checklist = computeChecklist(input);

  // Collect unique departments and tools across all usage areas
  const departments = [...new Set(input.aiUsageAreas.map((a) => a.department))];
  const toolsUsed = [...new Set(input.aiUsageAreas.flatMap((a) => a.toolsUsed))];

  const disclosureFields = {
    projectTitle: input.projectTitle,
    departments,
    toolsUsed,
    unionStatus: input.unionStatus,
    generatedAt: new Date().toISOString(),
  };

  // Build the deterministic template text
  const templateText = buildTemplateText(input, departments, toolsUsed);

  return {
    checklist,
    disclosureFields,
    templateText,
  };
}

/**
 * Build a deterministic disclosure template from project data.
 *
 * This fills in concrete values from the input rather than leaving placeholders.
 * The template covers all disclosed AI usage areas with their details.
 */
function buildTemplateText(
  input: DisclosureInputType,
  departments: string[],
  toolsUsed: string[]
): string {
  const lines: string[] = [];

  lines.push(`AI DISCLOSURE STATEMENT`);
  lines.push(`Project: ${input.projectTitle}`);
  lines.push(``);
  lines.push(`This project used AI tools in the following departments: ${departments.join(', ')}.`);
  lines.push(`Tools used: ${toolsUsed.join(', ')}.`);
  lines.push(`Union status: ${formatUnionStatus(input.unionStatus)}.`);
  lines.push(``);

  if (input.distributionTargets && input.distributionTargets.length > 0) {
    lines.push(`Distribution targets: ${input.distributionTargets.join(', ')}.`);
    lines.push(``);
  }

  lines.push(`DETAILED AI USAGE BY DEPARTMENT:`);
  lines.push(``);

  for (const area of input.aiUsageAreas) {
    lines.push(`Department: ${area.department}`);
    lines.push(`  Description: ${area.description}`);
    lines.push(`  Tools: ${area.toolsUsed.join(', ')}`);
    lines.push(`  Usage level: ${area.usageLevel}`);

    if (area.humanSupervisor) {
      lines.push(`  Human supervisor: ${area.humanSupervisor}`);
    }

    lines.push(`  Training data acknowledged: ${area.trainingDataAcknowledged ? 'Yes' : 'No'}`);

    if (area.department === 'voice') {
      lines.push(`  Consent documented: ${area.consentDocumented ? 'Yes' : 'No'}`);
    }

    if (area.compensationNotes) {
      lines.push(`  Compensation notes: ${area.compensationNotes}`);
    }

    lines.push(`  Union compliance checked: ${area.unionComplianceChecked ? 'Yes' : 'No'}`);
    lines.push(``);
  }

  lines.push(`Guidance, not legal advice. Consult an entertainment attorney for legal counsel.`);

  return lines.join('\n');
}

function formatUnionStatus(status: string): string {
  const labels: Record<string, string> = {
    sag_aftra: 'SAG-AFTRA',
    wga: 'WGA',
    iatse: 'IATSE',
    non_union: 'Non-Union',
    unknown: 'Unknown',
  };
  return labels[status] || status;
}
