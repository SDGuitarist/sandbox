# Codex Handoff: Writers Room Council App Spec Review

**Date:** 2026-05-03
**Phase:** Plan (pre-autopilot)
**Purpose:** External spec review before autopilot swarm launch. Convergence loop round 1. Minimum 2 Codex rounds required before autopilot.

---

## Instructions for Codex

Read these files in order:

1. `docs/plans/2026-05-03-feat-writers-room-council-app-spec.md` (THE SPEC - primary review target)
2. `docs/brainstorms/2026-05-02-writers-room-council-app-brainstorm.md` (origin brainstorm with all decisions)

## Review the spec for:

### 1. Cross-Section Contradictions (Highest Priority)
Prior spec work (Run 033) proved that AI tools miss contradictions internally consistent within each section but incompatible across sections. Check:

- Does every field referenced in the Zod schemas (Section 4) exist in the SQL schema (Section 3)? Check every field name, every type.
- Does every file in the Swarm Agent Assignment (after Section 13) appear in exactly one agent's creates list? No duplicates, no orphans.
- Does every export in the Export Names Table have a matching function/const in an agent's creates list?
- Does every entry in the Cross-Boundary Wiring Section reference agents that exist and files that are in those agents' creates lists?
- Does the Data Ownership Table match the RLS policies? Every writer listed should have INSERT/UPDATE permission. Every reader should have SELECT.
- Do the Phase gates reference features that are actually built in that phase? (e.g., Phase 1 gate requires Scoring Floor, is the Scoring Floor API actually created in Phase 1?)
- Does the TranscriptEntry schema (Section 4.1b) cover all the entry types that the Council modes (Sections 4.2-4.4) would generate?

### 2. Schema Completeness
- Are there Zod schemas for every API route's input AND output?
- Does the `update_signature_after_decision` RPC function handle all edge cases? (What if the principle_weights key doesn't exist yet? What if p_decision is not one of the valid values?)
- Is the `rate_limits` table included in migration 001 alongside the other tables?
- Does the `CouncilVerdict` Zod schema include `whatSurvives` (which has a corresponding DB column)?

### 3. Swarm Agent Safety
- Can all Phase 1 agents complete without dependencies on Phase 2 files?
- Can all Phase 2 agents complete without dependencies on Phase 3 files?
- Does the `phase0-ui` agent's note about creating a minimal `lib/ai/client.ts` create a conflict when `editor-core` creates the full version in Phase 2?
- Does `council-prompts` (Phase 3) modifying `lib/prompts/phase0.ts` (created by Phase 1) violate the file ownership model?
- Are there any implicit imports between agents in the same phase that are not declared in the reads list?

### 4. Brainstorm Fidelity
- Does the spec implement all 20 resolved decisions from the brainstorm?
- Does the spec implement all 12 autopilot build requirements from the brainstorm?
- Does the spec implement all 10 architectural constraints from the brainstorm?
- Are there any brainstorm decisions that the spec contradicts or omits?
- Does the spec's Feed-Forward section match the brainstorm's Feed-Forward?

### 5. Security Review
- Is the `auth.uid()` check in the RPC function sufficient to prevent privilege escalation?
- Are admin routes properly gated?
- Does the RLS policy on `editor_suggestions` (nested subquery through 3 tables) perform acceptably, or should it use the `auth.user_project_ids()` helper function?
- Is the CSRF protection (Content-Type + Origin header check) adequate for cookie-based auth?
- Is the prompt injection mitigation (XML sandboxing + system prompt instruction) sufficient?

### 6. Spec Readiness for Autopilot
- Is the spec prescriptive enough for swarm agents to build without making design decisions?
- Are there any sections where an agent would need to "figure out" how something works?
- Are the mock responses specified clearly enough for agents to implement them?
- Are the golden transcript regression fixtures defined with enough detail for agents to write tests?

## Output Format

```
## Findings

### P0 (Must fix before autopilot launch)
- [finding with section reference]

### P1 (Should fix, risk if ignored)
- [finding with section reference]

### P2 (Worth noting, not blocking)
- [finding with section reference]

## Claude Code Fix Prompt
[If P0s or P1s exist, provide a prompt for Claude Code to address them before launching autopilot.]
```

Prioritize cross-section contradictions. Those are the ones that become integration failures in the swarm build.
