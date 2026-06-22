# HANDOFF — Sandbox

**Date:** 2026-06-21
**Branch:** master (in sync with origin, working tree clean)
**Phase:** **G1 risk-tiered firebreak — BRAINSTORM COMPLETE, ready for PLAN phase.**
Start a fresh session for planning (this handoff is the kickoff).

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

## What the PLAN phase must do (read the brainstorm first)

1. **Spike FIRST (the Feed-Forward "least confident" item):** verify a
   **PreToolUse hook actually fires when `dangerouslySkipPermissions` is true.**
   The whole mechanism depends on intercepting *above* the bypass. Encouraging
   signal: CLAUDE.md already notes "security heuristics fire above
   dangerouslySkipPermissions" — but confirm it for `PreToolUse` hooks
   specifically before building anything. If it doesn't fire, the mechanism must
   move (agent-brief contract or a wrapper around the risky tools).
2. Resolve the 2 open questions in the brainstorm: (a) how approval resolves
   (extend `resolve-todos` vs new `/approve`; auto-merge vs unblock); (b) the
   deferred-merge × Required-Artifacts phase ordering (run reports `PIPELINE_PASS`
   with merge pending — must not trip the "run completes" / self-audit contract).
3. Honor the Plan Quality Gate (4 questions) + **EARS acceptance tests** translated
   from the brainstorm's "What success looks like" bullets.

## Key Artifacts (this session)

| Item | Location |
|------|----------|
| G1 brainstorm (plan input) | docs/brainstorms/2026-06-21-g1-risk-tiered-firebreak-brainstorm.md |
| Governance scorecard (G1–G5) | docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md |
| Framework source PDF | docs/governance/three-layers-of-agent-security-deepmind-2026-06.pdf |
| Master extraction (system reference) | docs/solutions/2026-06-21-unattended-swarm-autopilot-master-extraction.md |
| Existing approval-queue pattern | todos/ + .claude/skills/resolve-todos/ |
| Permission bypass switch | .claude/settings.local.json (`dangerouslySkipPermissions`) |
| Forbidden Actions contract | CLAUDE.md ("Forbidden Actions", "Bash Command Rules") |

## Deferred Backlog (priority order)

0. **[ACTIVE → PLAN] G1 risk-tiered firebreak** — brainstorm done; next is
   `/workflows:plan` (see "What the PLAN phase must do" above).
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
Read HANDOFF.md, then read docs/brainstorms/2026-06-21-g1-risk-tiered-firebreak-brainstorm.md
and the G1 item in docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md.

This is Sandbox on master (clean). The G1 risk-tiered firebreak brainstorm is
complete and plan-ready; all key decisions are locked (see the handoff). Run the
PLAN phase: /workflows:plan on the G1 brainstorm.

Lead the plan with a SPIKE that verifies the riskiest assumption — that a
PreToolUse hook fires when dangerouslySkipPermissions is true (intercepting above
the bypass). Do not design the rest until that's confirmed; if it fails, the
mechanism moves to the agent-brief contract or a tool wrapper.

Then resolve the brainstorm's 2 open questions, honor the Plan Quality Gate (4
questions), and write EARS acceptance tests from the brainstorm's "What success
looks like" bullets. Relevant files: .claude/skills/autopilot/SKILL.md (spawn +
bypassPermissions injection), .claude/settings.local.json, todos/ + resolve-todos
skill, CLAUDE.md (Forbidden Actions). Don't change code in the plan phase.
```
