# ⬅⬅ NEXT SESSION — Run 082 (Dynamic Workflows scale test): PLAN COMPLETE, BLOCKED-pending-spike ⬅⬅

**Phase:** Planning DONE. Brainstorm (2 refinement passes) → 5-agent deepen-plan → TWO Codex
plan-review rounds, all integrated. **No code yet.** This is a governance/infrastructure test:
validate the JS `Workflow` engine as a governance-faithful replacement for the manual autopilot
skill, via a throwaway ~12-resource Flask/SQLite swarm build (the app is disposable; the engine
validation is the deliverable).

**Artifacts:** plan `docs/plans/2026-07-20-feat-dynamic-workflows-max-scale-swarm-test-plan.md` ·
brainstorm `docs/brainstorms/2026-07-20-dynamic-workflows-scale-test-brainstorm.md`.

**STATUS: BLOCKED-pending-spike, BY DESIGN.** Governance is IDENTITY-based (firebreak trusts by
`agent_type`; empty ⇒ orchestrator ⇒ TRUSTED ⇒ ungoverned; `phase` is inert). Launch hinges on an
unproven engine fact — does a Workflow `agent()` propagate `agent_type` into the PreToolUse hook
envelope? (§Load-Bearing Unknown.)

**NEXT ACTION — the Phase-0 capability/identity spike (hard launch gate).** Run the hook-wiring
check first, then a ~40-line throwaway Workflow that captures the real hook envelope and proves:
**Q1a** worker emits non-empty `agent_type` (fail ⇒ UNLAUNCHABLE); **Q1b** worker CANNOT write an
absolute main-repo `.claude/` path (fail ⇒ UNLAUNCHABLE); **Q2** `swarm-runner`/`tail-runner`
identities are emittable + allowed control-plane writes while armed (fail ⇒ outer-wrapper or
UNLAUNCHABLE); plus `parallel()` join + isolation + model override. Green ⇒ proceed to spec
convergence (Claude→Codex→NotebookLM→human) then Phase A baseline slice. The full copy-paste
next-session prompt is in the commit message and was copied to the clipboard this session.
**A2 (run count) is non-gating, pass iff >31 (~34–38); "≥35" retired.** (The Run 081 prompt block
lower in this file is superseded.)

<details><summary>Prior — Amplify content-engine: SHIPPED & MERGED (2026-07-19), no WIP blocking</summary>

Copy-gen work DONE — merged via **PR #11** (`a2fcd1e`) + **PR #12** (`77cb50f`, W29–W36 batches +
Sunday review cron). `master` in sync with `origin/master`. Plan P3 + P4 delivered. Nothing unmerged.

</details>

<details><summary>Prior (now-completed) copy-gen build notes — kept for reference</summary>

Plan P3 (copy-gen + voice gate) and P4 (weekly glue + review gate) are both delivered by one skill.

**Cadence (updated 2026-07-11):** a week = **one theme → 3 angles → 9 posts (3 IG / 3 LI /
3 FB) + 6 graphics**. Each angle gets ONE card rendered in BOTH a **1:1 square (1080×1080)** for
Instagram and a **4:5 portrait (1080×1350)** for LinkedIn + Facebook.

**What shipped:**
- **`/content-batch "<theme>" [ISO-week]`** — `.claude/skills/content-batch/SKILL.md`. Turns one
  weekly theme into 3 angles, 9 posts in Alex's voice, and a per-angle card JSON (matching
  `render.py`'s schema) rendered in both formats, into a single
  `content-engine/staging/<ISO-week>/batch.md` at `status: draft`, gated by voice-guardian.
  Copy is generated IN-SESSION on Max (Claude Code reasons the posts itself); it READS
  `content_pipeline.py`'s `SYSTEM_PROMPT` (lines 35–153) verbatim as the voice spec but NEVER
  executes it. Invariants backed by Step-9 guards (billing, em-dash/banned, 9 posts, 3 angles,
  6 pngs).
- **`content-engine/render.py`** — now dual-format: `FORMATS = {"4x5":1080×1350, "1x1":1080×1080}`,
  `render_template(data, fmt)` / `render_to_png(html, out, fmt)`, CLI 3rd arg `[4x5|1x1]`.
  `template/card.html` has a `.fmt-1x1` layout that RETUNES spacing for the square canvas (so 1:1
  reads designed-for-square, not a squeezed 4:5). Verified clean at 3–5 items; 4:5 unchanged.
- **`content-engine/tests/check_render.py`** — accepts either valid card size (1080×1350 or
  1080×1080), prints which. Closes the plan's named dims-check verification command.
- **First real week: `content-engine/staging/2026-W28/`** — theme "Trusting AI answers": Angle 1
  "Why AI sounds so sure", Angle 2 "The 3-question test" (Alex-reviewed drop), Angle 3 "The time
  it burned me". voice-guardian = **GO** on all 9. All guards pass. Ready for Alex to review.

**GUARDRAILS (held; enforced by the skill):**
- **BILLING:** copy-gen is Max-only. NEVER the raw Anthropic API / `ANTHROPIC_API_KEY`.
  `content_pipeline.py` is the voice-spec source ONLY — do NOT execute it. Billing guard
  (`grep -rn "ANTHROPIC_API_KEY\|api.anthropic.com" content-engine/`) returns empty.
- Scheduling stays **manual** (Meta Business Suite + LinkedIn native). No Metricool.
- Nothing posts without Alex's review (staging stays `status: draft`).

**NEXT — pick one:**
1. **[ALEX] Review the W28 week** — read `content-engine/staging/2026-W28/batch.md` (9 posts) and
   eyeball the 6 graphics. Confirm the personal-anecdote posts (Angle 1 FB, all of Angle 3)
   against real memories or swap them out, flip `status: draft → approved`, and post. Starts the
   4-consecutive-weeks expansion-trigger clock.
2. **Review phase** (compound step 5) on `feat/content-engine-copy-gen` before merge: Codex first,
   then Claude Code. Scrutinize copy publishability + the billing invariant. Then merge + push.
3. **Open (Alex):** 1:1 caps at ~5 card items (square has least room); 4:5 can take 6. If you ever
   want 6-item cards on IG, the square layout needs another spacing pass.

**Verify commands:**
- Dims (all staging + out): `lead-scraper/.venv/bin/python content-engine/tests/check_render.py`
- Render one card both ways: `... render.py <data.json> <out>-1x1.png 1x1` and `... <out>-4x5.png 4x5`
- Run a new week: `/content-batch "<a new theme>"`

</details>

---

# HANDOFF — Sandbox · Run 081 COMPLETE (lesson-studio scale-validation swarm)

**Date:** 2026-07-10
**Branch:** master
**Phase:** COMPLETE — PIPELINE_PASS_WITH_DEFERRED_RISK (self-audit verdict); post-teardown closure DONE same session: smoke 23/23 PASS, P1 fix verified committed, FC62 registered

## Current State

Run 081 (30-agent Lesson Studio scale-validation swarm) is COMPLETE end-to-end. The build assembled all 30 workers conflict-free; self-audit verdict PIPELINE_PASS_WITH_DEFERRED_RISK (verify-self-audit 8/8 gates). POST-TEARDOWN (same session): the two HIGH deferred WARNs were closed — [081-W4] the FC61 P1 fix turned out to be already committed in `7ba77d3` (tail self-report was stale), and [081-W2] the smoke suite was re-run: found 1 REAL app bug (FC62 — `invoice.items` resolved the dict METHOD in Jinja → 500 on every invoice view; fixed to `invoice['items']`) + several harness bugs (308-redirect token loss, POST-only token pages, missing students-row setup), then **23/23 PASS** (evidence: docs/reports/081/smoke-rerun-postteardown.md). The governance stack (G1+FC58+080-W5+G3+Step-1.52 telemetry) validated at 30-agent scale without manual workaround.

## Key Artifacts

| Phase | Location |
|-------|----------|
| Plan (spec) | docs/plans/2026-07-09-feat-lesson-studio-scale-validation-plan.md |
| Assembly summary | docs/reports/081/assembly-summary.md |
| Contract check | docs/reports/081/contract-check.md |
| Review summary | docs/reports/081/review-summary.md |
| Context telemetry | docs/reports/081/context-telemetry.md |
| Solution doc | docs/solutions/2026-07-10-lesson-studio-30-agent-scale-validation-swarm-build.md |
| Self-audit | docs/reports/081/self-audit.md |
| Disconfirmer | docs/reports/081/disconfirmer.md |
| BUILD_TRACKING | BUILD_TRACKING.md |

## Review Fixes — RESOLVED post-teardown (2026-07-10, same session)

1. **[081-W4] RESOLVED (was already moot):** the FC61 template fix (5 files, 8 occurrences) was verified COMMITTED in `7ba77d3` (diffstat + zero `current_user()` template occurrences). The "staged, approval required" state in the tail's self-report was stale. The approval record `todos/approvals/RED-081-indirection-03a24cdd5e52.md` is retained as audit trail of the firebreak deferral.

2. **[081-W2] RESOLVED:** smoke suite re-run after Step 18w teardown — initial run surfaced 1 real app bug (**FC62**, `invoice.items` dict-method shadowing → 500; fixed) + harness bugs (fixed as setup, assertions untouched); final **23/23 PASS** incl. IDOR-404 ×3, both atomicity rollbacks, one-draft invariant, CSRF negatives, SECRET_KEY fail-closed. Evidence: `docs/reports/081/smoke-rerun-postteardown.md`. The F5 prediction held exactly (registered users need explicit students-row linking).

## Deferred Items (carry to next session)

| Item | Severity | Notes |
|------|----------|-------|
| ~~Smoke re-run~~ | DONE 2026-07-10 | 23/23 PASS post-teardown; docs/reports/081/smoke-rerun-postteardown.md |
| P2-01: `require_self_or_staff` dead code | P2 | Non-exploitable; deferred |
| P2-02: `target_student_id` string coercion | P2 | Deferred |
| P2-03: `count_enrolled` implicit conn identity | P2 | Portability risk; deferred |
| Context proxy recalibration (85% for 17–32 agents) | P2 | Update orchestration skill |
| Spec §4 "Injected As" column mandate | P2 | Update spec template + checker |
| FC-TEMPLATE-CONTEXT-CALLABLE brief injection | P2 | Add to agent-pitfalls.md template agent section |
| ~~[081-W6] MEMORY.md / workflow.md / patterns.md updates~~ | DONE 2026-07-10 | Written post-teardown same session (run-081 memory + MEMORY.md pointer) |
| agent-pitfalls.md update | DONE | FC61 + FC62 added, Update Log rows appended (2026-07-10) |
| **Keep dynamic surface lit** (FC62 mitigation) | **P1 — standing** | Runtime bugs are invisible to every static reviewer (FC62 passed the Opus disconfirmer). Enforce post-teardown smoke re-run whenever the firebreak defers it. |
| ~~Diversify the DISPOSER~~ (monoculture mitigation) | **CLOSED 2026-07-10 — evidence-check, premise did not fire** | Minimal-loop probe (`disposer-diversity-probe/`): a planted seduction trap (schema/model contradiction dressed as a "denormalized cache") was DEFERRED by ALL 4 disposers — 2/2 Sonnet matched 2/2 Opus on the crux. Lone Sonnet not seduced; no miss-divergence. Do NOT build the second-model pass (same shape as G5 evaporating). Fixture kept for re-test if a real disposer failure is ever observed. |

## Governance Validation Summary (Run 081)

- **G1 firebreak:** PASS — 3/3 RED actions denied, deterministic no-canary verdict
- **FC58 path-pin:** PASS — indirection approval file generated; trusted pipeline scripts ran green
- **080-W5 compounded-darkness gate:** PASS — check_compounded_darkness.py invoked, STATUS emitted
- **G3 self-audit chain:** PASS — disconfirmer→self-audit→Gate-8 under active tail firebreak
- **Context telemetry (Step 1.52):** PASS — all 4 boundary rows recorded
- **Residual:** Disposition monoculture — **the lone Sonnet DISPOSER** (`self-audit-reviewer`) makes the final disposition + grade alone. NOTE: the disconfirmer is ALREADY Opus, so "different model" is done there. Run 081's FC62 (invoice.items 500) passed static review + contract check + the **Opus** disconfirmer — every static reviewer regardless of model — and was caught ONLY by the dynamic smoke surface. Two accurate mitigations (do before next real swarm): **(1) keep the dynamic surface lit** (080-W5) — enforce post-teardown smoke re-run whenever the firebreak defers it; runtime bugs are invisible to every static reader. **(2) Diversify the DISPOSER**, not the disconfirmer — e.g. a second-model disposition pass on the self-audit-reviewer. See note in `.claude/agents/self-audit-reviewer.md` and memory `dynamic-surface-outside-monoculture`.

## Three Questions (from solution doc Feed-Forward)

1. **Hardest decision?** Naming `_LESSON_SELECT` as an explicit constant in the spec vs. describing the aliases in prose. The constant won — zero seam failures at the 4-way FK join.
2. **What was rejected?** Running the smoke suite under the active firebreak (would produce FIREBREAK_DEFERRED). Accepted the deferral per spec.
3. **Least confident about?** Whether the context proxy recalibration (85% literal for 17–32 agent swarms) is the right threshold — based on one data point (run 081 at 30 agents). Needs validation on a second 30-agent run.

## Scale-Validation Findings (Run 081 Deliverable)

| Gate | Result |
|------|--------|
| ≥20 agents spawned | PASS — 30 COMPLETED |
| Telemetry rows complete (4/4) | PASS |
| Firebreak probe PASS | PASS |
| 080-W5 gate emits legible STATUS | PASS |
| FC58 trusted scripts under tail firebreak | PASS (indirection deferral expected) |
| Honest final status | PIPELINE_PASS_WITH_DEFERRED_RISK |

## Prompt for Next Session

```
Read HANDOFF.md for context. This is sandbox, on master (pushed through a976609+, clean).

Run 081 (Lesson Studio 30-agent scale-validation swarm) is FULLY CLOSED — same-session
post-teardown closure done: smoke 23/23 PASS (docs/reports/081/smoke-rerun-postteardown.md),
FC61 P1 fix verified committed (7ba77d3), FC62 found+fixed (invoice.items Jinja
dict-method shadowing — dynamic-surface-only catch), all learnings propagated (FC61+FC62
in agent-pitfalls; LESSONS_LEARNED, memory, journal all updated). Self-audit verdict
stays PIPELINE_PASS_WITH_DEFERRED_RISK as the point-in-time record; the post-teardown
evidence artifact documents the closure — do NOT rewrite self-audit.md.

Honest-status guardrails: 30-agent run = resilience confirmed, context-death path
attempted-not-reproduced (NOT "solved"); proxy-budget calibration finding needs a 2nd
≥20-agent data point before changing SKILL.md Step 1.52.

NEXT — pick one:
1. [MASTER-DECLUTTER] — needs Alex: per-dir keep/untrack sign-off, archive-tag first,
   git rm --cached ONLY (NEVER rm -rf — lead-scraper production data on disk).
2. Pipeline folds from run 081 (small, autonomous): add the FC62 template scan
   (grep .items/.keys/.values) to the cross-worker scan step; add "Injected As" column
   mandate to spec template + completeness checker; decide proxy-budget recalibration
   posture (measure-again vs adjust now).
3. P2 cleanups on studio/ (throwaway — only if used as a vehicle again).
4. ~~[DISPOSER-MODEL-DIVERSITY]~~ — CLOSED 2026-07-10 by evidence-check probe
   (`disposer-diversity-probe/`): all 4 disposers (2 Sonnet + 2 Opus) caught the planted
   seduction trap; premise did not fire → not building it. The standing FC62 lesson
   remains: keep the DYNAMIC smoke surface lit (080-W5) — that's the real monoculture
   escape, not model diversity.

INVARIANTS unchanged: firebreak deny-known-bad + path-pinned FC58 carve-out; Gate 8
fail-closed; builds namespace under their OWN top-level dir (FC59); self-audit-reviewer
stays sonnet.
```
