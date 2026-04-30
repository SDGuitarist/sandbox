/**
 * Shared Interface Specification for all persisted tool outputs.
 * Festival Policy Lookup is read-only and does NOT create ToolEvent records.
 *
 * Spec reference: Section 10 -- Shared Interface Specification
 */

export type ToolType = 'DISCLOSURE' | 'RISK' | 'PROVENANCE' | 'BUDGET';

export interface ToolEvent<TPayload, TAI = never> {
  eventId: string;             // UUID, client-generated
  schemaVersion: 1;
  workshopSessionId?: string;
  anonymousSessionId: string;
  userId?: string;
  toolType: ToolType;
  deterministicPayload: TPayload;
  probabilisticPayload?: TAI;  // stored as JSONB, null when unavailable
  createdAt: string;           // ISO 8601
}
