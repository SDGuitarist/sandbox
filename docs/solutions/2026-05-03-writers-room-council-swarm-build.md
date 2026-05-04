---
title: "Writers Room Council: 13-Agent Swarm Build with 8-Agent Review"
date: 2026-05-03
type: solution
tags: [swarm, autopilot, next-js, supabase, anthropic-api, multi-agent-review, prompt-porting, inline-annotation]
project: writers-room-council
origin: docs/plans/2026-05-03-feat-writers-room-council-app-spec.md
build_method: autopilot
agents: 13
review_agents: 8
phases: 4
files: 85
tests: 205
commits: 17
p1_findings: 6
p2_findings: 7
---

# Writers Room Council: 13-Agent Swarm Build with 8-Agent Review

## What Was Built

A Next.js 15 + Supabase + Anthropic API writing council app with:
- Magic link auth with beta whitelist enforcement via auth hook
- Phase 0 onboarding (8-input fingerprint wizard + scoring floor)
- Seed Council (5-beat Champion/Contrarian sequence with streaming)
- Standard Council (5 AI voice characters + verdict + handoff)
- Returning Writer Protocol (revision evaluation against prior verdict)
- Editor mode (15-principle analysis: 2 deterministic + 13 LLM with Crystal filter)
- Inline annotation UI (controlled React, editable-on-accept)
- Editorial signature learning (accept/reject weighted principle profile)
- Rate limiting via Supabase RPC (not in-memory -- Vercel serverless safe)
- Mock mode for every LLM call path

85 TypeScript/TSX files, 4 SQL migrations, 205 tests, ~17K lines.

## Build Architecture

### Phasing Strategy (4 phases, 13 agents)

| Phase | Agents | Dependency Chain |
|-------|--------|-----------------|
| 1: Foundation | scaffold-auth + database (parallel) -> schemas -> phase0-ui | Schema barrel is the gate |
| 2: Editor | editor-core, editor-ui, signature-dashboard (parallel) | All read from Phase 1 exports |
| 3: Council | council-prompts -> seed-council + standard-council-rwp + project-flow (parallel) | Prompts must exist before modes |
| 4: Polish | demo-prep + polish (parallel) | Reads everything |

**Key insight:** The schemas agent (1.5) runs AFTER database but BEFORE any UI agent. This creates a single source of truth (Zod barrel file) that all subsequent agents import from. Without this gate, swarm agents invent incompatible data shapes.

### Dual SDK Pattern

- **Vercel AI SDK (`ai` package):** All streaming responses (Council voices). `streamText()` + `toDataStreamResponse()`.
- **Anthropic SDK (`@anthropic-ai/sdk`):** Non-streaming structured calls (Scoring Floor, Editor analysis). `client.messages.create()` with structured output.
- **Rule:** Never mix SDKs for the same call. Streaming = Vercel AI SDK. Non-streaming structured = Anthropic SDK.

### Two-Pass Editor Architecture

1. **Pre-LLM deterministic pass:** Regex scan for em-dashes (P7) and banned vocabulary (P8). Zero tokens. Always classified as `voice_protection` -- bypasses Crystal filter.
2. **LLM judgment pass:** Principles 1-6, 9, 11-15 analyzed by Opus 4.6. Each suggestion classified as `structural_catch`, `voice_formalization`, or `voice_protection`.
3. **Crystal filter (code, not prompt):** Suppress `voice_formalization` suggestions when `register_leveling = false`. Generate-then-filter pattern: LLM tags classification, deterministic code suppresses. Auditable and reliable.

## What Broke (Review Findings)

### 6 P1 Findings (All Fixed)

| Finding | Root Cause | Fix |
|---------|-----------|-----|
| `current_step` INTEGER in SQL, TEXT in app | Spec said INTEGER, agents wrote strings. Schema-code mismatch. | Changed column to TEXT |
| Rate limit RPC param mismatch + fails open | editor-core agent assumed 3-param signature, database agent implemented 2-param. Classic cross-agent seam. | Removed extra param, fail closed |
| `draftVersionId` stores `editorSessionId` | `EditorAnalysisResponse` didn't include `draftVersionId`. Two agents (council, rwp) independently stored the wrong ID. | Added field to schema + response |
| Missing `<Database>` generic on Supabase clients | scaffold-auth agent didn't pass generic. Entire type system unused. | Added `<Database>` to all 3 factories |
| PATCH handlers skip Zod validation | POST handlers used safeParse, PATCH handlers used `as` cast. Different agents wrote POST vs PATCH. | Created CouncilVerdictRequest schema |
| HSTS header missing | scaffold-auth agent set 3/4 security headers. Missed HSTS. | Added to next.config.ts |

### 7 P2 Findings (All Fixed)

| Finding | Root Cause | Fix |
|---------|-----------|-----|
| RWP GET endpoint missing | rwp/page.tsx makes GET, route only exports POST/PATCH. Cross-agent: UI agent assumed endpoint, API agent didn't build it. | Added GET handler |
| Seed beat off-by-one | protectionQuestion on beat 3, should be beat 2. Prompt agent and mock agent both drifted from spec. | Fixed ternary + mock |
| Fingerprint fields bare in prompts | Draft wrapped in XML tags, but fingerprint/project fields interpolated raw. 3 agents wrote 3 different injection warnings. | Wrapped all in XML tags |
| Draft version missing ownership check | RLS should catch it, but API layer didn't tie draft to project. | Added `.eq('project_id', projectId)` |
| handoff_state template string | `council_complete_${verdict}` -- if LLM returns unexpected value, CHECK constraint silently rejects. | Replaced with lookup map |
| rate_limits/allowed_emails missing write-deny RLS | Only SELECT policies existed. Direct INSERT possible. | Added deny-all write policies |
| Seed route auth pattern diverges | Fetches without user_id filter, returns 403. Other routes use in-query filter, return 404. | Standardized to in-query pattern |

## Patterns That Worked

### 1. Schema Barrel as Swarm Contract

The `src/lib/schemas/index.ts` barrel file re-exports every Zod schema. All agents import from this single path. The spec's Export Names Table prescribed exact names. Result: zero import name mismatches across 13 agents.

**Why it works:** Prescriptive specs (showing exact code shape) produce identical implementations. Descriptive specs (explaining what's needed) produce N different implementations.

### 2. Mock Mode from Day 1

Every LLM call has a mock fallback returning valid Zod-parsed data. Pattern: `if (!hasApiKey()) return getMockData()`. One mock system (not per-phase). App works fully without ANTHROPIC_API_KEY.

**Why it matters:** Agents can build and test in parallel without API access. Review agents can verify flow without spending tokens.

### 3. Verification Pipeline After Each Phase

After each phase merge: (1) ownership gate, (2) spec contract check (grep export names), (3) cross-boundary wiring check, (4) TypeScript check, (5) test suite. Catches integration failures before they compound.

### 4. Prompt Injection XML Sandboxing

All user-supplied content wrapped in named XML tags: `<user_document>`, `<writer_fingerprint>`, `<project_calibration>`, `<writing_sample>`. Injection warning references all tag names explicitly. Review caught that fingerprint fields were originally bare -- 3 agents wrote 3 different injection patterns.

**Lesson:** Standardize injection defense in a shared-rules file imported by all prompt builders. Don't let each agent invent its own warning text.

## Patterns That Failed

### 1. Cross-Agent Type Assumptions

The biggest failure class: agents assume schema shapes that don't match. `current_step` (INTEGER vs TEXT), `draftVersionId` (not in response), `p_user_id` (not in RPC signature). Unit tests pass within each agent's scope. Integration fails at the seam.

**Defense:** The spec's Cross-Boundary Wiring Table caught some of these, but not all. The table needs to include **parameter types**, not just function names.

### 2. POST vs PATCH Consistency

POST handlers got Zod validation because the spec prescribed it. PATCH handlers were added by agents without spec coverage and used `as` casts. Any route not explicitly spec'd will be built with shortcuts.

**Defense:** Spec must prescribe validation for ALL HTTP methods on every route, not just the primary one.

### 3. Fail-Open Rate Limiting

Rate limiter failed open on DB errors. This is the "safe" default for availability, but catastrophic for cost protection on API routes. Prior solution doc (Producer Brief) warned about this exact pattern on Vercel serverless.

**Defense:** Solution doc violations are P1. The learnings-researcher agent caught this -- confirming it's the highest-ROI review agent.

## Risk Resolution

| Risk (from Feed-Forward) | Status | How Resolved |
|--------------------------|--------|-------------|
| Inline annotation editable-on-accept quality | Mitigated | Controlled React (no contenteditable). Plain text -> splitTextByAnnotations() -> styled spans. Popover for suggestions. Inline input on accept. P3 performance concern (100K char ownerMap) flagged for useMemo. |
| Prompt porting from Claude Projects to API | Mitigated | Context assembly pattern: voice persona + framework rules + fingerprint + project + transcript + draft. 81 regression tests verify prompt structure. Golden transcript fixtures check for key patterns (verb catch, identification not declaration). |

## Metrics

- **Build time:** 4 phases, ~25 minutes total agent execution
- **Review time:** 8 agents in parallel, ~3 minutes
- **P1 fix time:** ~10 minutes (6 fixes)
- **P2 fix time:** ~8 minutes (7 fixes)
- **Test stability:** 205/205 throughout (tests updated for behavior changes, never deleted)
- **Zero-prompt achieved:** Yes -- full autopilot build + review + fix cycle with no manual intervention

## References

- Spec: `docs/plans/2026-05-03-feat-writers-room-council-app-spec.md`
- Prior art: `docs/solutions/2026-04-30-ethics-toolkit-platform-build.md` (format precedent)
- Swarm patterns: `docs/solutions/2026-04-09-autopilot-swarm-orchestration.md`
- Spec convergence: `docs/solutions/2026-04-30-spec-convergence-loop.md`
- Review synthesis: `~/Projects/gigprep/docs/solutions/2026-02-27-code-review-synthesis-patterns.md`

## Feed-Forward

- **Hardest decision:** Fixing P1s inline vs. deferring to a dedicated fix session. Chose inline because the fixes were surgical (1-3 lines each) and the context was hot.
- **Rejected alternatives:** Separate fix branches per P1 (too much overhead for small fixes), deferring Database generic to P3 (cascading impact too high).
- **Least confident:** The `<Database>` generic addition surfaces ~25 TS errors across components that use `as` casts. These are P3 (the casts worked before, they just aren't needed now). Whether to clean them all up in one pass or let them resolve organically as those files are touched.
