# Codex Handoff — Decision Review: How to Verify Plan A's Rare-Failure Fixes

**Phase:** plan (Plan A — Reliability fixes) — resolving the one open decision before plan structure is locked
**Created:** 2026-06-06
**Type:** focused decision review + recommendation (NOT a full plan/code review)

---

## Copy-paste prompt for Codex

```
Read these files first for project context:
  - CLAUDE.md                  (repo operating contract: autonomy classes, Required
                                Artifacts, Bash Command Rules, Escalation Rules)
  - docs/brainstorms/2026-06-06-autopilot-orchestration-hardening-brainstorm.md
                               (full brainstorm; see "Open Questions" → "How do we verify
                                a rare-failure fix?")
  - docs/plans/HANDOFF-orchestration-hardening-planning.md   (the open decision is restated
                                under "Open decision to resolve during planning")

DECISION TO MAKE: Plan A has two reliability fixes that prevent failures which do NOT occur
on a normal autopilot run, so passive observation cannot confirm them. Verification needs a
reproduction. Recommend HOW Plan A should verify them. This shapes whether Plan A's EARS
acceptance tests are automated or manual, so a clear, decisive recommendation matters.

The two fixes:
  Item 1 — Disk-verify delegated STATUS. Step 18w (and the swarm-runner handler) must read
    the named artifact's on-disk STATUS line (e.g. self-audit.md line 1) as authoritative,
    treat the agent's echoed wire STATUS as only a hint, and treat the artifact being
    missing / unreadable / STALE (wrong run-id or older than this run) as a genuine FAIL.
    The risk it guards: an agent finishes all work but forgets to echo its Output Contract;
    a naive "no STATUS line → FAIL" reading would fail a successful run. The risk it must
    NOT introduce: "trust the artifact blindly," which opens a stale-STATUS false-PASS hole.
    THIS CHANGE TOUCHES THE RUN'S TERMINAL PASS/FAIL GATE.
  Item 2 — worker-roster.md at spawn. The orchestrator writes
    role→agentId→branch→worktree-path to disk immediately after the parallel swarm spawn,
    before any completion arrives. Worktree branches are named worktree-agent-<agentId>,
    not the role, so on a mid-spawn context death the mapping (which otherwise lives only in
    volatile orchestrator context) is lost. This is WRITE-ONLY INSURANCE — zero behavioral
    change to the running pipeline; it only adds a file.

The three options on the table:
  A. HYBRID — failure-injection harness for item 1 only (it changes the terminal gate);
     documented manual repro for item 2 (zero-risk write-only insurance).
  B. FULL HARNESSES — automated failure-injection for both items (item 2's harness would
     simulate a mid-spawn context death and assert the roster reconstructs the mapping).
  C. MANUAL REPRO ONLY — both items verified by a documented runbook, no harness code.

Constraints to weigh:
  - Repo Bash Command Rules (CLAUDE.md): one command per call; no cd&&, no for-loops, no
    python3 -c, no &&/; chaining. Any harness must be runnable under these rules (likely a
    Write-tool-created script invoked in one Bash call).
  - The pipeline is a Claude Code skill (.claude/skills/autopilot/SKILL.md) + agent
    markdown files (.claude/agents/*.md) driven by an LLM orchestrator — it is NOT a
    conventional unit-testable codebase. Consider how a "harness" even executes against an
    LLM-driven control flow: does it test the STATUS-read/normalize routine in isolation
    (feed it fixture artifacts), or does it require a full run? Be concrete about what the
    harness actually exercises.
  - Owner is a beginner developer who prefers simple solutions, but item 1 is the only
    change in either plan that can silently flip a run's final verdict, so a false-PASS
    here is a high-consequence, low-visibility failure.
  - TAIL_SYNC_POINT: item 1's logic is duplicated in SKILL.md and tail-runner.md and must
    be mirrored in both. Factor this into the verification recommendation (does the harness
    need to cover both paths, or does de-duplicating the logic first reduce the test surface?).

Answer concretely:
  1. Pick A, B, or C (or a better option) and justify in 3–5 sentences.
  2. For item 1, specify the EXACT fixture cases the verification must cover and the
     expected verdict for each (at minimum: missing artifact; stale/wrong-run-id artifact;
     genuine-incomplete artifact; valid-PASS artifact with no wire STATUS). Define "stale"
     precisely enough to implement (run-id match? timestamp vs run-start? both?).
  3. State what the item-1 harness actually executes (isolated STATUS-read routine vs full
     run) and whether it must cover both the SKILL.md and tail-runner.md paths.
  4. For item 2, give the exact manual-repro steps (or harness assertions) and the
     pass criteria.
  5. Flag any way the chosen approach could produce a false sense of safety (a test that
     passes without actually exercising the false-PASS hole).

Output: a decisive recommendation (A/B/C) + the verification spec for items 1 and 2 in
enough detail to drop straight into Plan A's "## Acceptance Tests" (EARS) and "Verification
Commands" sections.
```

---

## Why this handoff exists

The verification approach is the one open decision the planning HANDOFF says must be
resolved *during* Plan A, and it determines whether the acceptance tests are executable or
documented-only. Rather than the human picking blind, we get Codex's fresh-context
recommendation first — especially valuable because the question has a non-obvious wrinkle:
the pipeline is LLM-driven, so "what does a harness even run against?" is itself part of the
decision, not just an implementation detail.

**After Codex responds:** fold its recommendation into Plan A's acceptance-test design, then
continue the plan flow (plan → deepen → self-review → the post-plan Codex review the user
already scheduled).
