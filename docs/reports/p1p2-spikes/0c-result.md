STATUS: PASS

# Spike 0c — per-wave swarm-runner reuse under the REAL ancestry shape (plan §0.0c, rev5)

Branch: feat/p1p2-unattended-swarm-wave-barrier. Recorded BEFORE any §1 SKILL/tool deliverable.
Firebreak: no sentinel in this session (ungoverned manual session), so bash ran GREEN; swarm-runner
ran as the TRUSTED `swarm-runner` identity twice (fresh context each).

## Why reshaped (Codex Finding 4)
The prior fixture cut a synthetic `spike-0c-base` from current HEAD and set
`original_branch=spike-0c-base`, so `merge-base(original_branch, worker) == original_branch HEAD` —
the base-divergence that swarm-runner Step 3 exists to handle was NOT exercised. rev5 builds the
real `origin/<default>` / `original_branch` shape:

| Ref | Role | SHA |
|-----|------|-----|
| `spike-default` (== `spikeorigin/spike-default`, a real remote-tracking ref on a local bare repo) | DEFAULT branch; workers root here (baseRef=fresh) | `033e191` |
| `spike-feat` | FEATURE branch (`original_branch`), AHEAD of default by 1 commit | `6a4a084` (at build) |

Workers are rooted on `spike-default` tip, so `merge-base(spike-feat, worker) == spike-default tip
(033e191) ≠ spike-feat HEAD (6a4a084)` — genuine base-divergence; the feature commit is never in a
worker's cherry-pick range. The real GitHub `origin` remote was never touched (distinct remote name
`spikeorigin`, bare repo in a temp dir).

## Procedure
1. `python3 tools/spike_per_wave_runner_setup.py` — built the fixture above + two disjoint COMPLETED
   worker sets (wave 1: `swarm-SPIKE-w1-alpha/beta`; wave 2: `swarm-SPIKE-w2-gamma/delta`), each one
   commit on a uniquely-namespaced file, rooted on `spike-default`.
2. Spawned the real `swarm-runner` agent (mode bypassPermissions) for **wave 1**
   (`reports_dir=docs/reports/SPIKE/w1/`, `assembly_branch=swarm-SPIKE-w1-assembly`,
   `original_branch=spike-feat`). Terminal STATUS: **PASS**. (No `TaskOutput` on the local_agent —
   only the bounded final STATUS line was read.)
3. Spawned `swarm-runner` **AGAIN, fresh context**, for **wave 2**
   (`reports_dir=docs/reports/SPIKE/w2/`, `assembly_branch=swarm-SPIKE-w2-assembly`,
   `original_branch=spike-feat`). Terminal STATUS: **PASS**.
4. `python3 tools/spike_per_wave_runner_check.py` — adjudicated all §0.0c PASS criteria.

## Adjudicator results (all PASS)

| check | result |
|-------|--------|
| w1 `assembly-summary.md` line-1 `STATUS: PASS` | PASS |
| w2 `assembly-summary.md` line-1 `STATUS: PASS` | PASS |
| no `swarm-SPIKE-*` branches remain (both assembly + worker branches deleted) | PASS |
| no leftover spike worktrees | PASS |
| w2 summary references NO w1 branch/assembly names (report isolation) | PASS |
| w1 summary references NO w2 branch/assembly names | PASS |
| w1: every cherry-pick base == `spike-default` tip (`033e191`) | PASS |
| w1: `spike-feat` HEAD (`6a4a084`) is NOT a cherry-pick base | PASS |
| w2: every cherry-pick base == `spike-default` tip (`033e191`) | PASS |
| w2: `spike-feat` HEAD (`6a4a084`) is NOT a cherry-pick base | PASS |

## Base-divergence evidence (both summaries)
Every worker's recorded "Cherry-pick Base (merge-base)" is `033e191490e51451a19e7ae9a599530356eb2d6e`
(the `spike-default` tip / `spikeorigin/spike-default`), NOT `spike-feat` HEAD:

- w1: `swarm-SPIKE-w1-alpha` base=`033e191`; `swarm-SPIKE-w1-beta` base=`033e191`.
- w2: `swarm-SPIKE-w2-gamma` base=`033e191`; `swarm-SPIKE-w2-delta` base=`033e191`.

This proves swarm-runner computes the fork-point base correctly under the real ancestry shape, and
does so IDENTICALLY across two sequential reuses (wave 2 ran after wave 1 had already advanced
`spike-feat`, yet w2's base is still the default tip — no run-level state carried over).

## Report isolation / no run-level leak
- Distinct `reports_dir` per wave (`docs/reports/SPIKE/w1/` vs `w2/`); w2 did not overwrite any w1
  report.
- w1 summary references only w1 branches/bases; w2 summary references only w2 branches/bases (grep
  cross-reference count = 0 each way).
- Both assembly branches (`swarm-SPIKE-w1-assembly`, `swarm-SPIKE-w2-assembly`) and all four worker
  branches were deleted; no leftover worktrees. `cleanup_status: complete` in both summaries.

## Firebreak expectations (as documented in §0.0c)
The firebreak had no sentinel this session, so it was inert; swarm-runner's contract/test steps ran
GREEN. In a real governed run swarm-runner runs as the TRUSTED identity and its pinned-tool /
`pytest` calls are identity-agnostically allowed — no toggling occurs. This spike did not (and
cannot in an ungoverned session) exercise the firebreak classifier; that is covered separately by
the classifier test suite (§8, 282→284).

## Verdict
**PASS** — swarm-runner is side-effect-clean to reuse per wave under the real baseRef=fresh /
`original_branch`-ahead ancestry shape: per-wave report isolation, complete cleanup, no run-level
state leak, and correct base-divergence fork-point computation across two sequential invocations.
Neither invocation needed wave-parameterization work. The §1 SKILL multi-wave loop may proceed to
reuse swarm-runner per wave (pending the overall §0 Codex re-review GO).
