---
title: "P4 Dress Rehearsal — first fully-unattended SKILL-driven multi-wave swarm run"
date: 2026-07-23
status: ready-to-launch
run_type: autopilot-swarm
launch_in: fresh-session
scale: small (waves:2, ~6-8 agents) — deliberate de-risking step BEFORE the ≥20-agent P4 baseline
feed_forward:
  risk: "the SKILL-encoded multi-wave barrier loop has NEVER run end-to-end unattended (Run 083 hand-ran the barriers). Its first hands-off exercise is where latent orchestration bugs surface — a wave barrier needing a human, the firebreak toggling/tearing down, or verify_wave/verify_harvest not firing from the SKILL."
  verify_first: true
---

# P4 Dress Rehearsal — Launch Brief

> **FRESH SESSION: YOUR FIRST TASK IS TO LAUNCH THE AUTOPILOT RUN SPECIFIED IN §4 BELOW,**
> **after the §3 pre-launch checklist passes.** Everything you need is in this file. Do not
> re-plan the tooling or re-run the Codex reviews — that work is DONE and merged. This run
> EXERCISES it. If the §3 checklist fails on any BLOCKING item, STOP and report — do not launch.

## 1. The ONE thing this run proves

The unattended multi-wave swarm **barrier loop** — encoded in `.claude/skills/autopilot/SKILL.md`
(the "Multi-Wave Barrier Loop (Path B)" section) and enforced by `tools/verify_wave.py` +
`tools/verify_harvest.py` — has **never run end-to-end fully unattended**. Run 083 proved the
mechanics but a **human hand-ran every wave barrier, approved the pushes, and cat-verified the
firebreak**. This run proves the SKILL drives the whole loop **hands-off, with 0 interventions**,
at **small scale first** so a loop-mechanics bug is caught cheaply before the expensive
≥20-agent P4 baseline.

This is trust-gate step **P4**, run as a scaled-down dress rehearsal. If it passes 0-intervention,
the very next run is the full **≥20-agent P4 baseline** (same loop, more agents) — and THAT becomes
the trusted baseline (see MEMORY `unattended-big-run-trust-gate`).

## 2. Where the repo is (self-contained context)

- **master @ `cc3dc11`** carries everything this run needs, all Codex CODE-review **GO**:
  - **P1/P2** — the multi-wave wave-barrier verifier `tools/verify_wave.py`
    (`--validate-schema` / `--wave K` / `--reconcile`) + `tools/wave_artifact.py`. Suites:
    verify_wave **40/40**, wave_artifact **15/15**.
  - **P3** — the FC-harvest value gate `tools/verify_harvest.py` (breadth/bijection/evidence/
    net-new) + the compounded-darkness `c2-smoke-report.md` fix. Suites: verify_harvest **17/17**,
    compounded_darkness **13/13**.
  - **Firebreak** — FC68 cwd-root anchored; `TRUSTED_PIPELINE_SCRIPT_PATHS` pins verify_wave,
    wave_artifact, verify_harvest, check_compounded_darkness, check_spec_provenance,
    verify_delegated_status, firebreak-activate. Classifier suite **285/285**.
- **Design X (load-bearing, do NOT violate):** unattended runs push **NO code to origin/master**.
  Workers write+commit only (they are prohibited from cross-module execution). All integration +
  self-verification happen at per-wave assembly on the local feature branch. The SOLE sanctioned
  origin/master write is the one-time pre-Wave-0 spec-provenance repair (SKILL 9w.9.5).
- **Gate architecture:** the firebreak stays **ACTIVE for the entire run — no toggle window.**

## 3. Pre-launch checklist (BLOCKING — verify ALL before running `/autopilot`)

Run these and confirm each. If any BLOCKING item fails, STOP and report; do not launch.

1. **Fresh full-context session** — this session was started clean (the autopilot orchestrator IS
   the session; a swarm build must complete all phases in one context). BLOCKING.
2. **Permissions:** `.claude/settings.local.json` has `dangerouslySkipPermissions: true`. BLOCKING.
3. **Firebreak hook loaded (FC58-fixed):** `~/.claude/settings.json` PreToolUse points at
   `/Users/alejandroguillen/Projects/sandbox/.claude/hooks/firebreak-gate.sh` (NOT a stale
   `sandbox-g1`). A stale hook reproduces FC58 and INVALIDATES the run. BLOCKING.
4. **Clean base:** `git rev-parse origin/master` == `cc3dc11` (or newer with these merges); working
   tree clean; you are about to branch a fresh feature branch off master. BLOCKING.
5. **Tooling green** (proves the merged loop tools are intact):
   - `python3 tools/test_verify_wave.py | tail -1` → 40/40
   - `python3 tools/test_verify_harvest.py | tail -1` → 17/17
   - `python3 .claude/hooks/test_firebreak_classify.py | tail -1` → 285/285
   BLOCKING (any red = a broken base; STOP).
6. **Pitfalls injection ready:** `~/.claude/docs/agent-pitfalls.md` exists; you WILL inject the 10
   general failure classes + per-agent-type rules into every agent brief (mandatory, per CLAUDE.md
   "Autopilot Agent Injection"). Copy the BUILD_TRACKING template to the repo root.
7. **Namespace:** the build MUST write its app code under its OWN top-level dir named for the build
   (e.g. `plantpal/`) — NEVER the shared `app/`. (9w.9 ghost-file gate enforces this.)

## 4. The launch (your first task)

Run the autopilot skill on the throwaway target below. It is chosen to split cleanly into **2
dependent waves** (Wave 2 consumes Wave 1) yielding **~6–8 worker agents** — enough surface to
exercise a real wave barrier, small enough to be cheap.

```
/autopilot Build "PlantPal", a small Flask + SQLite plant-care tracker. Users register / log in
(session auth). A logged-in user can add a Plant (name, species, location, watering_interval_days),
edit/delete their own plants, log a Watering event per plant (timestamp, note), and see a dashboard
that filters plants by "needs water" vs "ok" based on the last watering + interval. Plants and logs
are owned per-user (role+ownership auth). Server-rendered templates, a navbar, and flash messages.
No external APIs. THROWAWAY validation build — keep it minimal but real. Namespace ALL app code
under plantpal/ (never app/). This is an autopilot-SWARM build: the plan MUST end up
swarm: true with waves: 2 — Wave 1 = scaffold/app-factory + session auth + models/db
(User, Plant, WateringLog); Wave 2 = plant CRUD routes+templates, watering-log routes+templates,
and the needs-water dashboard/filter UI that CONSUME Wave 1's models+auth.
```

If the planner produces `swarm: false` or a single wave, NUDGE it: this is a swarm build with a
Wave-1 foundation (scaffold/auth/models) and a Wave-2 feature layer that depends on it — set
`swarm: true`, `waves: 2`, and assign agents so every Wave-2 file's cross-module imports resolve to
a Wave-1 file. The autopilot handles the rest: deepen → pre-swarm gates (schema validate,
spec-completeness, spec-provenance repair) → Wave 0/1 spawn → **verify_wave --wave 1** barrier →
Wave 2 spawn → assembly → **verify_wave --reconcile** → shared tail (compounded-darkness →
verify_harvest → disconfirmer → self-audit) → learnings.

## 5. Success criteria — what makes this rehearsal a PASS (0-intervention)

After the run, verify in the artifacts (`docs/reports/<run-id>/`, `BUILD_TRACKING.md`,
`self-audit.md`):

1. **0 human interventions.** The run completed ALL phases without a human touching a wave barrier,
   a push, or the firebreak. (This is the whole point.)
2. **Firebreak ACTIVE through the tail** — no manual toggle, no silent fail-open; teardown only at
   the final teardown step AFTER the disk-verify gates.
3. **Wave barrier fired FROM the SKILL:** `verify_wave --wave 1` gated Wave 2's spawn (Wave 2 did
   not start until Wave 1 verified PASS), and `verify_wave --reconcile` ran in the tail and PASSed.
   Evidence: `docs/reports/<run-id>/w1/wave.md`, `w2/wave.md`, and the reconcile STATUS.
4. **verify_harvest** ran in the tail (PASS if a harvest was produced) or is a documented SKIP
   (solo/non-harvest) — not silently absent.
5. **No unattended CODE push to origin/master.** Build code is on the feature branch only; the sole
   master write is the one-time spec-provenance repair. Confirm `git log origin/master` shows no
   build commits from this run.
6. **All mandatory artifacts** present (CLAUDE.md "Required Artifacts"): BUILD_TRACKING.md (filled),
   solution doc, learnings propagation summary, HANDOFF.md update, self-audit report with WARN
   dispositions + Run Quality Grade.
7. **Self-audit status** is `PIPELINE_PASS` or `PIPELINE_PASS_WITH_DEFERRED_RISK` with every WARN
   disposed.

**If all 7 hold → the SKILL multi-wave barrier loop is proven hands-off at small scale.** Record the
outcome (see §7) and GREEN-LIGHT the full **≥20-agent P4 baseline** as the next run.

## 6. If it goes wrong (record, don't force)

- **A wave barrier needed a human** (you had to hand-run verify_wave or approve a spawn) → that IS
  the finding: the loop is not yet 0-intervention. Record exactly where and why; do NOT paper over
  it. This blocks the ≥20-agent P4.
- **Firebreak toggled / tore down before the tail / fail-opened** → the no-toggle guarantee failed.
  Capture the firebreak records + `.claude/firebreak-active.json` state; STOP; re-open the relevant
  FC (FC58/FC68). Do not force past it.
- **Context death mid-run** → resume via `tail-resume` from `CHECKPOINT.md` / the wave
  `transition-state.json` (the write-ahead resume machine, plan §5). Do NOT restart from scratch.
- **spec-eval wants an API call** → GUARDRAIL: Max subscription only, NEVER pay usage credits.
  Accept `SPEC_EVAL_SKIPPED` with the human-approved waiver noted in BUILD_TRACKING (as Run 083 did).

## 7. After the run (close the loop)

- Write the run outcome to `docs/reports/<run-id>/` (autopilot does most of this) and a short
  dress-rehearsal verdict: did all 7 §5 criteria hold? PASS/FAIL + evidence.
- Update `HANDOFF.md`: record the rehearsal result and, if PASS, set the next step to the
  **≥20-agent P4 baseline** run (same loop, scaled up).
- Do NOT launch the ≥20-agent P4 in the same session — it needs its own fresh full-context session.

## 8. Hard invariants (never violate, any scale)

- No unattended CODE push to `origin/master` (Design X). No `git push --force` / history rewrite.
- Firebreak deny-known-bad; `TRUSTED_PIPELINE_SCRIPT_PATHS` file-only, NO `-m` carve-out.
- Self-audit-reviewer stays Sonnet; disconfirmer stays Opus; Gate-8 fail-closed.
- Builds namespace under their own top-level dir (never `app/`).
- NEVER pay usage credits — Max subscription only.
- Inject agent-pitfalls into every agent brief (mandatory).
