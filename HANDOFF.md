# HANDOFF -- Sandbox

**Date:** 2026-05-17
**Branch:** master (writers-room-council: feat/per-project-voice-override)
**Phase:** Compound complete -- Per-Project Voice Override build (run 043)

## Current State

Per-Project Voice Override feature implemented for Writers Room Council app.
11 commits on `feat/per-project-voice-override` branch in `writers-room-council/`.
401 tests passing. 4 review agents ran (security, TypeScript, data integrity,
flow trace). All P1s fixed. 3 pre-existing issues deferred.

## Key Artifacts

| Phase | Location |
|-------|----------|
| Plan | writers-room-council/docs/plans/2026-05-17-feat-per-project-voice-override-plan.md |
| Brainstorm | writers-room-council/docs/brainstorms/2026-05-17-per-project-fingerprint-and-flow-fix-brainstorm.md |
| Solution | docs/solutions/2026-05-17-per-project-voice-override-build.md |
| BUILD_TRACKING | BUILD_TRACKING.md |
| Reports | docs/reports/043/ |
| Self-Audit | docs/reports/043/self-audit.md |

## Deferred Items

- [043-W1] Opening tag escaping in escape.ts (pre-existing gap, future hardening)
- [043-W2] Unescaped draft/userResponse in council.ts fallback path (pre-existing, HIGH)
- [043-W3] PATCH endpoint for editing overrides post-creation (next iteration)
- [043-W4] `string | null` narrowing for description/intent/protecting (type-safety PR)
- [043-W5] Route-level regression test (voice-merge-regression.test.ts) not built
- [043-W6] Self-audit key format divergence (043-D vs 043-W, now reconciled)
- Safety profiles (from prior work)
- Project-local hooks (from prior work)
- Square webhook signature key (from prior work)

## Three Questions

1. **Hardest decision?** NULL-by-default with placeholders vs pre-filled values. Placeholders preserve "skip entirely" UX promise and reduce staleness risk.
2. **What was rejected?** Snapshot-on-create (contradicts skip-entirely), full per-project fingerprint (too much friction), genre-only override (doesn't solve the real problem).
3. **Least confident about?** Whether users will discover the collapsed voice section. If beta feedback shows low usage, consider expanding by default or moving above genre.

## Prompt for Next Session

```
Read HANDOFF.md for context. This is the sandbox project.
Writers Room Council: feat/per-project-voice-override branch has 11 commits
ready for merge. Migration 015 needs to be applied to remote Supabase before
deploy. Pre-existing prompt injection gaps (draft/userResponse in council.ts
fallback, opening tags) should be addressed in a follow-up hardening pass.
```
