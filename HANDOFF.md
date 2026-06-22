# HANDOFF — Sandbox

**Date:** 2026-06-21
**Branch:** master (in sync with origin, working tree clean)
**Phase:** **G1 risk-tiered firebreak — PLAN COMPLETE (deepened, v1 thinned), awaiting external Plan Review (Codex).**
Next: paste the Codex handoff prompt (in the plan, "Codex Handoff Prompt" section) into Codex → bring findings back → apply fixes → Claude second pass → `/workflows:work` on the thinned v1.

## Current State

Today's session (manual) produced three governance/knowledge artifacts and one
completed brainstorm, all committed and pushed to master:

1. **Master extraction** of all unattended-swarm/autopilot/guardrails/evals work —
   `docs/solutions/2026-06-21-unattended-swarm-autopilot-master-extraction.md`.
2. **Governance analysis** scoring the autopilot system against Google DeepMind's
   *Three Layers of Agent Security* (June 2026) — surfaced 5 gaps (G1–G5) —
   `docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md`
   (+ source PDF in the same dir).
3. **G1 brainstorm** (refined, 2 review passes, plan-ready) —
   `docs/brainstorms/2026-06-21-g1-risk-tiered-firebreak-brainstorm.md`.

**G1 in one line:** a risk-tiered firebreak that enforces CLAUDE.md's existing
"Forbidden Actions" contract (currently unenforced under
`dangerouslySkipPermissions`) by classifying actions and **deferring** the
binding/irreversible tail to the `todos/` approval queue, keeping the safe
majority unattended.

## Decisions already locked in the G1 brainstorm

- **Escalation = defer-and-continue** via the existing `todos/` + `resolve-todos`
  queue (human = async batch reviewer, not a 2am babysitter).
- **Classifier = deterministic denylist (v1) → hybrid w/ AI advisory (Phase 2).**
  Deterministic always dispositive; AI only ever flags blind spots.
- **Merge-to-`main` = RED** (deferred for approval; v1 does NOT redesign assembly).
- **RED tier** = git force/shared-push + merge-to-main + prod-DB destructive +
  out-of-repo deletes + external sends + deploy + external-MCP-writes (default-deny)
  + package removal. **GREEN** = everything local in the worktree **+ the sanctioned
  learnings-propagation out-of-repo writes** (carve-out — must not be deferred).

## PLAN phase output (2026-06-21, session 2 — DONE)

1. **Spike GREEN (riskiest assumption verified first).** Empirically confirmed on
   claude 2.1.173 that a **PreToolUse hook fires AND blocks above
   `dangerouslySkipPermissions`** — for both the main session and a Task-spawned
   subagent. Mechanism viable; no fallback (agent-brief/tool-wrapper) needed.
   Residual = worktree-subagent firing + hook placement → gated as Step 0.
   Proof: `docs/spikes/2026-06-21-g1-pretooluse-hook-under-bypass-spike.md`.
2. **Plan written, passed both gates** (plan-quality-gate = GO, ears-validator =
   PASS), then **deepened by 5 adversarial reviewers** (security, architecture,
   simplicity, data-integrity, performance) and **thinned to a safety-complete v1**.
3. **Both brainstorm open questions resolved:** (Q1) human-only approval via a
   glob-isolated `todos/approvals/` queue (NOT extending `resolve-todos`, which runs
   unattended); (Q2) no new run status needed.
4. **Deepening Review changed the design** (table R1–R8 at top of plan):
   - **R1** hook placement flipped **project → GLOBAL** + positive-control probe.
   - **R2** the graceful **deferred-merge wiring CUT from v1** — the swarm-runner
     merge is LOCAL and autopilot never pushes, so "merge-to-main" wasn't actually
     irreversible; the draft's pointer-commit reproduced FC51 base-drift and risked
     a silent false-`PIPELINE_PASS`. v1 merge-RED fires only on a `master`/shared
     target and just defers + one HANDOFF line.
   - **R3/R4** threat model restated honestly (guards honest mistakes + bounds
     outward blast radius, NOT adversarial-proof) + evasion hardening (git `-C`
     normalization, indirection-defer, outward allowlist incl. `gh api`/`npm
     publish`/`nc`/`ssh`, `mcp__*` read-only allowlist).
   - **R5** queue hardened: gitignore `todos/approvals/`, collision-free atomic
     uuid filenames (the `NNN` sequence races across 31 workers).
   - **R6** token-grep fast-path (python cold-start tax ≈ 7–12 min/run).
   - **R8** `/approve` skill deferred to v2; `resolve-todos` guard stays.
5. **User decisions (2026-06-21):** fully cut the status-mapping sliver (no v1
   status engineering for a deferred master-merge); next phase = Plan Review (Codex).
6. **v1 scope = Step 0 → Phase 1 → Phase 2.** v2 (deferred, documented): graceful
   merge disposition, `/approve` skill, AI advisory pass.

## Key Artifacts (this session)

| Item | Location |
|------|----------|
| **G1 PLAN (deepened, v1 thinned)** | **docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md** |
| **G1 spike (riskiest assumption, GREEN)** | **docs/spikes/2026-06-21-g1-pretooluse-hook-under-bypass-spike.md** |
| Codex Plan-Review prompt | "Codex Handoff Prompt" section in the plan above |
| G1 brainstorm (plan input) | docs/brainstorms/2026-06-21-g1-risk-tiered-firebreak-brainstorm.md |
| Governance scorecard (G1–G5) | docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md |
| Framework source PDF | docs/governance/three-layers-of-agent-security-deepmind-2026-06.pdf |
| Master extraction (system reference) | docs/solutions/2026-06-21-unattended-swarm-autopilot-master-extraction.md |
| Existing approval-queue pattern | todos/ + .claude/skills/resolve-todos/ |
| Permission bypass switch | .claude/settings.local.json (`dangerouslySkipPermissions`) |
| Forbidden Actions contract | CLAUDE.md ("Forbidden Actions", "Bash Command Rules") |

## Deferred Backlog (priority order)

0. **[ACTIVE → PLAN REVIEW] G1 risk-tiered firebreak** — plan done, deepened, v1
   thinned. Next is external Plan Review (Codex prompt ready), then apply fixes →
   Claude second pass → `/workflows:work` on v1 (Step 0 → Phase 1 → Phase 2).
1. **FC51 orchestrator rule** — ensure the converged spec is at the worktree base
   before swarm spawn (cherry-pick the spec-update commit into worktree bases, OR
   inline-inject spec sections into briefs). Live fragility that bit Run 070.
   (Partly addressed by the 2026-06-21 `check_spec_provenance.py` BASEREF-FRESH
   change — that's the *detection* half; the orchestrator *repair* rule remains.)
2. **Track A `P-extract`** — refactor `swarm-runner.md` cherry-pick prose into a
   shared callable so Track A (FC51) earns a real EXERCISED fixture row. Overlaps #1.
3. **Suite adoption decision** — wire `validate_hardening.py` in as a blocking gate.
   Proposal: docs/proposals/validate-hardening-on-fixtures.md.
4. **Eval-harness ↔ catalog FC drift** — harness covers 47 FCs; catalog is at
   FC1–FC57. Add scenarios/judges for FC48–FC57. (Surfaced 2026-06-21.)
5. **[070-W4] Todo #070 (P2, LOW)** — double `get_schedule_entries` in
   `callsheets.generate`. File: todos/070-pending-p2-callsheets-generate-redundant-double-query.md
6. **G2–G5** (from the governance scorecard) — in-flight AI monitor (G2),
   monoculture mitigation in verification roles (G3), per-run-nonce ledger
   hardening (G4), delegation-as-authority-transfer (G5).

## Stashes (untouched, local)

3 stashes on `master`: `stash@{0}`/`{1}` are superseded cpaa WIP (safe to drop);
`stash@{2}` is unmerged venue-scraper proxy/`html_mode` work for
`feat/lead-scraper-expansion` (keeper — fix `claude-sonnet-4-20250514` →
`claude-sonnet-4-6` on revival).

## Recovery SHAs (older, if ever needed)

| Ref (deleted) | Tip SHA | Where it lives now |
|---------------|---------|--------------------|
| `feat/film-production-pm` | `9b432bf` | 2nd-parent lineage of `49deb17` on master |
| `test/fc52-9w95-rewire-real-swarm` | `998854e` | reflog / GC window (~30d) |

## Prompt for Next Session

```
Read HANDOFF.md, then read docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md
(start with the "Deepening Review — Findings & v1 Revisions" table — the plan was
revised R1–R8; review the thinned v1: Step 0 → Phase 1 → Phase 2).

This is Sandbox. The G1 PLAN phase is COMPLETE: spike GREEN, plan passed both
gates, deepened by 5 reviewers, thinned to v1. The next phase is PLAN REVIEW.

If Codex review findings exist: triage them (P0/P1/P2), apply fixes to the plan,
then do a Claude second pass (per ~/.claude/docs/mandatory-review-workflow.md).
If not yet reviewed: the copy-paste Codex prompt is in the plan's "Codex Handoff
Prompt" section — run it in Codex, bring findings back.

After Plan Review is clean: /workflows:work on the plan's v1 (Step 0 gating spike
FIRST — global hook placement + the token-grep fast-path must pass before Phase 1).
Don't build the v2-deferred items (graceful merge disposition, /approve skill, AI
advisory pass).
```
