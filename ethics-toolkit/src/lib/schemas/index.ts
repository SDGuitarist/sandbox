/**
 * Barrel export for all shared Zod schemas.
 *
 * Spec reference: Section 4 (all 5 tools) + Section 10 (ToolEvent)
 */

// Shared interface
export type { ToolType, ToolEvent } from './tool-event';

// Tool 1: AI Disclosure Generator
export {
  DisclosureInput,
  DisclosureOutput,
  DisclosureAI,
  CHECKLIST_ITEMS,
  computeChecklist,
} from './disclosure';
export type {
  DisclosureInputType,
  DisclosureOutputType,
  DisclosureAIType,
} from './disclosure';

// Tool 2: Festival Policy Lookup
export { PolicyLookupInput } from './policy-lookup';
export type { PolicyLookupInputType } from './policy-lookup';

// Tool 3: Project Risk Scanner
export {
  RiskScannerInput,
  RiskScannerOutput,
  RiskAI,
  computeRiskScore,
} from './risk-scanner';
export type {
  RiskScannerInputType,
  RiskScannerOutputType,
  RiskAIType,
} from './risk-scanner';

// Tool 4: AI Provenance Chain Builder
export {
  ProvenanceInput,
  ProvenanceOutput,
  computeProvenance,
} from './provenance';
export type {
  ProvenanceInputType,
  ProvenanceOutputType,
} from './provenance';

// Tool 5: Budget vs. Ethics Calculator
export {
  BudgetInput,
  BudgetOutput,
  BudgetAI,
  RATE_TABLE,
  computeBudget,
} from './budget';
export type {
  BudgetInputType,
  BudgetOutputType,
  BudgetAIType,
} from './budget';
