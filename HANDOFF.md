# HANDOFF -- Sandbox

**Date:** 2026-05-13
**Branch:** master
**Phase:** Compound complete -- Workshop Registration Hub build finished

## Current State

Workshop Registration Hub build (run 042) complete. 8-agent cross-stack swarm (Flask + Express), 35 files, ~1,750 lines. All verification gates passed. Review found 30 issues (8 P1, 12 P2, 8 P3); all P1s fixed, 4 P2s fixed. 3 new failure classes added to agent-pitfalls.md. Learnings propagated.

## Key Artifacts

| Phase | Location |
|-------|----------|
| Brainstorm | docs/brainstorms/2026-05-13-workshop-registration-hub-brainstorm.md |
| Plan (deepened + converged) | docs/plans/2026-05-13-feat-workshop-registration-hub-plan.md |
| Reports | docs/reports/042/ (ownership-gate, contract-check, smoke-test, spec-consistency-check) |
| Solution | docs/solutions/2026-05-13-workshop-registration-hub-swarm-build.md |
| BUILD_TRACKING | BUILD_TRACKING.md |

## Review Fixes Pending (P2)

1. Admin brute-force protection (rate limiting on admin endpoints)
2. CSRF protection on registration form
3. Send-reminders CLI parallelization (ThreadPoolExecutor)
4. Supabase client singleton thread safety (double-checked locking)
5. Admin dashboard missing CSS styles
6. HTML-escape user names in email templates
7. Square API timeout configuration
8. N+1 query optimization in admin endpoint

## Deferred Items (from prior work)

- Safety profiles (offline-safe, online-build, prod-sensitive)
- Project-local hooks
- spec-contract-checker tool mismatch (read-only vs write-report)
- Square webhook signature key (needs ngrok setup)

## Three Questions

1. **Hardest decision?** Whether to run Agent 9 (integration-wiring) in a worktree or defer to post-assembly. Deferred -- spec-contract-checker and assembly-fix agents served the same purpose.
2. **What was rejected?** Running agents in phased order (1, then 2-6, then 7-8) -- launched all 8 in parallel since worktrees provide isolation.
3. **Least confident about?** Transaction boundary fixes. Removing conn.commit() from update_status() changes the contract for ALL callers. If any caller forgot to add their own commit, data silently stays uncommitted.

## Prompt for Next Session

```
Read HANDOFF.md for context. This is the sandbox project.
Workshop Registration Hub (run 042) is complete with 8 remaining P2 review items.
Next: either fix P2s or move to a new build. The Square webhook
signature key still needs ngrok setup for end-to-end payment testing.
```
