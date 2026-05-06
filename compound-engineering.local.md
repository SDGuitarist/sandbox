# Review Context — Ethics Toolkit

## Risk Chain

**Brainstorm risk:** "Cross-cutting concerns (auth, realtime, LLM, payments, email) at platform scale have never been tested in a swarm."

**Plan mitigation:** 4-phase sequential build (foundation -> tools -> realtime -> integration) with schema pre-gate. Export Name Table + Cross-Boundary Wiring Section prescribed.

**Work risk (from Feed-Forward):** Integration seam failures despite prescriptive spec -- agents produced correct isolated code but wrong imports, dead wiring, and non-atomic operations at boundaries.

**Review resolution:** 28 unique findings (12 P0, 12 P1-R1, 4 P1-R2) from 5 agents. All P0/P1 resolved across 3 commits. 15 P2s deferred. Top finding: import mismatches (13 files) from agents making independently reasonable naming decisions.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| lib/ai/route-factory.ts | NEW: extracted from 3 duplicate routes | Single point of failure for all AI calls |
| lib/realtime/use-workshop-channel.ts | NEW: shared channel hook | Channel lifecycle management |
| lib/email/send.ts | HMAC token signing + retry fix | Crypto correctness, timing safety |
| supabase/migrations/005_p1_fixes.sql | RLS, FKs, triggers, constraints | Data integrity, cascading effects |
| supabase/migrations/004_atomic_upvote_and_claim.sql | Atomic RPCs | Concurrency correctness |
| app/api/cron/process-emails/route.ts | Atomic claim-before-send | Double-send prevention |

## Plan Reference

`docs/plans/2026-04-30-ethics-toolkit-platform-spec.md`
