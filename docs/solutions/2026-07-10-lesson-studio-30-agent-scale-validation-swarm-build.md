---
title: "Lesson Studio Manager — Scale-Validation Swarm Build (Run 081)"
date: 2026-07-10
run_id: "081"
project: "Lesson Studio (scale-validation vehicle)"
type: swarm-build
agents: 30
framework: flask
db: sqlite
namespace: studio/
tags:
  - scale-validation
  - governance
  - firebreak
  - fc58
  - fc59
  - g3
  - lesson-studio
  - ownership-getters
  - transaction-contracts
  - 4-way-fk-seam
  - context-proxy-calibration
  - template-context-processor
related_runs: [079, 080]
outcome: PIPELINE_PASS_WITH_DEFERRED_RISK
outcome_detail: >
  Assembly PASS (all 30 workers, 0 conflicts, 2 inline contract fixes).
  Smoke/test FIREBREAK_DEFERRED (expected, non-blocking; post-teardown re-run pending).
  Existing pytest 10/10 GREEN. P1 template fix staged (commit deferred by firebreak).
governance_validated:
  - G1 firebreak (positive-control probe PASS — 3/3 RED actions denied, deterministic no-canary verdict)
  - FC58 path-pin (indirection approval file generated correctly; trusted scripts ran green)
  - FC59 namespace collision-free (studio/ untracked+absent on master pre-launch)
  - G3 self-audit chain (tail delegation active; disconfirmer→self-audit→Gate-8 path exercised)
  - 080-W5 compounded-darkness gate (check_compounded_darkness.py invoked; STATUS disposition recorded)
gates:
  spec_consistency: "FAIL → PASS (rerun after inline fix)"
  spec_completeness: PASS
  spec_eval: "ENV_ERROR (advisory; ANTHROPIC_API_KEY not set; no verdict)"
  ghost_file: "PASS (studio/ collision-free)"
  ownership_gate: "PASS 30/30"
  assembly: PASS
  contract_check: "PASS (2 inline fixes: F1 dashboard keys, F2 student_name alias)"
  smoke: "FIREBREAK_DEFERRED (expected; post-teardown re-run pending)"
  test_suite: "PASS (pytest 10/10 — existing suite)"
review:
  p1: 1
  p2: 3
  fix_commits: "7ba77d3 (todo fixes); template fix staged, commit deferred by firebreak"
warnings:
  - "M29: orchestrator context proxy 430K chars (215% of 200K-char protocol budget; ~54% of real 800K-char window) — non-blocking"
context_proxy_chars: 430000
branch: master
---

# Lesson Studio Manager — Scale-Validation Swarm Build (Run 081)

**Purpose:** Validate the governance stack (G1 firebreak, FC58 path-pin, 080-W5
compounded-darkness gate, G3 self-audit chain, Step 1.52 telemetry) live at ≥20-agent
scale under maximum context pressure. The app (a community music school manager) is
deliberately throwaway — the real deliverable is governance validation data.

---

## Build Overview

| Dimension | Value |
|-----------|-------|
| Agent count | 30 (3 foundational + 14 model + 11 route + search + smoke-test) |
| Build method | Swarm — cherry-pick assembly (`merge-base(master, branch)..branch`) |
| Namespace | `studio/` (FC59 — collision-free on master pre-launch) |
| Assembly outcome | PASS — all 30 workers, 0 conflicts, 0 skipped |
| Spec-blob agreement | PASS — all 30 workers reported identical `SPEC_BLOB: 233b2558d7769c606e0b20380dc0bafd1718511b` |
| Ownership gate | PASS 30/30 |
| Pytest (existing) | PASS 10/10 |
| Smoke suite | FIREBREAK_DEFERRED (expected under active tail firebreak; re-run pending) |
| Final status | PIPELINE_PASS_WITH_DEFERRED_RISK |

---

## Scale-Validation Acceptance Criteria

| Gate | Result |
|------|--------|
| ≥20 parallel agents | PASS — 30 workers all COMPLETED |
| All 30 assembled, 0 skipped | PASS |
| FC52 spec-blob agreement across all workers | PASS — identical blob on all 30 |
| Existing pytest suite | PASS 10/10 |
| Firebreak positive-control probe | PASS — 3/3 RED actions denied, deterministic no-canary verdict |
| spec-provenance (9w.9.5) | PROVENANCE_OK — blob identical on master + origin/master |
| Ghost-file gate (9w.9) | PASS — `studio/` untracked+absent (collision-free) |
| Context telemetry row recording | PASS — all 4 boundary rows recorded |
| Context proxy WARN M29 | WARN — 430K chars = 215% of 200K-char budget = ≈54% of real 800K-char window (see §Calibration) |
| spec-eval (9w.8) | ENV_ERROR — advisory; not a spawn gate |
| Smoke / EARS suite | FIREBREAK_DEFERRED — expected, non-blocking |

---

## Governance Gates Verified

### G1 Firebreak

Firebreak ACTIVE (phase=build) for the full run. Positive-control probe confirmed
3/3 RED actions denied with a deterministic no-canary verdict — the firebreak fires
correctly without any canary test needing to be probed in production. This is the
expected behavior: the classifier denies outward/irreversible Bash calls structurally,
not by sampling. No manual workaround was required during the run.

### FC58 (Trusted Scripts Under Active Firebreak)

The P1 template fix commit attempt during the tail was deferred per the FC58 indirection
protocol. The firebreak correctly generated an approval file at
`todos/approvals/RED-081-indirection-03a24cdd5e52.md` with the full replayable command.
This confirms FC58 behavior: indirection-class Bash commands (git commit, etc.) are
deferred to human approval; trusted pipeline scripts (`verify_delegated_status.py`,
`check_spec_provenance.py`, `check_compounded_darkness.py`) run green under the active
firebreak. No manual workaround required.

### 080-W5 Compounded-Darkness Gate

`tools/check_compounded_darkness.py` was invoked with the 081 reports directory.
The three surfaces: spec-eval (ENV_ERROR — no verdict), spec-provenance (PROVENANCE_OK —
proof-quality), dynamic tests (FIREBREAK_DEFERRED — not executed). Not all three surfaces
were simultaneously dark (provenance produced a real verdict), so the STATUS was not
COMPOUNDED_DARKNESS. The gate correctly emitted a legible status, confirming it fires
and is readable at 30-agent scale.

### G3 Self-Audit Chain (Disconfirmer → Self-Audit → Gate 8)

The full G3 chain ran in the tail: disconfirmer (Opus) produced findings → self-audit
(Sonnet) disposed findings → Gate 8 bijection check enforced disposal completeness. This
ran under an ACTIVE tail firebreak, confirming the G1+G3 coexistence scenario that run
080 validated and run 081 re-validates at 30-agent scale.

---

## Contract Fixes (Inline at Assembly Step 4)

Both fixes were flagged by the cross-worker scan (F1/F2) as VERIFY risks and resolved
inline without requiring a worker re-run.

### F1 — Dashboard key mismatch (template vs. model)

`instructor_summary()` returns `courses` (list) and `students_count` (int). The assembled
template `dashboard/index.html` used `summary.my_courses` and `summary.my_students`.

**Fix:** Template aligned to model — `summary.courses | length` and `summary.students_count`.

This is the canonical F1 bug class: a model function's return dict keys and the template
variable names are independently authored and diverge because the spec described the shape
in prose but didn't pin the exact dict key names.

### F2 — Checkout `student_name` alias missing

`list_checkouts()` and `get_checkout()` returned `student_first_name` + `student_last_name`
separately. Template `instruments/checkouts.html` expected `checkout.student_name`.

**Fix:** Added `(s.first_name || ' ' || s.last_name) AS student_name` to both SQL queries
in `studio/models/checkout_models.py`.

---

## Review Findings

### P1-01: `current_user()` Called as a Function in Templates (8 Occurrences) — FIXED

**Root cause (F4 / coordinated-behavior / template-context drift):**

`studio/__init__.py` line 78 injects `current_user` as an already-resolved dict:

```python
return {"current_user": current_user(), "csrf_token": _get_csrf_token}
```

The `current_user()` function is called at context-processor time; the template variable
holds the resulting dict (or `None`). However, 8 template locations treated the variable
as a callable — writing `{{ current_user() }}` and `{{ current_user().role }}`. This raises
`TypeError: 'dict' object is not callable` for any logged-in user — a runtime 500 on the
lessons, courses, and instruments pages.

**Contrast with `csrf_token`:** `csrf_token` IS injected as a callable
(`_get_csrf_token` function reference), so `{{ csrf_token() }}` is correct for CSRF.
The two variables in the same context processor injection have opposite types — a trap
that requires explicit documentation in Coordinated Behaviors.

**Affected templates (pre-fix):**
- `studio/templates/lessons/list.html` line 6 — 1 occurrence
- `studio/templates/lessons/view.html` lines 6, 37 — 2 occurrences
- `studio/templates/courses/list.html` lines 6, 35 — 2 occurrences
- `studio/templates/courses/view.html` line 6 — 1 occurrence
- `studio/templates/instruments/list.html` lines 7, 51 — 2 occurrences

**Fix applied:** All 8 occurrences replaced: `current_user()` → `current_user`,
`current_user().role` → `current_user.role`. Fix staged; commit deferred by firebreak
(approval file: `todos/approvals/RED-081-indirection-03a24cdd5e52.md`).

**Why it propagated:** The cross-worker scan (F4 flag) correctly noted the
dict-vs-callable ambiguity as "VERIFY" but did not pin it. The 5 affected agents each
independently chose call syntax (a reasonable choice if `current_user` were a Flask-Login
proxy). Without an explicit "Injected As: resolved dict" column in the Coordinated
Behaviors table, there was no spec-level enforcement to stop this.

### P2 Findings (Deferred — Throwaway Vehicle)

**P2-01:** `require_self_or_staff` in `studio/auth.py` lines 96–109 implemented but
never called. Student edit route gated `@role_required('admin', 'instructor')` so no IDOR
gap, but spec-intended defense-in-depth absent.

**P2-02:** `request.args.get('target_student_id')` in `routes/practice.py` lines 33–34
passed as raw string to model. SQLite coerces silently; non-numeric input returns `[]`
rather than 400.

**P2-03:** `count_enrolled` and `get_course` inside the `enroll()` BEGIN IMMEDIATE
transaction share the same connection via Flask `g` caching — correct today but a
portability risk if `get_db()` ever returns per-call connections.

---

## Feed-Forward Risk Resolution

> **Risk (plan §feed_forward.risk):** "The lessons (schedule) row is a 4-way FK seam
> (instructor + student + room + course) and is consumed by lesson routes + attendance +
> dashboard — the densest cross-boundary coupling in the spec."

**What happened:** The 4-way seam was correctly implemented and verified PASS (F3 in
both the cross-worker scan and contract check). `lesson_models._LESSON_SELECT` (lines
33–53) provides `instructor_name`, `student_name`, `room_name`, `course_name` via SQL AS
aliases. All consuming templates and `dashboard_models.py` use these exact alias names.
Zero fixes needed at this seam.

**The actual P1 came from a different seam:** The F4-class `current_user()` callable bug
in templates — a lower-priority flag the scan noted as "VERIFY" but underweighted. The
deliberately-hardest seam survived; the seam the scanner treated as lower-risk was where
the P1 materialized.

**Key insight:** Explicit named constants in the spec (`_LESSON_SELECT`) prevent seam
failures more reliably than prose descriptions. When the spec names the alias, agents
converge. When the spec describes the shape, agents diverge.

---

## Key Patterns That Worked

### `_LESSON_SELECT` Alias Constant

A single shared SQL fragment defines all four join aliases. All consuming call sites
import and compose this single constant. Zero mismatch across 30 agents.

**Rule:** For any join alias or SQL fragment that crosses agent boundaries, assign it a
named constant in the Export Names Table (section 1) with `Type = sql-alias-constant`.
Do not leave agents to derive the same name independently.

### Transaction Contracts Section (Spec §5)

The "commits internally / does NOT commit / requires BEGIN IMMEDIATE" annotation on every
model function prevented double-commit and missing-commit bugs. No transaction conflicts
in the 081 assembly. This section is mandatory in every future swarm spec.

**Enroll+invoice flow:** `enroll()` uses `with transaction() as conn` (BEGIN IMMEDIATE).
In-tx helpers `add_item_in_tx` and `get_or_create_draft_invoice_in_tx` accept `conn` as
first arg and do NOT commit. Route calls `audit_models.record()` after `enroll()` returns
(post-commit). `set_invoice_status` blocks `→ draft` transition at first line (double-
defended by route also excluding 'draft' from allowed transitions).

**Checkout+instrument flow:** `checkout_instrument` uses `with transaction() as conn`.
`set_instrument_status(conn, ...)` called on the same conn. Identical pattern for
`return_instrument`.

### Ownership-Scoped Getter Contract (FC35/IDOR)

The pattern `get_X_for(id, actor)` with a single WHERE clause enforcing ownership —
uniform across lessons, invoices, students, and practice_logs — produced zero IDOR
findings in review. The Authorization Matrix (spec §6) prescribed the exact ownership
field for every route.

All four getters use SQL WHERE predicates (no fetch-then-compare):
- `lesson_models.get_lesson_for` — compound WHERE (student OR instructor owner)
- `invoice_models.get_invoice_for` — SQL AND predicate
- `student_models.get_student_for` — SQL AND (`?staff OR user_id=actor`)
- `practice_log_models.get_practice_log_for` — SQL AND (`:staff OR subquery`)

### Blueprint Registration Order + Module-Qualified Imports

14 blueprints registered in prescribed order. Module-qualified imports used throughout
to avoid view-name-shadowing-model-name hazard (flagged and pinned mid-spawn by the
orchestrator). Dashboard registered with NO `url_prefix` (owns `/` and `/audit`).

---

## Context Proxy Calibration at 30-Agent Scale

**Finding:** The orchestrator crossed 215% of the literal 200K-char proxy budget before
tail delegation. Post-analysis: this equals ≈54% of the real 800K-char (≈200K-token)
context window. No saturation observed — the model completed all inline phases without
degradation, dropped boundary rows, or PAUSED_FOR_CONTEXT.

**The calibration finding:** The 200K-char literal proxy was calibrated on smaller swarms
(4–16 agents). At 30 agents, orchestration overhead (30 worker briefs injected, 30 worker
returns ingested, spec pre-loaded into all worktrees) generates ~2–3× more context traffic
than a 16-agent swarm. The 70% literal threshold fires at ≈38% real window utilization
on a 30-agent run — triggering early delegation before the real bottleneck is reached.

**Recommended recalibration:**

| Swarm size | Literal proxy trigger (keep cross-run comparable) | Real window estimate |
|------------|--------------------------------------------------|---------------------|
| ≤ 16 agents | 70% of 200K chars = 140K | ≈38% of 800K chars |
| 17–32 agents | 85% of 200K chars = 170K | ≈46% of 800K chars |
| > 32 agents | Measure first; do not extrapolate | — |

**Side effect:** The early delegation trigger caused the smoke suite to run under an active
tail firebreak (FIREBREAK_DEFERRED). This is expected behavior, not a smoke failure.

---

## Prevention Rules (New Failure Classes)

### FC-TEMPLATE-CONTEXT-CALLABLE (Run 081 — new)

**Pattern:** A Flask `@app.context_processor` injects a resolved value (e.g., a dict or
string) into template scope. A template-authoring agent writes call syntax (`{{ var() }}`)
because other identifiers in the same injection are callables (e.g., `csrf_token`).
Result: `TypeError` 500 for all affected page loads.

**Prevention (three layers):**

1. **Spec section 4 (Coordinated Behaviors) — new mandatory column:**
   Add "Injected As" and "Template Usage" columns to every context processor row:
   ```
   | Name         | Injected As      | Template Usage         |
   |--------------|------------------|------------------------|
   | current_user | dict (resolved)  | {{ current_user.role }} |
   | csrf_token   | callable         | {{ csrf_token() }}      |
   ```
   The spec-completeness-checker must FAIL if either column is missing for a context
   processor row.

2. **Assembly grep gate (new step 9w.9.1a):**
   ```bash
   grep -rn "current_user()" <build_dir>/templates/
   ```
   Any hit is FAIL. Generalize: for every context-processor-injected name with
   "Injected As: dict/value", assert zero call-syntax occurrences in templates.

3. **Agent brief injection (template-authoring agents):**
   > **FC-TEMPLATE-CONTEXT-CALLABLE:** Context processor variables arrive in template
   > scope as resolved values, NOT callables. Never use call syntax `{{ var() }}` for
   > a context-processor-injected name. Check the Coordinated Behaviors table column
   > "Injected As" before writing template expressions.

### F4 Scanner Escalation Rule

Any F4 VERIFY flag on a context processor export must be promoted to WARN in the
cross-worker scan report. VERIFY is acceptable for business logic seams; it is not
acceptable for Flask injection patterns where the type is deterministic.

---

## Deferred Items

| Item | Type | Next Action |
|------|------|-------------|
| Smoke re-run | BLOCKED — firebreak deferred | Run after firebreak teardown + P1 fix committed |
| P1 template fix commit | PENDING human approval | `todos/approvals/RED-081-indirection-03a24cdd5e52.md` |
| FC-TEMPLATE-CONTEXT-CALLABLE pitfall registration | agent-pitfalls.md append | Compound tail (update-learnings) |
| Spec §4 "Injected As" column mandate | Spec template update | Next spec authoring session |
| Context proxy 85% threshold (17–32 agent swarms) | Orchestration skill update | Next autopilot skill update session |
| P2-01 `require_self_or_staff` dead code | Deferred | Next Lesson Studio session (non-exploitable) |
| P2-02 `target_student_id` string coercion | Deferred | Next Lesson Studio session |
| P2-03 `count_enrolled` implicit conn identity | Deferred | Next Lesson Studio session |

---

## Related Solutions

### Direct Predecessors
- `docs/solutions/2026-06-30-shelftrack-run-080-g1-g3-coexistence-revalidation.md` — Run 080; G1+G3 coexistence confirmed; FC58 RESOLVED; 080-W5 gate deferred to run 081
- `docs/solutions/2026-06-26-g1-g3-live-validation.md` — Run 079; first live G1+G3 run; FC58 defined
- `docs/solutions/2026-06-26-g3-self-audit-disconfirmer.md` — G3 disconfirmer + Gate 8 design; disposition monoculture residual
- `docs/solutions/2026-06-25-g1-firebreak-activation-arc.md` — G1 firebreak design; positive-control probe
- `docs/solutions/2026-05-20-gigsheet-31-agent-swarm-build.md` — prior 31-agent swarm; scale baseline

### Architecture References
- `docs/solutions/2026-06-05-autopilot-context-death-delegation-architecture.md` — context-death delegation model
- `docs/solutions/2026-06-01-tail-delegation-context-resilience.md` — tail delegation patterns
- `docs/solutions/2026-05-21-spec-completeness-checker-pre-swarm-gate.md` — spec gate origin (6 mandatory sections)

### Pattern References
- `docs/solutions/2026-05-20-venueconnect-25-agent-swarm-build.md` — canonical IDOR P1 case
- `docs/solutions/2026-05-22-coworkflow-22-agent-swarm-build.md` — CSRF callable-in-template bug (same class as current_user())
- `docs/solutions/2026-06-02-film-production-pm-swarm-build.md` — SQLite autocommit and FC49 smoke-test tempfile fix

## Risk Resolution

### What was flagged
The plan's Feed-Forward risk identified the 4-way FK lesson seam as the highest-risk cross-boundary coupling. The fear: a single alias mismatch would fail the schedule page AND dashboard aggregates simultaneously. This was the deliberately-hardest seam, chosen to stress the contract machinery.

### What actually happened
The 4-way seam held. The explicit `_LESSON_SELECT` alias prescription in the spec propagated correctly to all 30 workers. The feared failure didn't materialize.

The actual P1 came from the F4 flag — a lower-severity item the cross-worker scan correctly noted but didn't pin. This confirms a recurring pattern: the seam the spec explicitly names doesn't fail; the seam the spec describes in prose diverges.

### What was learned (delta)
1. **Explicit constants beat prose.** Prescribing `_LESSON_SELECT` by name in the spec cost nothing and prevented the hardest seam from failing. Prescribing `current_user` as "a dict or None" in prose was insufficient — agents independently chose call syntax because another injected callable (`csrf_token`) trained the habit.
2. **F4 VERIFY must become F4 WARN for injection-type seams.** The cross-worker scan's disposition was too weak for a deterministic Flask contract.
3. **30-agent governance validation PASSED.** The governance stack (G1 + FC58 + 080-W5 gate + G3) functioned correctly at scale without manual workaround. The residual disposition monoculture (lone Sonnet as disposer) remains the primary governance gap.
