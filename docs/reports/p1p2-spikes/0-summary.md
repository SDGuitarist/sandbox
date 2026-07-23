STATUS: PARTIAL — 0a PASS, 0b PASS, 0c READY (not yet run)

# §0 verify-first spikes — summary (plan §0)

Branch: feat/p1p2-unattended-swarm-wave-barrier. Recorded BEFORE any SKILL/tool
deliverable edit (per plan §0). Firebreak: no sentinel in this session (ungoverned
manual session), so spike bash ran GREEN by default.

| Spike | Result | Evidence |
|-------|--------|----------|
| 0a — end-to-end two-wave falsification | **PASS** | docs/reports/p1p2-spikes/0a-result.md |
| 0b — TaskStop observability | **PASS** (nuances) | docs/reports/p1p2-spikes/0b-result.md |
| 0c — per-wave swarm-runner reuse | **READY, NOT RUN** | fixture: tools/spike_per_wave_runner_setup.py |

## 0a — PASS (Design X premise holds)
Wave-2 worker authored+committed `pkgspike/routes.py` importing `pkgspike.database.query`
with the Wave-1 file ABSENT (author+commit rc 0). The cross-wave import correctly FAILED
at author time (ModuleNotFoundError) — confirming workers must be write+commit-only. After
cherry-pick assembling BOTH waves, the integrated tree passed `python -m compileall` +
the pytest import-smoke (4 passed). typecheck: N/A (no mypy/pyright in .venv; substituted
by the import-smoke, a strict superset of compileall). => Design X is sound; proceed.

## 0b — PASS (prove-zero-live gate viable; use TaskStop, not TaskList)
`TaskStop` reliably terminated a genuinely-running worker Agent (running → killed,
observed immediately). Nuances feeding §3.1: (1) `TaskList` does NOT track background
Agents — enumerate via recorded roster task_ids + completion notifications, not TaskList;
(2) a completed agent can leave an orphaned detached background shell — "terminal" is about
the Agent task; (3) never call `TaskOutput` on a local_agent for status (it dumps the full
transcript). None of these change the design; they refine the §3.1/§5 enumeration source.

## 0c — READY, not yet run (recommend a fresh context)
Fixture builder written: `tools/spike_per_wave_runner_setup.py` (build / --teardown). It
creates a throwaway `spike-0c-base` branch + two disjoint COMPLETED worker-branch sets
(swarm-SPIKE-w1-*, swarm-SPIKE-w2-*) under uniquely-namespaced files, so swarm-runner can be
invoked TWICE (fresh context each) with distinct reports_dir/assembly_branch. PASS = per-wave
report isolation + both assembly branches cleaned up + no run-level state leak (w2 summary
references only w2). Deferred to a fresh context: this session's context is heavily loaded
(two local_agent TaskOutput transcript dumps), and 0c spawns swarm-runner twice + mutates repo
branches — it should run deliberately, not under context pressure.

## Gate status
- §0a and §0b PASS → the two design-critical premises (spec-only authoring + prove-zero-live)
  hold. Neither triggers the plan's STOP-for-revision branch.
- §0c must PASS before the §1 SKILL/tool deliverables (it gates swarm-runner reuse).
- SEPARATELY: the rev4 plan is still "awaiting Codex re-review." Per the rev4 HANDOFF, the §1
  deliverables should not begin until Codex returns GO (or Alex approves as reviewer).
