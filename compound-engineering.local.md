---
review_agents:
  - security-sentinel
  - learnings-researcher
  - flow-trace-reviewer
---

# Review Context — Lesson Studio Scale-Validation Swarm Build (Run 081)

## Risk Chain

**Brainstorm risk (Feed-Forward, verify_first):** "The lessons (schedule) row is a 4-way FK seam (instructor + student + room + course) and is consumed by lesson routes + attendance + dashboard — the densest cross-boundary coupling in the spec."

**Plan mitigation:** Named the SQL fragment `_LESSON_SELECT` explicitly in the Export Names Table with all four join alias names. Prescribe it as a named constant, not prose. Transaction Contracts section annotated every model writer. Authorization Matrix with exact ownership field per route.

**Work outcome:** 30 workers COMPLETED. All 30 SPEC_BLOB agreements. Ownership gate 30/30 PASS. Assembly conflict-free. Contract check caught 2 inline fixes (F1 dashboard keys, F2 checkout student_name alias). Smoke FIREBREAK_DEFERRED (active tail firebreak — expected).

**Review resolution:** 1 P1 (current_user() called as function in 5 templates — 8 occurrences; fix staged/committed pending human approval), 3 P2 (deferred — non-exploitable on throwaway vehicle). Feed-Forward seam (4-way FK) was PASS; the actual P1 came from the F4 flag (current_user dict-vs-callable) which the cross-worker scan flagged as VERIFY but underweighted.

## Files to Scrutinize (for next session / smoke re-run)

| File | What changed | Risk area |
|------|-------------|-----------|
| studio/templates/lessons/list.html | current_user() → current_user (line 6) | F4 template callable bug |
| studio/templates/lessons/view.html | current_user() → current_user (lines 6, 37) | F4 template callable bug |
| studio/templates/courses/list.html | current_user() → current_user (lines 6, 35) | F4 template callable bug |
| studio/templates/courses/view.html | current_user() → current_user (line 6) | F4 template callable bug |
| studio/templates/instruments/list.html | current_user() → current_user (lines 7, 51) | F4 template callable bug |
| studio/models/checkout_models.py | Added student_name AS alias to list_checkouts + get_checkout | F2 contract fix |
| studio/templates/dashboard/index.html | summary.my_courses → summary.courses|length; summary.my_students → summary.students_count | F1 contract fix |
| studio/models/lesson_models.py | _LESSON_SELECT aliases (instructor_name, student_name, room_name, course_name) | Feed-Forward seam — VERIFIED PASS |

## Deferred Items

- **Smoke re-run:** pending firebreak teardown + P1 fix commit approval. Approval file: `todos/approvals/RED-081-indirection-03a24cdd5e52.md`
- **P2-01:** `require_self_or_staff` in auth.py never called — non-exploitable, deferred
- **P2-02:** `target_student_id` string coercion in practice route — deferred
- **P2-03:** `count_enrolled` implicit conn identity inside enroll() transaction — portability risk, deferred
- **Context proxy recalibration:** raise literal trigger to 85% for 17–32 agent swarms (currently 70%)
- **Spec §4 "Injected As" column:** mandate in spec template + spec-completeness-checker

## Plan Reference

`docs/plans/2026-07-09-feat-lesson-studio-scale-validation-plan.md`
