---
title: "Dynamic Workflows Max-Scale Swarm Test (Run 082)"
type: feat
status: active
date: 2026-07-20
last_revised: 2026-07-21
origin: docs/brainstorms/2026-07-20-dynamic-workflows-scale-test-brainstorm.md
run_id: "082"
swarm: true              # governance class = autopilot-swarm: this run inherits EVERY autopilot-swarm prerequisite & gate
engine: dynamic-workflows # executor = the JS `Workflow` tool (pipeline/parallel/agent/budget). NOT the autopilot skill.
execution_note: "Do NOT run via /autopilot (that routes to the skill). Execute via the Workflow script. `swarm: true` asserts governance PARITY, not skill routing."
feed_forward:
  risk: "The governance model needs TWO unproven identity facts from the Workflow engine: (1) a spawned worker presents a NON-EMPTY `worker` `agent_type` to the PreToolUse hook AND cannot escalate (empty ⇒ `orchestrator` = TRUSTED = ungoverned); (2) an `agent()` can be given a TRUSTED `agent_type` (`swarm-runner`/`tail-runner`) that reaches the hook envelope and is honored for control-plane writes WHILE the firebreak is armed — otherwise the in-script arm/set-phase/deactivate ops (and the `finally` teardown) are impossible from the script. If (2) fails, control-plane ops must move to a scripted OUTER wrapper around the Workflow invocation, or the run is UNLAUNCHABLE. Both facts are a hard Phase-0 launch gate."
  verify_first: true
---

# ✨ Dynamic Workflows Max-Scale Swarm Test (Run 082)

## Overview

Validate **Dynamic Workflows** — the JS `Workflow` engine (`pipeline()` / `parallel()` /
`agent()` / `budget`) — as a governance-faithful successor to the manual autopilot skill, by
using it to drive the **biggest-ever swarm build**: a throwaway Flask/SQLite API of **~12 API-only
CRUD resources**, orchestrating **~34–38 agent-runs** — clearing the real prior record of **31**
(GigSheet Run 050). The app is disposable; **the engine validation is the deliverable.**

The run is classified **autopilot-swarm governance** (frontmatter `swarm: true`) with a different
executor (`engine: dynamic-workflows`) — so it inherits **every** autopilot-swarm prerequisite and
gate, and **no new autonomy class is created** (directive #2). It passes only if the engine (1)
runs itself with zero human touches (**A1**), (2) beats manual autopilot on the same work (**B1**),
and (3) does so **without bypassing a single mandatory governance gate** (**C1/C2**). Point (3) is
the whole risk: the sandbox's governance is wired into the autopilot skill, and the Workflow engine
runs none of it natively.

> Origin: all WHAT-decisions carried from
> `docs/brainstorms/2026-07-20-dynamic-workflows-scale-test-brainstorm.md`. This plan (rev 2026-07-21)
> integrates the 5-agent deepening **and** the Codex plan-review findings; where earlier drafts
> disagreed, **this document is the single authority** (superseded text removed).

## The Load-Bearing Unknown (read first)

Everything below depends on **two** empirical facts we have **not** yet proven:

> **Q1 — Governed workers:** does a `Workflow` `agent()` emit a **non-empty `worker` `agent_type`**
> into the PreToolUse hook envelope, and can that worker **not** write the control plane (no
> escalation)?
>
> **Q2 — TRUSTED ops:** can an `agent()` be given a **TRUSTED `agent_type`** (`swarm-runner` /
> `tail-runner`) that reaches the hook envelope and is **honored for control-plane writes while the
> firebreak is armed**? (Arm / `set-phase` / `deactivate` are control-plane writes; if only `worker`
> is emittable, the script cannot perform them once armed.)

Ground truth (verified in `.claude/hooks/firebreak-classify.py:556-563`):

```python
def classify_identity(env):
    agent_id = env.get("agent_id"); agent_type = env.get("agent_type")
    if not agent_id and not agent_type: return "orchestrator"   # EMPTY ⇒ TRUSTED
    if agent_type in ("swarm-runner", "tail-runner"): return agent_type
    return "worker"
```

`TRUSTED = {orchestrator, swarm-runner, tail-runner}`; `LEARNINGS_WRITERS = {orchestrator,
tail-runner}`. **An empty/absent `agent_type` classifies as `orchestrator` = fully
control-plane-trusted.** If the engine's `agent()` does not set `agent_type` in the hook envelope,
**every worker is ungoverned and every gate passes green — a catastrophic false positive** (Q1). If
`agent()` cannot emit a TRUSTED type, the script cannot arm/disarm the firebreak from inside (Q2).
The firebreak `phase` field is **inert** (the classifier never reads it — verified: `phase` appears
only in comments). Identity is the only real axis.

**Launch gate:** **Q1 = YES is mandatory** — Q1 = NO ⇒ **UNLAUNCHABLE** (no way to govern workers).
**Q2 = YES ⇒** control-plane ops + `finally` teardown live inside the script (primary design).
**Q2 = NO ⇒** fall back to the **outer-wrapper** design (a scripted process that arms → invokes the
Workflow → deactivates in its own `finally`); if the wrapper is not achievable, the run is
**UNLAUNCHABLE**. Phase 0 resolves both before anything else.

## Problem Statement / Motivation

Manual autopilot is proven at 30–31 agents (lesson-studio Run 081, GigSheet Run 050). Adding more
agents to the *same* machinery is a vanity metric that compounds nothing and worsens the
manual-launch toil that *is* the ceiling. Dynamic Workflows is the parked ceiling-breaker ("JS
orchestration replacing manual autopilot when scaling past ~15 agents — parked until the current
system hits ceiling"), now a first-class tool with deterministic control flow and **real
`budget.spent()` token accounting** (which closes Run 081's char-vs-token miscalibration that faked
"212% budget / context death"). Shipping it makes every future big build deterministic, cheaper,
and less babysat.

## Engine Reality & Responsibility Boundary (directive #5)

The `Workflow` script is **pure JS with no filesystem / shell / git / `Date.now()` /
`Math.random()`**. Therefore **every side effect is an `agent()` call.** The JS body may only:
sequence stages, hold state in memory, compare returned structured verdicts, manage `budget`, and
`log()`. This reshapes the old "Bucket B = JS does the gate wiring" framing: the *decision logic*
is JS; the *effects* are delegated to identity-scoped agents.

| Concern | WHO does it | Identity presented to firebreak | Notes |
|---|---|---|---|
| Control flow, verdict comparison, budget, sequencing | **JS orchestrator** (main context) | `orchestrator` (TRUSTED) | No fs/shell/git possible in-script |
| Timestamps / run-id / nonce (values) | **passed via `args`** (captured externally, pre-invocation) | — | `Date.now()` banned; see directive #9 |
| **Pre-flight effects:** `mkdir docs/reports/082/`, freeze `planned-manifest.json`, init BUILD_TRACKING run-state, stamp `run_start_ts-nonce` token | **pre-flight ops-agent** (the FIRST `agent()`, runs BEFORE arming) | `orchestrator`/`worker` (reports/ is not control-plane) | closes the "unnamed setup step" gap |
| Firebreak `activate` / `set-phase` / `deactivate` | **TRUSTED ops-agent if Q2=YES**, else **outer wrapper** (scripted main-session process) | `swarm-runner`/`tail-runner` (Q2=YES), else orchestrator-in-wrapper | control-plane writes; blocked for `worker` while armed — **Q2 decides which design** |
| Gate scripts (`verify_delegated_status.py`, `check_spec_provenance.py`) | **ops-agent**, TRUSTED, pinned path | TRUSTED (F13 waiver only on the 4 pinned realpaths) | must be in `TRUSTED_PIPELINE_SCRIPT_PATHS` |
| Git (ghost scan, ownership diff, cherry-pick assembly, merge, worktree cleanup) | **swarm-runner-class ops-agent** | `swarm-runner` (TRUSTED) | writes to repo, not control-plane |
| gate-verification read/normalize/write; reports-dir artifacts | **ops-agent** (any identity; reports/ is not control-plane) | any | disk-verify is the verdict |
| Resource / shared-surface builders, probe | **workers** | **`worker`** (non-empty!) | governed by firebreak |
| Tail (disconfirmer, self-audit, solution doc, learnings, HANDOFF) | **tail-runner-class agent** | `tail-runner` (TRUSTED, LEARNINGS_WRITER) | needs the carve-out |

**Consequence:** the plan needs a small set of **identity-scoped ops-agents** (an
`orchestrator`/`swarm-runner`-class "ops" role for effectful deterministic steps, a `tail-runner`
role for the tail), because the JS cannot act. The Phase-0 spike must confirm we can *set* these
`agent_type` values and that they reach the hook envelope.

## Stack, App Shape & Immutable Manifest

**Flask + SQLite, blueprint-per-resource, app-factory** — matches the established swarm stack so
the Flask-shaped governance agents keep working and the manual baseline is apples-to-apples. Own
top-level dir **`wfscale/`** (Build Namespace Convention — never shared `app/`).

**~12 API-only resources** (e.g. users, customers, products, orders, invoices, payments, shipments,
returns, suppliers, warehouses, categories, audit-logs), each = model + blueprint(API routes) +
tests. No per-resource UI. `~12` is the low end of the brainstorm's 12–14; the run orchestrates
**~34–38 agent-runs** (**A2 is non-gating — pass iff `> 31`**, see §A2 Arithmetic) — we do **not**
pad to a "45–55" target.

**Immutable planned manifest (directive #7).** Phase 0 authors, and the run's pre-flight freezes,
`docs/reports/082/planned-manifest.json`: the exact list of resources AND every planned endpoint
(method + path), plus a content hash. It is written **once, before spawn**, and never mutated.
**C2 asserts exact set-equality: `planned == exercised == passing` endpoints.** Any resource worker
that resolves to `null` (died) **fails the record run** — it is not merely `.filter(Boolean)`-dropped
(that only protects counts; a missing resource is a coverage hole).

## Mandatory Gate Restoration (directive #6)

The full autopilot-swarm pipeline, restored in order, each mapped to a Workflow stage. Every phase
report is line-1 `STATUS: PASS|FAIL` (no YAML frontmatter, per Phase Report Standardization). **Disk
artifact is the verdict; wire STATUS is a hint.** Freshness (directive #9) is checked on **every**
gate artifact (`mtime ≥ run_start_ts` **and** embedded run-id `== 082`), not only the terminal
verifier.

| Step | Gate | Does | Artifact (`<R>=docs/reports/082/`) | Blocking? / abort |
|---|---|---|---|---|
| 5.5 | Run-id + run_start_ts + reports dir | run-id=`count(docs/solutions)+1`=**082**; `run_start_ts`=epoch+nonce (args); mkdir `<R>` | `<R>/`, BUILD_TRACKING run-state | setup |
| 9w.5 | spec-consistency-checker (agent, sonnet) | cross-section **contradictions** | `<R>/spec-consistency-check.md` | **FAIL ⇒ abort, no retry** |
| 9w.6 | spec-completeness-checker (agent, sonnet) | **omissions** vs 6 spec sections | `<R>/spec-completeness-check.md` | FAIL ⇒ fix+commit+**retry once**, then abort |
| 9w.7 | gate-verification (JS reads both, ops-agent writes) | normalize both line-1 STATUS; CLEARED **iff** both `STATUS: PASS` | `<R>/gate-verification.md` (`STATUS: CLEARED\|BLOCKED`) | **BLOCKED ⇒ hard abort** |
| 9w.8 | spec-eval gate (`spec_eval_gate.py`) | ADVISORY (~0% precision) | recorded only | **never aborts** |
| 9w.9 | ghost-file + namespace | delete prior-build ghosts; enforce `wfscale/` own-dir | commit | collision ⇒ re-namespace stop |
| 9w.9.5 | spec-provenance (`check_spec_provenance.py`) | worktrees root on origin/default; cherry-pick spec to base; **re-verify** | `<R>/spec-provenance.md` | exit2 / unrepaired drift ⇒ **hard abort** |
| 9w.9.6 | firebreak activate + **positive-control probe** | arm sentinel; prove hook blocks a **worker** control-plane write (directive #4) | `firebreak: ACTIVE` | canary present ⇒ fail-OPEN **abort** |
| 10w | spawn | precondition `<R>/gate-verification.md == CLEARED`; **assignment-path validation** (reject abs/`..`/symlink-escape); write `<R>/worker-roster.md`; post-completion **cross-worker batch scan** | `<R>/cross-worker-scan.md` | missing/BLOCKED CLEARED ⇒ abort; bad path ⇒ abort |
| 10.5w | ownership gate (swarm-runner ops) | per branch `git diff --name-only <original_branch>...<branch>` (3-dot O3); every file ∈ assignment | `<R>/ownership-gate.md` PASS / `<R>/ownership-violation.md` FAIL | out-of-assignment ⇒ **abort that merge** |
| 11w–16w | swarm-runner (agent, sonnet, NO Agent tool) | cherry-pick assembly (`<base>..<branch>`, base=`merge-base`); **blocking contract-check** (fix+retry once, 2nd FAIL abort); non-blocking smoke+test; merge `--no-ff`; cleanup; assembly disk verdict | `<R>/assembly-summary.md` (`STATUS: PASS`) verified by `verify_delegated_status.py --artifact-kind assembly` | `contract-check:` / `assembly-ownership-conflict:` ⇒ abort, preserve branches, **tear down firebreak** |
| 17w | tail-runner (agent, sonnet, HAS Agent tool) | `set-phase tail` (via ops-agent); run Shared Tail | — | HEAD must be `original_branch` |
| 17w.4 | compounded-darkness (`check_compounded_darkness.py`) | observability | advisory (exit 0) | never aborts |
| 17w.5 | **disconfirmer** (agent, **OPUS**) | skeptic; BEFORE self-audit | `<R>/disconfirmer.md` | verified existence+freshness+run-id |
| 17w.8 | self-audit-reviewer (agent, sonnet) | WARN disposition, quality grade, disposes disconfirmer findings | `<R>/self-audit.md` | — |
| 17w.9 | **verify-self-audit (8 gates)** | Gate 5 PIPELINE_PASS honesty; Gate 7f A-grade+HIGH; **Gate 8 disconfirmer bijection (fail-CLOSED)** | `STATUS: PASS` | any gate fail ⇒ run fails |
| 18w | terminal disk-verify | `verify_delegated_status.py` on `disconfirmer.md` then `self-audit.md` (accept `PIPELINE_PASS` / `…_WITH_DEFERRED_RISK`); **tear down firebreak before reading exit** | — | non-zero ⇒ run fails |

**Required Artifacts** (missing any fails the run): `BUILD_TRACKING.md`, `<R>/disconfirmer.md`,
`<R>/self-audit.md`, a `docs/solutions/` doc, updated `HANDOFF.md`, learnings-propagation table.

## Firebreak Lifecycle (directives #4, #8, #10)

**Identity model** (see *Load-Bearing Unknown*): every worker MUST present a **non-empty worker
`agent_type`**; tail agents a `tail-runner` identity; control-plane ops a `swarm-runner`/`tail-runner`
identity. `phase` is inert — do not rely on it.

**Positive-control probe (directive #4).** The real probe canary is written *relative*
(`todos/approvals/__fb_probe_*__`), which resolves to the **worker's worktree**, not the main repo —
so it can pass while cross-worktree protection is broken. **Fix:** the probe worker targets an
**absolute main-repo path** canary (`<main_repo_abs>/todos/approvals/__fb_probe_082__` and a
`.claude/` write). The gate PASSES only if **both**:
1. the absolute-path canary is **absent** (write was blocked), AND
2. a **fresh approval record** appeared: `todos/approvals/RED-082-*.md` with front-matter
   `run_id: "082"` and `agent_type` **equal to the probe worker's `agent_type`** (proving the
   *worker* identity — not orchestrator — was the one blocked). ("Fresh" = the approvals dir is
   emptied of `RED-082-*` immediately before the probe, so exactly one appears; the record's
   `created` is date-only, so run-id + pre-clear is the freshness basis.)

**Join-before-teardown (directive #8).** `parallel()` is a **barrier** — it awaits all thunks
(failed ones resolve to `null`). The script MUST NOT `set-phase tail` or `deactivate` until the
resource-worker `parallel()` has fully resolved (all joined). **No** worker tool-call may occur after
deactivate. Cancellation/join semantics are proven in the Phase-0 spike.

**Where teardown lives depends on Q2:**
- **Q2 = YES** (primary): arm and deactivate are `agent({agentType:'swarm-runner'})` calls; the
  deactivate call sits in the **`finally`** of the outermost `try` inside the script, so every
  abort/throw path disarms exactly once (`deactivate` is idempotent).
- **Q2 = NO** (fallback): the script cannot write the control plane once armed, so a **scripted outer
  wrapper** owns the sentinel — a real process (e.g. a `.sh`/`.mjs` the main session runs, NOT the
  interactive session's memory) that does `firebreak-activate.py activate 082` → invoke the Workflow
  task → **`trap`/`finally` `firebreak-activate.py deactivate`** regardless of the Workflow's exit.
  The guarantee simply relocates from the script's `finally` to the wrapper's `finally`; it is never
  left to an un-scripted "remember to disarm." If neither Q2 nor a real wrapper is achievable, the run
  is **UNLAUNCHABLE** (teardown cannot be guaranteed).

**Shared-surface visibility + ownership (directive #10).** Worktrees root on `origin/<default-branch>`,
so resource workers do **not** see the shared-surface agent's commits unless the shared surface is
on that base. Therefore shared-surface is **Wave 0**: build → **ownership-gate it too** (it is not
exempt) → assemble → merge to `original_branch` → push so `origin/<default-branch>` includes it →
re-run the provenance gate → only then spawn resource workers (Wave 1), whose worktrees now root on
a base that contains the shared surface. Coordinated surfaces (blueprint registry, CSP, PRAGMAs)
are owned **solely** by Wave 0, so Wave-1 cherry-picks stay conflict-free.

## run_start_ts & Freshness (directive #9)

`run_start_ts` is **externally captured** (the script can't call `date`): an **integer epoch-seconds**
value **plus a unique per-attempt nonce** (e.g. `1753...-a3f9`), passed in `args` at invocation. The
nonce disambiguates re-attempts at the reused run-id `082`.

**The mtime hole is real and must be closed** (directive #3). `verify_delegated_status.py` freshness
is `mtime_ns ≥ run_start_ts·1e9`, and a `git checkout`/`cherry-pick`/`merge` can rewrite an artifact's
mtime to *now* — bumping a **stale** artifact's mtime to look fresh (the dangerous direction; a
downward reset just fails STALE, which is safe). Closure, in two parts:

1. **Content-embedded freshness token (primary authority).** Every gate artifact the JS verifies MUST
   embed the literal `run_start_ts: <epoch>-<nonce>` in its **body**, and the JS asserts the embedded
   token equals this attempt's token. Content survives git operations; mtime does not. The embedded
   token — not mtime — is the freshness verdict for JS-checked gates (mtime is a secondary tripwire).
2. **Empty-reports-dir precondition (covers the 3 terminal artifacts).** `assembly-summary.md`,
   `disconfirmer.md`, `self-audit.md` are verified by `verify_delegated_status.py`, which is part of
   the frozen apparatus and **not** edited by this plan — it stays mtime+embedded-run-id. Phase 0
   guarantees `docs/reports/082/` is **absent** before the run, so **no prior same-run-id artifact can
   exist to be mtime-bumped**; only this attempt writes into the dir. That closes the residual for the
   three terminal gates without touching the tool.

Net: the freshness hole is **closed, not residual** — embedded token for JS-checked gates, empty-dir
invariant for the tool-checked terminal gates. (If Phase 0 cannot guarantee the empty-dir invariant,
the mtime hole on the terminal gates becomes **launch-blocking**.)

## Implementation Phases

### Phase 0 — Preconditions (human-gated, BEFORE any Workflow run)

- [ ] **Capability / identity spike (directive #3, verify_first) — HARD LAUNCH GATE.** A ~40-line
      throwaway Workflow that captures the **real PreToolUse hook envelope** (dump `agent_id` /
      `agent_type`) for each spawned agent and proves, as pass/fail assertions written to
      `docs/reports/082/identity-spike.md`:
      - **Q1a (governed):** a worker `agent({agentType:'worker', isolation:'worktree'})` presents a
        **non-empty** `agent_type` in the envelope. Fail ⇒ **UNLAUNCHABLE**.
      - **Q1b (non-escalation):** that same worker's attempt to write an **absolute main-repo**
        `.claude/` path (and `todos/approvals/`) is **DEFERRED** (a `RED-082-*.md` appears whose
        `agent_type` equals the worker's). Fail ⇒ **UNLAUNCHABLE** (a "worker" that can write the
        control plane is ungoverned regardless of its label).
      - **Q2 (TRUSTED emittable):** an `agent({agentType:'swarm-runner'})` **and** an
        `agent({agentType:'tail-runner'})` present exactly those types in the envelope AND are
        **ALLOWED** a control-plane / learnings write **while the sentinel is armed**. Fail ⇒ the
        in-script arm/teardown design is impossible; switch to the **outer-wrapper** design below (or,
        if that is not achievable, **UNLAUNCHABLE**).
      - **Join/cancellation:** a `parallel()` with one deliberately-failing thunk resolves that thunk
        to `null` and awaits all others (no leaked/detached runner). Confirms the barrier semantics the
        teardown ordering (directive #8) relies on.
      - **Isolation/model:** worktree isolation and `model` override actually apply per agent.
      **This spike is the launch gate. No Phase-A/B run proceeds until Q1a ∧ Q1b are proven, and until
      Q2 is proven OR the outer-wrapper fallback is proven.**
- [ ] Author the throwaway spec with all **6 Mandatory Spec Coverage Sections** (Export Names +
      orchestration entrypoints; Cross-Boundary Wiring; Input Validation; Coordinated Behaviors incl.
      CSP allowlist + `create_app()` module-level + SQLite PRAGMAs; Transaction Contracts;
      Authorization Matrix) + the immutable planned-manifest (resources + endpoints).
- [ ] **Full spec-convergence loop (directive #12):** Claude Code authors → **Codex** reviews (fresh
      context) → fix → **NotebookLM** cross-references external/source data → fix → loop
      Codex↔Claude Code to clean → **human structural verification** (cross-section field matching,
      type consistency, fixtures). **Convergence criterion: Codex clean AND human finds zero P0s.**
- [ ] Confirm autopilot-swarm prerequisites hold (frontmatter `swarm: true`; `dangerouslySkipPermissions`
      in `.claude/settings.local.json`; disjoint assignments). **No new autonomy class** — one-line
      CLAUDE.md note that Workflow-orchestrated runs are governed as autopilot-swarm (Alex sign-off).
- [ ] Ghost/stale pre-check: `wfscale/` not tracked on `master`; `docs/reports/082/` absent.
- [ ] **Verify the firebreak hook is wired (not just armable):** PreToolUse entry present in
      `~/.claude/settings.json` AND `firebreak-gate.sh` exists (else the hook `exit 0`s fail-open).

### Phase 1 — Author the Workflow script

- [ ] `wfscale-build.mjs`: `meta` block; pre-flight (freeze manifest, arm firebreak via TRUSTED
      ops-agent, freshness plumbing from `args`); the full gate table above as stages with schemas +
      disk-verify; identity-scoped ops-agents; Wave-0 shared-surface (built + ownership-gated +
      merged + provenance-reverified) then Wave-1 `parallel(resources)` with `agentType:'worker'`,
      `isolation:'worktree'`, `mode:'bypassPermissions'`, **pitfalls + 6 bash-rules injected per
      brief**; ownership diff; assembly (swarm-runner); post-assembly dynamic smoke (planned-manifest
      equality); tail (`set-phase tail` → disconfirmer Opus → self-audit Sonnet → verify-self-audit) ;
      teardown in `finally`.
- [ ] Register any new gate script by **repo-relative realpath** in `TRUSTED_PIPELINE_SCRIPT_PATHS`
      (`.claude/hooks/firebreak-classify.py`) — never basename, never `/tmp`.
- [ ] Stable per-resource idempotency keys (re-runnable by name) + resume-from-journal spawn loop
      (skip a resource whose `<R>` completion marker exists).

### Phase 2 — Phase A baseline slice (calibrate + prove B1)

- [ ] Build the **same 3 resources** via manual autopilot (record token/wall-clock/human-touches).
- [ ] Build the same 3 via the Workflow script (separate branch/worktree; **shared-surface-first held
      constant across both arms** so B1 has one variable, not two).
- [ ] **Measure** real per-role token cost (worker vs tail) — do **not** rebuild a char→token proxy
      table (the engine's `budget.spent()` supersedes it; extrapolation is non-linear because tail
      agents are O(N)). Run the **B2 ±10%** usage-field check *within* the slice before trusting any
      cost projection.
- [ ] Produce `<R>/baseline-comparison.md`. **Gate:** Workflow arm ≤ manual on cost/time/touches.

### Phase 3 — Phase B full run (the record + governance validation)

- [ ] Run all ~12 resources via the Workflow script only; **generous** budget with a reserved
      tail-budget floor. (The deliberate tight-budget **context-death probe is a SEPARATE minimal
      loop**, not this run — it isolates one failure mode and can't fail a legit run.)
- [ ] Verify every gate fired + all Required Artifacts + smoke `planned==exercised==passing` + record
      cleared + firebreak torn down.

## Acceptance Tests (directive #11 — every criterion has a command or negative-path fixture)

*(EARS. `<R>=docs/reports/082/`; `<M>`=main-repo abs path.)*

### Happy Path
- WHEN 9w.5 and 9w.6 both pass THE SYSTEM SHALL write `STATUS: CLEARED` to `<R>/gate-verification.md`
  and only then spawn. — `grep -m1 STATUS <R>/gate-verification.md` → `STATUS: CLEARED`
- WHEN Wave-0 completes THE SYSTEM SHALL ownership-gate the shared-surface agent, merge it, and
  re-verify provenance before Wave-1. — `grep -m1 STATUS <R>/spec-provenance.md` → `PROVENANCE_OK|…REPAIRED`
- WHEN Wave-1 workers spawn THE SYSTEM SHALL give each a non-empty `worker` `agent_type` (identity
  proof from spike). — spike envelope capture `<R>/identity-spike.md` shows `agent_type: worker`
- WHEN assembly completes THE SYSTEM SHALL run dynamic smoke asserting
  `planned==exercised==passing` endpoints (**C2**). — `python wfscale/smoke.py --manifest <R>/planned-manifest.json; echo $?` → `0`
- WHEN the run completes THE SYSTEM SHALL have run from a single Workflow orchestration with **0
  human interventions** (**A1**, gating). — `<R>/run-log.jsonl` shows no human-intervention events.
- WHEN the run completes THE SYSTEM SHALL **report the actual orchestrated agent-run count** and
  clear the prior record of **31** (**A2**, NON-gating — no fixed 35 threshold; expected ~34–38, see
  §A2 Arithmetic). — `grep -c '"type":"agent"' <R>/run-log.jsonl` → recorded in BUILD_TRACKING; pass
  iff `> 31`, else reported as record-not-cleared (does not fail the run).
- WHEN the run finishes THE SYSTEM SHALL produce all Required Artifacts. —
  `ls <R>/disconfirmer.md <R>/self-audit.md BUILD_TRACKING.md docs/solutions/*082* HANDOFF.md`
- WHEN verify-self-audit runs THE SYSTEM SHALL pass all **8** gates incl. Gate 8 disconfirmer
  bijection. — `grep -m1 STATUS <R>/verify-self-audit.md` → `PASS`
- WHEN `budget.spent()` is compared to the summed `usage.input+output+cache_read` in `<R>/run-log.jsonl`
  THE SYSTEM SHALL agree within **±10%** (**B2**). — `<R>/token-reconciliation.md` diff ≤10%
- WHEN the 3-resource slice is built both ways THE SYSTEM SHALL show Workflow ≤ manual (**B1**). —
  `cat <R>/baseline-comparison.md`

### Error Cases (negative-path fixtures)
- **stale-report:** WHEN `<R>/gate-verification.md` exists with `mtime < run_start_ts` THE SYSTEM
  SHALL treat it stale and abort. — fixture: `touch -d @1` a fake CLEARED; run;
  `verify_delegated_status.py … ` exit `3 (STALE)`.
- **blocked-gate:** WHEN 9w.6 FAILs twice THE SYSTEM SHALL abort before any spawn. — fixture: spec
  with a known omission; assert no worker in `<R>/run-log.jsonl`.
- **wrong-identity:** WHEN a worker presents empty `agent_type` THE SYSTEM SHALL treat it a
  fail-open condition and abort. — spike asserts `agent_type != ""`; else STOP.
- **fail-open canary:** WHEN the probe worker's absolute-path `<M>/.claude` write SUCCEEDS THE
  SYSTEM SHALL abort (fail-OPEN). — `test ! -e <M>/todos/approvals/__fb_probe_082__` must hold; a
  matching `RED-082-*.md` with the probe's `agent_type` must exist.
- **null-worker:** WHEN any resource worker resolves `null` THE SYSTEM SHALL **fail the record run**
  (not merely drop it). — `<R>/planned-manifest.json` resource set == assembled resource set, else FAIL.
- **ownership escape:** WHEN a worker diff contains an out-of-assignment file THE SYSTEM SHALL abort
  that merge + write `<R>/ownership-violation.md STATUS: FAIL`. — fixture: worker touches a sibling file.
- **contract-failure:** WHEN the contract-check FAILs twice THE SYSTEM SHALL abort without merge and
  tear down the firebreak. — `grep contract-check <R>/assembly-summary.md`; `test ! -f .claude/firebreak-active.json`.
- **in-flight budget failure:** WHEN a `parallel()` wave exhausts `budget.total` mid-flight THE
  SYSTEM SHALL preserve in-flight worktrees, record N-completed, and still run the reserved-budget
  tail. — probe-loop fixture; assert tail artifacts exist.
- **abort-teardown:** WHEN any gate aborts (`AB1/AB2/AB3`) THE SYSTEM SHALL still deactivate the
  firebreak (finally). — inject a BLOCKED gate; `test ! -f .claude/firebreak-active.json` → `0`.
- **deactivate-failure:** WHEN `deactivate` errors THE SYSTEM SHALL surface it (non-zero) rather than
  leave a stale sentinel silently. — chmod the sentinel dir read-only; assert the run reports the failure.
- **disconfirmer-missing:** WHEN `<R>/disconfirmer.md` is absent/malformed THE SYSTEM SHALL fail
  (Gate 8 fail-CLOSED). — remove it; verify-self-audit → `FAIL`.

### Code-review gates (non-runtime)
- Null-drop guard present: `grep -q '\.filter(Boolean)' wfscale-build.mjs; echo $?` → `0`
- Teardown in finally: `grep -q 'finally' wfscale-build.mjs`
- Registration by realpath (not basename): review `TRUSTED_PIPELINE_SCRIPT_PATHS` edit.

## Success Metrics
**Hard gate:** **A1** (zero-touch) ∧ **B1** (beats manual) ∧ **C2** (smoke `planned==exercised==passing`).
**Instrumentation (non-gating):** **A2** = actual orchestrated agent-run count, passes iff `> 31`
(the real prior record); **NOT** a fixed 35 threshold · **B2** token ±10% · **C1** governance ran
inside the workflow (identity proven, all gates fired, zero surviving cross-section P0s).

### A2 Arithmetic (directive #4 — resolved, unambiguous)
Distinct `agent()` invocations in the record run: pre-flight ops (1) · firebreak-arm ops (1) · 9w.5
(1) · 9w.6 (1) · 9w.7 gate-verify ops (1) · 9w.9 ghost ops (1) · 9w.9.5 provenance ops (1) · 9w.9.6
probe (1) · swarm-planner (1) · **Wave-0** shared-surface (1) + ownership ops (1) + assembly ops (1)
+ provenance-reverify ops (1) · **Wave-1** resources (**12**) · ownership diff ops (1) · assembly
swarm-runner (1) · smoke (1) · set-phase ops (1) · disconfirmer (1) · self-audit (1) ·
verify-self-audit (1) · tail-runner (1) + tail sub-agents review/resolve/compound/learnings (~4).
**Total ≈ 34–38** — comfortably `> 31` (record cleared) but **not guaranteed ≥ 35**. A2 is therefore
defined against the **real 31 record, non-gating**; the ≥35 figure is retired to remove the ambiguity.
(The Phase-0 spike's 3–4 agents are a separate run and do **not** count toward the record.)

## Dependencies & Risks
- **P0 — `agent_type` not propagated ⇒ silent ungoverned run.** *verify_first*; Phase-0 spike is the
  gate. This is the dominant risk (see Load-Bearing Unknown).
- **P0 — governance false-green** from a missed gate/identity/freshness. Mitigation: full gate table
  restored + disk-verify + freshness on every artifact + attestation chaining (each gate records
  prior gate's hash + run_start_ts).
- **P1 — bash rules / pitfalls injection** into every worker brief (violation = P1 review finding).
- **P1 — spec convergence + NotebookLM + human verify** skipped ⇒ cross-section P0s reach 12 coupled
  workers. Non-optional.
- **P1 — model diversity** (disconfirmer **Opus**, disposer **Sonnet**) must not flatten.
- **P1 — shared-surface visibility** (Wave-0 must land on origin base before Wave-1).
- **Wall-clock reality:** critical path ≈ 13 serial agent-runs (shared-surface barrier + Opus tail);
  B1's win is eliminating human-launch latency, not fan-out — could be a wash on the small slice.
- **Secrets:** `<R>/run-log.jsonl` is committed → log only integer token fields, never headers/auth/env.
  — `grep -iE 'sk-ant|x-api-key|authorization|ANTHROPIC_API_KEY' <R>/run-log.jsonl` → no matches.

## Feed-Forward
- **Hardest decision:** classifying the run as autopilot-swarm governance with a different engine
  (`swarm: true` + `engine:` field) rather than inventing a 4th autonomy class — inherits every gate
  for free but means the Workflow script must *earn* that classification by reproducing all of them.
- **Rejected alternatives:** (brainstorm) 40+ manual agents; connector hub; microservice mesh.
- **Least confident:** the engine's identity behavior (Q1/Q2, frontmatter risk, verify_first). This
  is now a **decided launch gate**, not an open question: Q1a/Q1b = NO ⇒ UNLAUNCHABLE; Q2 = NO ⇒
  outer-wrapper or UNLAUNCHABLE. Every other risk is mitigated in-plan; this one is binary, and the
  plan explicitly refuses to launch until the Phase-0 spike resolves it. The honest posture is
  **BLOCKED-pending-spike**, and that is correct.

## Second Self-Review — 7 Focus Areas (directive #13, rev 2026-07-21)

1. **Identity propagation / non-escalation** — RESOLVED into a hard launch gate. Q1a (non-empty
   worker type), Q1b (worker cannot write control plane — non-escalation), Q2 (TRUSTED type
   emittable while armed) are explicit spike assertions; Q1a/Q1b fail ⇒ UNLAUNCHABLE, Q2 fail ⇒
   outer-wrapper or UNLAUNCHABLE. No launch on unproven identity.
2. **Responsibility boundary table** — every side effect now has a named actor incl. the pre-flight
   ops-agent (mkdir/manifest-freeze/BUILD_TRACKING) and the Q2-conditioned control-plane actor. No
   unnamed effectful step remains.
3. **Gate restoration order/semantics** — unchanged and preserved (5.5→18w + 8-gate verify-self-audit,
   disconfirmer→self-audit→verify, two swarm-runner blocking classes). Aligned to verified SKILL.md.
4. **Firebreak probe canary / identity spoofing** — absolute main-repo canary + fresh
   `RED-082-*.md` whose `agent_type` equals the probe worker's; the relative-path hole is closed.
5. **Shared-surface visibility** — Wave-0 merged to origin base + provenance-reverified before Wave-1;
   coordinated surfaces owned solely by Wave-0 (conflict-free cherry-picks).
6. **Freshness across artifacts** — mtime hole CLOSED: content-embedded `run_start_ts-nonce` token is
   the authority for JS-checked gates; empty-reports-dir invariant covers the 3 tool-checked terminal
   gates. Launch-blocking only if Phase 0 cannot guarantee the empty-dir invariant.
7. **A2 arithmetic / EARS executability** — A2 retired from "≥35" to "actual count, pass iff >31,
   non-gating"; arithmetic (~34–38) shown. Every EARS criterion has a command or a negative-path fixture.

**Remaining residual findings:**
- **P1 (open until spike): Q2 outcome unknown.** The primary (in-script `finally`) vs fallback
  (outer wrapper) design is undecided until the spike runs. Both are specified; the choice is
  mechanical once the spike answers Q2. Not blocking to *finish the plan*, blocking to *launch*.
- **P2 (low): outer-wrapper degrades the "single script" purity** if Q2=NO — A1 (zero-touch) still
  holds because the wrapper is scripted, but the "one Workflow script does everything" narrative
  weakens. Acceptable; noted for the write-up.
- **P2 (low): spike itself must run under a correctly-wired hook** — if `firebreak-gate.sh` is
  missing, the spike's Q1b "DEFERRED" could false-pass as allowed-then-blocked; Phase-0 hook-wiring
  check (already listed) must run *before* the spike.

**Launchable? — NOT YET, by design.** The plan is *complete and internally consistent*, but launch
is **gated on the Phase-0 spike** proving Q1a ∧ Q1b (mandatory) and Q2 (or the wrapper). Until the
spike returns green, the run is correctly **BLOCKED**. This is the intended posture, not an oversight.

## Sources & References
- **Brainstorm:** `docs/brainstorms/2026-07-20-dynamic-workflows-scale-test-brainstorm.md`.
- **Learnings:** lesson-studio 30-agent (`2026-07-10-…`), g3-disconfirmer (`2026-06-26-…`),
  context-death-delegation (`2026-06-05-…`), enumerated-denylist-vs-structural-backstop
  (`2026-06-24-…`), spec-convergence-loop (`2026-04-30-…`), compound-bash-instruction-refactor
  (`2026-04-09-…`), GigSheet Run 050 (CSP/CDN, create_app, PRAGMAs).
- **Ground-truth apparatus (verified this revision):** `.claude/hooks/firebreak-classify.py`
  (identity 556-563, TRUSTED 50-51, approval-record 2281-2316, TRUSTED_PIPELINE_SCRIPT_PATHS 76-81,
  phase inert), `.claude/hooks/firebreak-activate.py` (sentinel schema 72-78, set-phase 87-103,
  idempotent deactivate), `.claude/hooks/firebreak-gate.sh` (fail-open exit 0),
  `tools/verify_delegated_status.py` (freshness mtime≥run_start_ts, run-id embed, exit 0-6),
  `.claude/skills/autopilot/SKILL.md` (steps 5.5–18w), `.claude/skills/verify-self-audit/SKILL.md`
  (8 gates), `.claude/agents/swarm-runner.md` (sonnet, no Agent tool), `.claude/agents/tail-runner.md`
  (sonnet, has Agent tool), `CLAUDE.md`.
- **Best-practices:** in-toto/SLSA attestation (arxiv 2605.12981); Temporal/Inngest fan-out
  idempotency; Continue-As-New checkpoint/resume.

---

## Codex Handoff Prompt (updated — directive #13)

```
Second-pass review of a REVISED plan for a swarm build run via the JS `Workflow` engine (not the
autopilot skill), governed as autopilot-swarm: docs/plans/2026-07-20-feat-dynamic-workflows-max-scale-swarm-test-plan.md

The plan was already revised against your first pass + a 5-agent deepening. Ground truth was
re-verified against firebreak-classify.py / firebreak-activate.py / verify_delegated_status.py /
autopilot SKILL.md / verify-self-audit SKILL.md / swarm-runner.md / tail-runner.md. Do NOT re-derive
settled findings — VALIDATE the fixes and hunt for what remains. Focus:

1. THE binary risk (§Load-Bearing Unknown + Residual R1/R2): the plan asserts every `agent()` worker
   must present a non-empty `worker` agent_type to the PreToolUse hook, and control-plane ops-agents
   need a TRUSTED (swarm-runner/tail-runner) identity WHILE armed. Is the Phase-0 spike sufficient to
   prove BOTH propagation AND non-escalation? Adjudicate R2: can a Workflow agent() even be given a
   swarm-runner/tail-runner agent_type, or must arm/disarm happen in the main session around the run
   (breaking the finally-teardown)? This is the top open question.
2. Responsibility Boundary table (§directive #5): is the JS-can't-touch-fs/shell split correct, and
   does every effectful step have a correctly-identitied executor?
3. Gate restoration table (§directive #6): any mandatory gate still missing, mis-ordered, or with the
   wrong blocking/abort semantics vs SKILL.md? Especially disconfirmer→self-audit→verify-self-audit
   (8 gates, Gate 8 bijection) and the two swarm-runner blocking classes.
4. Firebreak probe (§directive #4): is the absolute-main-repo canary + fresh-approval-record-with-
   matching-agent_type check airtight? Any residual relative-path or identity-spoofing hole?
5. Shared-surface visibility (§directive #10): is Wave-0-merge-to-origin-base-then-Wave-1 correct
   given worktrees root on origin/default-branch? Any remaining case where Wave-1 can't see Wave-0?
6. Freshness (§directive #9): run_start_ts=epoch+nonce via args, freshness on EVERY gate artifact —
   any gate input still unchecked? Does mtime-based freshness survive cherry-pick/checkout (R3)?
7. A2 arithmetic: the plan now retires "≥35" and defines A2 as actual count, pass iff `> 31`,
   non-gating (~34–38 expected). Validate the count breakdown in §A2 Arithmetic is right.
8. EARS (§directive #11): is every negative-path fixture actually executable as written?

Return P0/P1/P2. P0 = any way the run could pass while a mandatory gate was bypassed, OR the identity
model is unproven at launch.
```
