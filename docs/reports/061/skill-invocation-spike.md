# Skill Invocation Spike — Run 061

**Date:** 2026-06-01
**Purpose:** Verify that the Skill tool works from inside a spawned agent,
confirming the tail-runner architecture (agent invokes skills directly).

## Setup

Spawned a general-purpose agent with `mode: "bypassPermissions"`. Tested
whether three skills are accessible and invocable from that nested context.

## Results

| # | Skill | Accessible | Loaded | Result |
|---|-------|-----------|--------|--------|
| 1 | `compound-engineering:workflows:review` | YES | YES | PASS |
| 2 | `compound-engineering:workflows:compound` | YES | YES | PASS |
| 3 | `update-learnings-noninteractive` | YES | YES | PASS |

## Details

All three skills loaded their full instruction sets successfully. The Skill
tool is fully accessible from within a spawned agent context. Each skill
returned its complete definition (multi-agent review instructions, compound
orchestration, learnings propagation steps).

## Conclusion

**SPIKE RESULT: ALL_PASS**

Proceed with the current architecture: the tail-runner agent invokes
`/workflows:review`, `/workflows:compound`, and
`/update-learnings-noninteractive` directly via the Skill tool. No fallback
to orchestrator-invoked skills is needed.

## Impact on Plan

No architecture revision required. The plan's primary design (tail-runner
invokes skills) is confirmed. The Feed-Forward risk ("Whether /workflows:review
and /workflows:compound work when invoked from inside a spawned agent") is
resolved: they do.
