# Validation-Validity Governance (Bucket 3 of the run-070 meta-analysis)

**Why this exists.** The roadmap (`docs/roadmap-to-fully-unattended.md`) governs
*verification touches* — turning human defect-catching into deterministic gates.
This doc governs a different axis the run-070 meta-analysis surfaced: **is our
"green" actually meaningful?** A pipeline can pass every gate and still fail to
produce the knowledge it claims (M6), validate a copy it won't ship (M7), leave a
whole defect layer ungated (M10), or hide systemic bugs behind defensive briefing
(M18). These are governance questions, not failure classes — they don't belong in
`agent-pitfalls.md`.

**Scope discipline (carried from Bucket 2).** Every pattern below was mined from a
single run (070). Per the operator's Bucket-2 ruling, n=1 patterns are NOT written
into live gated artifacts (`verify-self-audit`, `self-audit-reviewer`'s 6-row
table, `spec_eval_gate.py`). This doc captures the *principle* and the *actionable
change*, then marks each as either **drained** (safe, additive, non-breaking) or
**parked** (requires a coordinated live-gate change and/or corpus calibration —
see `docs/proposals/retroactive-corpus-meta-analysis.md`).

Source: `docs/reports/070/meta-analysis.md` (patterns M1–M38).

---

## M6 — Execution quality ≠ epistemic quality

**The pattern.** Run 070 graded **A (4.7/5)** on the Run Quality rubric, which
honestly scores process and artifacts. But that grade does NOT score *"did the run
produce the knowledge it claimed to?"* Run 070 existed to validate the
orchestration-hardening tracks; by an epistemic axis it is ~C+ (Track B barely
proven — M3/M4; a near-miss on shipping a silently-invalid build — M2). A clean
execution grade can sit on top of weak evidence for the run's actual purpose.

**The principle.** A run that exists to *establish a claim* (a validation run, a
spike, a "does the hardening work" build) must be graded on **how strong its
evidence is for that claim**, separately from how cleanly it executed. The two
can diverge sharply and the execution grade is the louder, more misleading one.

**Drained (safe, this session):** added an epistemic-quality focus to the
`self-audit-reviewer` "Questions A Skeptical Reviewer Would Ask" section — every
self-audit must now ask *"How strong is the evidence for the claim this run exists
to support, distinct from whether execution was clean?"* This is ungated
narrative, so it breaks no gate.

**Parked (needs a coordinated live-gate change):** promoting epistemic quality to a
**7th scored dimension** of the Run Quality Grade. `verify-self-audit` Gate 7b
hard-requires *exactly 6 data rows*; a 7th dimension means editing the rubric
table, the output-format example, the Step-6 self-check, AND Gate 7b in lockstep
— an invasive change to a live gate on n=1 evidence. Do it only when (a) the
corpus mine shows execution/epistemic divergence recurs, and (b) the gate change
is made atomically across both files.

---

## M7 / M33 — The freeze→validate→merge model has four cracks

**The pattern.** The orchestration-hardening branch was *frozen*, then *validated*
by running a real build, and will be *merged*. That governance model has four
structural cracks, all surfaced by run 070:

1. **Circular validation (M5).** The hardening was validated *using* the hardening.
   A latent bug in the hardening would have looked like an ordinary build problem,
   not a hardening defect. Self-validating infrastructure cannot separate "correct"
   from "didn't trigger." → needs failure-mode fixtures (M4 proposal:
   `docs/proposals/validate-hardening-on-fixtures.md`), not a real app.
2. **Validated copy ≠ merged copy (M7).** We validated the hardening as *inherited
   into* `feat/film-production-pm`; we will *merge it from* `feat/cpaa-event-replay-simulator`.
   Nothing asserts the two copies are byte-identical. **Actionable pre-merge check
   (operator):** before merging, diff the hardening-bearing files between the
   validated branch and the merge-source branch; the merge is only as validated as
   that diff is empty.
3. **No feedback edge (M33c).** Validation surfaced a hardening-*adjacent* issue
   (spec-provenance / FC52) with no defined path back to amend the frozen branch
   before merge. A freeze must include a "validation found something the freeze
   should incorporate → unfreeze, amend, re-validate" edge, or it ships known-stale.
4. **Freeze assumed a stationary master (M33d).** During the freeze, `master` gained
   an orphan commit (`f90aed8`), which required a pre-flight merge to restore the
   O3 invariant. A freeze is a claim about a *moving* baseline; it must re-check the
   baseline at merge time, not assume the world held still.

**Drained (this doc):** the model and its four cracks are now documented governance,
with crack #2 turned into a concrete operator pre-merge check.

**Crack #2 check RESULT (2026-06-08): CLEAN.** Executed — `merge-base(feat/film,
feat/cpaa)` = feat/cpaa's tip `0d36a24` = the hardening commit; pure-hardening files
byte-identical; feat/film's SKILL.md changes are additive-only (`+64/-0`, `+46/-0`).
Merging feat/cpaa brings exactly the validated hardening. The check ALSO surfaced
crack-adjacent finding M30: the FC52 spec-provenance fix (`5af6f4d`) lives only on
feat/film and would be stranded by a feat/cpaa→master merge. Full evidence + the
"two decisions" framing in the handoff's Open Operator Decisions section.

**Not touched (operator authority):** the actual merge/push remain the operator's
call (`CLAUDE.md` Forbidden Actions; roadmap §0 "authority touches"). This doc
informs that decision; it does not make it.

---

## M10 — The feasibility layer is now ungated, and that is the layer 070's real gaps lived in

**The pattern.** Three detector layers cover spec quality:
- **structural** — 9w.5 (consistency) + 9w.6 (completeness): *are the 6 sections
  present and internally consistent?*
- **feasibility** — 9w.8 (spec-eval): *is what the spec asks for actually
  buildable / semantically possible?*
- **integration** — contract-check + review: *do the assembled pieces fit?*

9w.8 was correctly **demoted to advisory** (its precision was ~0% — 2-for-2 waived
across runs 068/069 for single-shot-agent artifacts; see
`[[spec-eval-gate-behavior]]` memory). But the demotion left the **feasibility
layer entirely ungated** — and run 070's *real* gaps were ALL feasibility-layer:
the contentless-FTS5 impossibility, the ~8 worker judgment-calls filling semantic
holes (M8). The structural gates passed (6 sections present) while the spec asked
for things that were impossible or underspecified. **Structural completeness ≠
feasibility**; the higher-precision structural gates do NOT cover this layer.

**The principle.** Demoting a low-precision gate is correct; *abandoning the layer
it was the only cover for* is not. The fix is to **restore feasibility-layer
coverage by fixing the harness's precision**, not to accept the layer as
permanently ungated. Re-promotion criterion is already recorded in the spec-eval
memory: "if the harness's precision is fixed, restore the abort in 9w.8 step 2."

**Drained (safe, this session):** added a note to the `[[spec-eval-gate-behavior]]`
memory reframing the demotion — the layer is *ungated*, not *covered by structural
gates*, and precision-fix-then-re-promote is an **open improvement on the roadmap,
not optional cleanup**.

**Parked (real engineering):** the harness precision fix itself
(`eval-harness/spec_eval_gate.py`) and the 9w.8 re-promotion are a build, not a
doc edit. Until then, the feasibility layer's only backstop is workers hitting
empirical walls post-spawn (M38 — distributed spec-review with no collection
channel; see Bucket 4).

---

## M18 — Defensive briefing converts loud failures into silent ones (thin-brief validation mode)

**The pattern.** Run 070's workers got contract content from *both* the worktree
spec file *and* their briefs. The briefs were defensively rich, so when the spec
file was stale (FC52), the briefs silently backfilled it — the build succeeded and
the stale-spec bug was nearly invisible (caught by luck, M2). Over-defensive
briefing is **camouflage**: it's correct for production runs (you want the build to
succeed) but actively harmful for **validation runs**, whose entire purpose is to
make systemic bugs *fail loudly*.

**The principle.** A run's briefing posture should match its purpose:
- **Production runs** → defensive briefs (maximize build success).
- **Validation runs** (purpose = exercise/prove the system) → **thin briefs**:
  deliberately minimal "read the spec" briefs so a systemic defect (stale spec,
  missing wiring, broken gate) fails loudly on run 1 instead of being masked.

Run 070 would have surfaced the worktree-base-spec bug cleanly on the first run
with thin briefs.

**Drained (this doc):** thin-brief validation mode is documented as an **opt-in
mode for validation runs**, not a default. A future validation run (e.g. the M4
fixture build) should declare thin-brief mode in its plan so the system is tested,
not the briefing.

**Not drained into the live SKILL:** thin-brief mode is NOT made a default or a new
SKILL step — defensive briefing remains correct for ordinary builds. It's a
conscious choice the operator/plan makes per validation run.

---

## Disposition summary

| Pattern | Owning change | Status this session |
|---|---|---|
| M6 | epistemic-quality axis on Run Quality | Drained as skeptical-question (safe); 7th gated dimension PARKED (corpus + atomic gate change) |
| M7/M33 | freeze→validate→merge governance | Drained as documented model + operator pre-merge diff check; merge itself untouched |
| M10 | feasibility-layer re-coverage | Reframed in spec-eval memory (safe); harness precision fix + 9w.8 re-promotion PARKED (engineering) |
| M18 | thin-brief validation mode | Documented as opt-in validation-run mode; NOT a SKILL default |

Cross-refs: `docs/reports/070/meta-analysis.md`,
`docs/latent-risks-and-mitigations.md`, `docs/roadmap-to-fully-unattended.md`,
`docs/proposals/retroactive-corpus-meta-analysis.md`,
`docs/proposals/validate-hardening-on-fixtures.md`.
