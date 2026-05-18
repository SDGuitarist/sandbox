---
title: Per-Project Voice Override + Auto-Navigate to Council
date: 2026-05-17
project: writers-room-council
type: feature
build_method: solo
run_id: "043"
agents_used: 1 (orchestrator)
review_agents: security-sentinel, kieran-typescript-reviewer, data-integrity-guardian, flow-trace-reviewer
findings: 1 P1 fixed, 5 P2 fixed, 3 deferred (pre-existing)
tests_added: 16 (merge-voice: 3, escape: 9, schema: 4)
tests_total: 401
---

# Per-Project Voice Override + Auto-Navigate to Council

## Problem

Writers working across genres (comedy pilot + dramatic feature) get the same
voice calibration for both projects because the fingerprint is account-level.
After creating a project, users land on the project dashboard instead of
the council submission page.

## Solution

4 nullable voice override columns on the `projects` table. NULL means "use
account fingerprint" (zero-regression for existing projects). A shared
`mergeVoiceOverride` utility applies the null-coalescing fallback across all
5 council code paths. The project form shows fingerprint values as placeholder
text (not pre-filled), so untouched fields remain NULL.

Auto-navigate: project creation redirects to `/projects/[id]/council`.

## Architecture Decisions

1. **NULL-by-default (placeholders, not pre-filled):** Fields the user doesn't
   touch stay NULL and use fingerprint directly. Only explicit typing creates
   an override. This reduces staleness risk and matches the "skip entirely"
   UX promise.

2. **Shared escape module:** `src/lib/prompts/escape.ts` covers all 6 XML
   sandbox tags. Applied to all fingerprint + project interpolation sites in
   council.ts and seed.ts (system prompt). Also applied to seed userMessage
   (found during security review).

3. **Pick types anchored to VoicePromptParams:** `mergeVoiceOverride` returns
   `VoicePromptParams['fingerprint']` — if the prompt interface changes, the
   merge function fails to compile. `SeedBeatParams.fingerprint` references
   the same type to prevent drift.

4. **Zod transform for normalization:** `optionalVoiceField` uses explicit
   length check (not falsy coalescing) to handle empty → null. The form sends
   raw strings; Zod is the single source of truth for normalization.

5. **Idempotent migration:** `ADD COLUMN IF NOT EXISTS` + `EXCEPTION WHEN
   duplicate_object` for CHECK constraints. Re-runnable in local dev.

## Risk Resolution

**Feed-Forward risk:** "Override fields may go stale if user updates account
fingerprint later."

**What happened:** The placeholder approach reduces this — most fields will be
NULL (using fingerprint directly). Only explicit overrides can go stale, and
those are intentional user choices. Editing overrides post-creation is scoped
for a future iteration. The risk is accepted for beta.

**What was learned:** NULL-by-default with placeholder display is a general
pattern for "optional override" features. It avoids snapshot-on-create
staleness and reduces DB storage. The merge utility pattern
(`project.field ?? fingerprint.field`) is reusable for any layered-config
feature.

## Review Findings (Notable)

1. **Security P1 (fixed):** seed.ts userMessage interpolated project
   description/intent/protecting without escaping — prompt injection vector
   for beat 1. Fixed by applying `escapeForXmlSandbox()`.

2. **Data Integrity P1 (fixed):** Migration lacked idempotency guards. Fixed
   with `IF NOT EXISTS` + exception handling.

3. **TypeScript P2 (fixed):** `SeedBeatParams.fingerprint` was a structural
   duplicate of `VoicePromptParams['fingerprint']`. Replaced with type reference.

4. **Security P2-3 (fixed):** Zod transform used `||` which treats "0" as
   falsy. Fixed with explicit `length > 0` check.

## Deferred Items

| Item | Why Deferred | Ticket/Next |
|------|--------------|-------------|
| Opening tag escaping in escape.ts | Pre-existing gap, not introduced by this PR | Future hardening pass |
| Unescaped draft/userResponse in council.ts fallback | Pre-existing, affects raw-text submissions only | Future hardening pass |
| PATCH endpoint for editing overrides post-creation | Explicitly out of scope per plan | Next iteration |
| `string | null` narrowing for description/intent/protecting | Pre-existing type mismatch across all routes | Separate type-safety PR |

## Key Files

- `src/lib/prompts/escape.ts` — shared XML escape (6 tags)
- `src/lib/council/merge-voice.ts` — null-coalescing merge utility
- `src/lib/schemas/api-contracts.ts` — Zod optionalVoiceField transform
- `src/app/api/projects/route.ts` — INSERT with voice columns
- `src/app/api/council/{standard,seed,rwp}/route.ts` — 5 paths use merge
- `src/app/(app)/projects/new/` — page + form with fingerprint placeholders
- `supabase/migrations/015_project_voice_overrides.sql` — idempotent migration

## Commits

10 commits on `feat/per-project-voice-override`:
1. Shared XML escape module
2. Migration + types
3. Merge utility
4. Schema + API route
5. Council routes use merge (all 5 paths)
6. UI + fingerprint placeholders + auto-navigate
7. Project page select + tests
8. Test fix (case-insensitive escape expectation)
9. Review fix: migration idempotency + Zod transform tests
10. Security fix: seed userMessage escape + Zod "0" edge case
11. TS review fix: type reference + form payload + details collapsed
