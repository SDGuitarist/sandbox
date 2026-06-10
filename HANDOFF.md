# HANDOFF — Sandbox

**Date:** 2026-06-09
**Branch:** master
**Phase:** Run 070 + orchestration-hardening + fixture suite **SHIPPED TO MASTER**.
NEXT: deferred backlog, starting with the **FC51 orchestrator rule** (#3 below).

## Current State

The 120-commit `feat/film-production-pm` line is **merged into master** via a
`--no-ff` merge commit (**`49deb17`**) and **pushed to origin**. Local and remote
`master` are in sync. The feature branch (local + remote) and the throwaway
`test/fc52-9w95-rewire-real-swarm` branch have been **deleted** (all commits are
preserved in master's history).

What shipped:
- **Run 070 Film Production PM** app (16-agent swarm, validate-on-real-build vehicle).
- **All 3 orchestration-hardening tracks** — A (cherry-pick assembly / FC51),
  B (orchestration-entrypoint presence guard / FC50), C (spec-eval demotion).
- **Orchestration-hardening fixture suite** (`eval-harness/validate_hardening.py`)
  — negative-test regression net; honest fidelity vocabulary
  (EXERCISED / SPIKE-VALIDATED / PROSE-ASSERTED / MIRRORED).
- **FC52 spec-provenance detector** (`tools/check_spec_provenance.py`) +
  SKILL 9w.9.5 share-not-fork rewire.
- Meta-analysis + 4 solution docs + learnings propagation.

All gates were GREEN at merge: 3 Codex rounds (R1/R2/R3 GO), 9w.9.5 rewire
scoped-validated, pre-merge safety check CLEAN, merge fast-forward-safe (zero
conflicts).

## Recovery SHAs (if ever needed)

| Ref (deleted) | Tip SHA | Where it lives now |
|---------------|---------|--------------------|
| `feat/film-production-pm` | `9b432bf` | 2nd-parent lineage of `49deb17` on master |
| `test/fc52-9w95-rewire-real-swarm` | `998854e` | reflog / GC window (~30d); narrative in git history |

## Key Artifacts

| Phase | Location |
|-------|----------|
| Plan (fixture suite) | docs/plans/2026-06-08-feat-hardening-fixture-suite-plan.md |
| Solution (fixture suite) | docs/solutions/2026-06-09-orchestration-hardening-fixture-suite.md |
| Solution (hardening) | docs/solutions/2026-06-07-autopilot-orchestration-hardening.md |
| Solution (Run 070) | docs/solutions/2026-06-08-film-production-pm-run-070-swarm-build.md |
| Runner + all fixture logic | eval-harness/validate_hardening.py |
| Fixtures + README (fidelity contract) | eval-harness/fixtures/ |
| Shipped FC52 detector | tools/check_spec_provenance.py |
| Live gate rewire | .claude/skills/autopilot/SKILL.md (Step 9w.9.5) |

## Deferred Backlog (priority order)

1. **[NEXT] FC51 orchestrator rule** — ensure the converged spec is at the
   worktree base before swarm spawn (cherry-pick the spec-update commit into each
   worktree base, OR inline-inject spec sections into briefs). This is a **live
   fragility that already bit Run 070** (brief-injection is fragile; orchestrator
   must pre-load the converged spec into worktrees). Highest value — it's a real
   defect, not a coverage gap. Lives in the autopilot skill orchestration path.
2. **Track A `P-extract`** — refactor `swarm-runner.md:76-138` cherry-pick prose
   into a shared callable so Track A (FC51) earns a real EXERCISED fixture row
   instead of agent-prose. Needs its own real-build validation. (Note: overlaps
   with #1 — doing #1 may reshape what gets extracted here.)
3. **Suite adoption decision (operator)** — wire `validate_hardening.py` into the
   autopilot pipeline as a blocking gate. Proposal: docs/proposals/validate-hardening-on-fixtures.md.
4. **[070-W4] Todo #070 (P2, LOW)** — double `get_schedule_entries` in
   `callsheets.generate`; pass pre-fetched entries as optional param.
   File: todos/070-pending-p2-callsheets-generate-redundant-double-query.md
5. **F-C1 scorer timeout bound (P3, LOW)** — 420s `--with-api` timeout could
   false-`TIMEOUT` a slow-but-healthy scorer. Non-blocking, opt-in path only.
   Revisit only if real `--with-api` runs flake on timeout.

## Prompt for Next Session

```
Read HANDOFF.md. This is Sandbox, on master (49deb17) — the Run 070 + hardening
+ fixture suite line is shipped. Working the deferred backlog, starting with #1:
the FC51 orchestrator rule. Goal: guarantee the converged spec is at the worktree
base before swarm spawn (cherry-pick the spec commit into worktree bases, or
inline-inject spec sections into briefs), so the Run-070 brief-injection fragility
can't recur. Start by locating the spawn path in .claude/skills/autopilot/SKILL.md
and how worktrees are created, then brainstorm the fix before changing anything.
```
