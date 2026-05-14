# HANDOFF -- Sandbox

**Date:** 2026-05-13
**Branch:** master
**Phase:** Plan complete -- READY FOR AUTOPILOT LAUNCH

## Current State

Workshop Registration Hub plan is spec-converged and ready for autopilot launch. 4 Codex passes, 11 total findings, all resolved. Zero P0 contradictions remain. This is a 9-agent cross-stack swarm build (Flask + Express, SQLite + Supabase, Square + Resend) -- the most ambitious sandbox build to date.

## Key Artifacts

| Phase | Location |
|-------|----------|
| Brainstorm | docs/brainstorms/2026-05-13-workshop-registration-hub-brainstorm.md |
| Plan (deepened + converged) | docs/plans/2026-05-13-feat-workshop-registration-hub-plan.md |

## Convergence History

| Pass | Findings | Status |
|------|----------|--------|
| 1st Codex | 7 (admin ownership, Square ID, proxy codes, register contract, webhook idempotency, cancel flow, minor fixes) | All resolved |
| 2nd Codex | 3 (admin realtime P0, register_attendee docstring, webhook payload) | All resolved |
| 3rd Codex | 1 (ADMIN_PASSWORD leaked to browser JS) | Resolved |
| 4th Codex | 0 | **CLEAN -- GO for autopilot** |

## Pre-Build Setup Required

Before launching autopilot, set up these external services:

1. **Square sandbox credentials** -- Create app in Square Developer Console, get sandbox access token, location ID, webhook signature key
2. **Resend API key** -- Create account at resend.com, get API key
3. **Supabase project** -- Create NEW project, get URL + service role key + anon key, run the Supabase schema SQL from the plan

## Deferred Items (from prior work)

- Safety profiles (offline-safe, online-build, prod-sensitive)
- Project-local hooks
- `--no-prompt` flag for global update-learnings
- spec-contract-checker tool mismatch (read-only vs write-report)

## Prompt for Next Session

```
Read HANDOFF.md and docs/plans/2026-05-13-feat-workshop-registration-hub-plan.md.

This is a 9-agent cross-stack swarm build -- Workshop Registration Hub.
Plan is spec-converged (4 Codex passes, 0 P0s). Ready for autopilot launch.

Pre-build: set up Square sandbox, Resend API key, and new Supabase project
(see plan Dependencies section). Then run autopilot with swarm: true.

Key risk (Feed-Forward): Cross-stack API contract between Flask and Express
is novel. The spec convergence loop scrutinized it hard -- contract is clean
but this is the first cross-stack swarm build ever attempted.
```
