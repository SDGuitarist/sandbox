# HANDOFF — Sandbox (G1 Firebreak)

**Date:** 2026-06-25
**Branch:** `feat/g1-risk-tiered-firebreak`
**Phase:** Compound COMPLETE — G1 built, hardened, **activated (live)**, captured.

## Current State

The G1 risk-tiered firebreak is **live**: a deterministic PreToolUse classifier that
defers a swarm worker's outward/irreversible actions to `todos/approvals/` and denies
control-plane writes, instead of blanket `bypassPermissions`. The global hook is
registered in `~/.claude/settings.json`; the autopilot orchestrator is wired to write
the run sentinel, run a positive-control probe, and tear down (SKILL Steps 9w.9.6 / 17w
/ 18w). Four classifier suites green (265 / 26 / 295-0gaps / 319 RED + 127 GREEN);
activation verified end-to-end. **One thing remains before G1 is fully proven: it has
never run inside a real swarm** — the built-in probe self-validates on first real use
(aborts fail-open if the hook isn't governing).

## Key Artifacts

| Phase | Location |
|-------|----------|
| Plan | `docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md` |
| Governance map | `docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md` (G1 → DONE) |
| Step-0 spike | `docs/spikes/2026-06-21-g1-pretooluse-hook-under-bypass-spike.md` (PASS) |
| Convergence diagnosis | `docs/solutions/2026-06-24-enumerated-denylist-vs-structural-backstop.md` (Update 2026-06-25) |
| Activation arc | `docs/solutions/2026-06-25-g1-firebreak-activation-arc.md` |
| Code | `.claude/hooks/firebreak-{gate.sh,classify.py,activate.py}`; `.claude/skills/autopilot/SKILL.md` 9w.9.6/17w/18w |
| Global hook | `~/.claude/settings.json` (backup `…bak-firebreak-20260625`) |

## Deferred Backlog (priority order)

0. **G1 live validation** — the first real swarm run is its proof; the probe aborts
   fail-open if the hook isn't governing. Needs the `dangerouslySkipPermissions` env.
1. **G3 — monoculture in verification (RECOMMENDED NEXT)** — inject perspective
   diversity into verification roles, not just research fan-outs. Field-proven by the
   G1 review loop (Codex+Claude were correlated reviewers). Antidote already known.
2. **G4 — ledger nonce** — per-run nonce / signed STATUS to close the reused-run-id
   hole (also legacy key **FC52-BASEREF-FRESH-071**; already on the autopilot backlog).
3. **G5 — delegation as authority transfer** — handoff records carry authority/
   responsibility/accountability, not just task status (doc-level).
4. **G2 — in-flight AI monitor** — net-new capability; brainstorm first (cost vs coverage).
5. **G1 follow-ons (small):** wire the SOLO autopilot path; close the stale-sentinel-on-
   crash residual (started_at/staleness guard); outward-tier `--cache-to type=registry`
   (cache push) is a declared residual, not yet closed.
6. **Pre-existing (carried):** FC51 orchestrator spec-at-worktree-base repair rule;
   Track A `P-extract`; `validate_hardening.py` adoption gate; eval-harness↔catalog FC
   drift (FC48–FC57); Todo #070 (P2 double-query in `callsheets.generate`).

## Stashes (untouched, local)

3 stashes on `master`: `stash@{0}`/`{1}` superseded cpaa WIP (safe to drop);
`stash@{2}` is unmerged venue-scraper proxy/`html_mode` work for
`feat/lead-scraper-expansion` (keeper — fix `claude-sonnet-4-20250514` → `claude-sonnet-4-6` on revival).

## Recovery SHAs (older, if ever needed)

| Ref (deleted) | Tip SHA | Where it lives now |
|---------------|---------|--------------------|
| `feat/film-production-pm` | `9b432bf` | 2nd-parent lineage of `49deb17` on master |
| `test/fc52-9w95-rewire-real-swarm` | `998854e` | reflog / GC window (~30d) |

## Three Questions (from the activation-arc Feed-Forward)

1. **Hardest decision?** Whether "flip it on" meant registering the hook (literal but
   inert for swarms) or wiring the orchestrator (the real thing). Both, in order —
   registering an inert global hook and calling it done would have been the textbook
   fail-open.
2. **What was rejected?** Manufacturing a throwaway swarm build to validate G1 live —
   the same over-engineering the convergence loop fell into; the probe self-validates.
3. **Least confident?** The first real swarm run (environment permitting). The probe is
   designed to abort safely if anything is off, so the failure mode is a halted run, not
   an ungoverned one.

## Prompt for Next Session

```
Read HANDOFF.md for context. This is sandbox, branch feat/g1-risk-tiered-firebreak.
G1 firebreak is live (built, hooked, orchestrator-wired, captured) — its first real
swarm run will self-validate it. The DeepMind governance map (docs/governance/...)
has 5 gaps; G1 is DONE. Recommended next: G3 (monoculture in verification) — brainstorm
how to inject perspective diversity into build-verification roles, since the G1 review
loop just proved correlated reviewers share blind spots.
```
