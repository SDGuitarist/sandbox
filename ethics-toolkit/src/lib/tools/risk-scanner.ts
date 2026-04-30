/**
 * Project Risk Scanner -- deterministic scoring engine.
 *
 * Re-exports computeRiskScore from the schema module (which implements
 * Steps 1-7 exactly per Section 4 Tool 3).
 *
 * This file is the canonical import point for tool agents and API routes.
 */

export {
  computeRiskScore,
  type RiskScannerInputType,
  type RiskScannerOutputType,
} from '@/lib/schemas/risk-scanner';
