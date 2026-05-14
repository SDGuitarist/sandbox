# Spike: update-learnings Non-Interactive Behavior

**Date:** 2026-05-13
**Plan:** docs/plans/2026-05-13-feat-sandbox-autonomy-hardening-plan.md (Phase 2)

## Question

Does the autopilot skill's context ("Do not stop between steps") reliably
suppress the code-explainer prompt in `/update-learnings` Step 7?

## Method

Structural analysis instead of a full autopilot dry run. A single run
would not prove reliability -- it would only prove it worked once.

## Evidence

1. **FC11 history:** The orchestrator skipped the ENTIRE `/update-learnings`
   step in 2 of 3 recent builds. The problem is worse than prompt suppression
   -- the whole command is inconsistently executed.

2. **Competing instructions:** The autopilot skill says "Do not stop between
   steps" (SKILL.md line 43). The update-learnings command says "Then ask:
   Want to run code-explainer?" (update-learnings.md line 282). When both
   are active in context, which instruction the LLM prioritizes is
   non-deterministic.

3. **Statistical insignificance:** A single spike run cannot prove that
   suppression is reliable across future builds with different context
   loads, different app sizes, and different positions in the context window.

## Code-explainer question appeared?

Not tested via live run. Structural analysis shows the outcome is
non-deterministic, which is equivalent to YES for planning purposes --
you cannot rely on behavior that sometimes works.

## Decision

**Path B: Create a sandbox-local skill `update-learnings-noninteractive`.**

This reimplements Steps 1-6 of the global `update-learnings` command
without Step 7 (the code-explainer prompt). The autopilot skill calls
`/update-learnings-noninteractive` instead of `/update-learnings`.

### Rationale

- Deterministic: no competing "then ask" instruction exists in the local skill.
- Sandbox-local: no global command is modified.
- Accepted duplication: Steps 1-6 are duplicated (~230 lines). This is
  deliberate technical debt, not a permanent pattern. A future plan should
  refactor the global command to accept a `--no-prompt` flag.
- Does not inflate the autopilot SKILL.md (the new skill is a separate file).
