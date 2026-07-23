STATUS: PARTIAL — 0a PASS (strengthened), 0b PASS, 0c RESHAPED (run pending this session)

# §0 verify-first spikes — summary (plan §0, rev5)

Branch: feat/p1p2-unattended-swarm-wave-barrier. Recorded BEFORE any SKILL/tool
deliverable edit (per plan §0). Firebreak: no sentinel in this session (ungoverned
manual session), so spike bash ran GREEN by default.

rev5 resolves the Codex §0 spike-review NO-GO (4 findings): (1) 0a strengthened to
boot create_app() + catch the app-context/teardown lifecycle class; (2) §3.1
orphaned-detached-child policy + §7 containment; (3) "typecheck" language purged;
(4) 0c reshaped to the real origin/<default>-vs-original_branch ancestry shape.

| Spike | Result | Evidence |
|-------|--------|----------|
| 0a — end-to-end two-wave + lifecycle-gate proof | **PASS** | docs/reports/p1p2-spikes/0a-result.md |
| 0b — TaskStop observability | **PASS** (nuances) | docs/reports/p1p2-spikes/0b-result.md |
| 0c — per-wave swarm-runner reuse (real ancestry) | **RESHAPED, run pending** | tools/spike_per_wave_runner_setup.py + spike_per_wave_runner_check.py |

## 0a — PASS (import-resolution premise AND lifecycle-gate sufficiency; rev5 strengthened)
The fixture is now a minimal Flask app. A Wave-2 worker authored+committed `pkgspike/factory.py`
(create_app) + `pkgspike/routes.py` importing `pkgspike.database.query` with the Wave-1 file
ABSENT (author+commit rc 0); the cross-wave import correctly FAILED at author time
(ModuleNotFoundError) — confirming workers must be write+commit-only. The worker's create_app
called `init_db()` BARE (a latent bug it could not discover with Wave-1 absent). After cherry-pick
assembling BOTH waves, the integrated gate BOOTED create_app(): the BROKEN tree FAILED with the
genuine `RuntimeError: Working outside of application context` (the H6/H3 lifecycle class — a bare
import-smoke would have PASSED it), then the assembly-fix (`with app.app_context(): init_db()`)
made the gate PASS (6 passed). This proves BOTH (A) write+commit-only authoring is sound and (B)
the integrated assembly gate catches the import AND app-context/teardown classes — the precise,
scoped claim, not a blanket "Design X holds". typecheck: N/A (no mypy/pyright configured; the gate
is an import-smoke + app-boot, NOT static type checking).

## 0b — PASS (prove-zero-live gate viable; use TaskStop, not TaskList)
`TaskStop` reliably terminated a genuinely-running worker Agent (running → killed,
observed immediately). Nuances feeding §3.1: (1) `TaskList` does NOT track background
Agents — enumerate via recorded roster task_ids + completion notifications, not TaskList;
(2) a completed agent can leave an orphaned detached background shell — "terminal" is about
the Agent task (now given an EXPLICIT §3.1 policy + §7 containment in rev5, see 0b-result.md);
(3) never call `TaskOutput` on a local_agent for status (it dumps the full transcript).

## 0c — RESHAPED to the real ancestry shape (run pending this session)
Fixture builder + adjudicator rewritten (`tools/spike_per_wave_runner_setup.py`,
`tools/spike_per_wave_runner_check.py`). The prior fixture cut a synthetic `spike-0c-base` from
current HEAD with `original_branch=spike-0c-base`, so `merge-base(original_branch, worker) ==
original_branch HEAD` — base-divergence was NOT exercised (Codex Finding 4). rev5 builds:
`spike-default` (default; pushed to a local bare `spikeorigin` → real `spikeorigin/spike-default`
ref), `spike-feat` AHEAD of default by 1 (original_branch), and two disjoint worker sets rooted on
`spike-default` tip. So `merge-base(spike-feat, worker) == spike-default tip ≠ spike-feat HEAD`.
swarm-runner is spawned TWICE (original_branch=spike-feat); the check asserts report isolation,
full cleanup, no run-level leak, AND every cherry-pick base == spike-default tip. Result will be
written to `docs/reports/p1p2-spikes/0c-result.md`.

## Gate status
- §0a and §0b PASS → the two design-critical premises (spec-only authoring + a lifecycle-catching
  assembly gate; prove-zero-live) hold. Neither triggers the plan's STOP-for-revision branch.
- §0c must PASS before the §1 SKILL/tool deliverables (it gates swarm-runner reuse).
- The rev5 plan + spikes go back to Codex for a §0 re-review; §1 deliverables do not begin until
  Codex returns GO (or Alex approves as reviewer).
