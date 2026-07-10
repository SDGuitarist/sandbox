STATUS: PASS -- 23/23 post-teardown smoke

# Post-Teardown Smoke Re-Run — run 081 (closes 081-W2; 081-W4 verified)

Run AFTER Step 18w firebreak teardown (same session), per the run-080 protocol
([080-W4]). Command: `.venv/bin/python test_smoke.py` + `python -m compileall studio`
(clean).

## Timeline

1. **Initial re-run:** 5 PASS, 3 FAIL, then a hard crash (TypeError 500 on
   /invoices/<iid>).
2. **1 REAL app bug found + fixed (FC62, new class):**
   `studio/templates/invoices/view.html` used `invoice.items` — Jinja resolves the
   dict METHOD `.items` over the `'items'` key (getattr precedes getitem), so
   `{% if invoice.items %}` was always-truthy and `{% for item in invoice.items %}`
   raised `TypeError: 'builtin_function_or_method' object is not iterable` → 500 on
   EVERY invoice view for all staff. Fixed to `invoice['items']` (2 occurrences).
   Repo-wide template scan for `.items/.keys/.values` attribute access: no other hits.
   Neither the static review, the contract check, nor the disconfirmer caught this —
   only the dynamic surface did (validates the 080-W5 "keep dynamic LIT" thesis).
3. **3 initial FAILs + 4 subsequent FAILs = harness artifacts, NOT app bugs**
   (app verified spec-correct by direct probe before any test edit; assertions
   unchanged, only test SETUP fixed — FC59 discipline):
   - `get_token()` fetched collection URLs without trailing slash → Flask 308
     canonical-redirect stub page → no `_csrf` token → POSTs died at the CSRF gate
     (400) instead of reaching the code under test. Fix: `follow_redirects=True`.
   - Tokens were fetched from POST-only (`/practice/new` → 405) or role-forbidden
     (`/instruments/new` → 403) pages → token None → 400-CSRF masked the asserted
     403 authz responses. Fix: source the token from `/` (base.html's logout form
     carries `_csrf` for any logged-in user).
   - Registered "student" users have no `students` row (spec-correct: registration
     does not auto-link; seed/staff create rows — cross-worker-scan flag F5). Fix:
     `link_student_row()` test-setup insert linking user→students row.
4. **Final result: 23/23 PASS** — register/login, student CRUD, checkout atomicity
   (+rollback on unavailable), enroll→invoice atomicity (+double-enroll rollback),
   invoice view + total=SUM(items), one-draft-per-student (accretion + IntegrityError
   backstop), IDOR-404 ×3 (students/invoices/lessons) + owner-200, staff-practice 403,
   student-instruments 403, CSRF wrong/missing 400, SECRET_KEY fail-closed,
   ends_at<=starts_at 400.

## WARN dispositions updated

- **081-W2 (HIGH, smoke never ran) → RESOLVED.** Dynamic surface now LIT: 23/23 PASS
  post-teardown (this artifact).
- **081-W4 (HIGH, P1 fix staged not committed) → RESOLVED (was already moot).** The
  FC61 fix (5 templates, 8 occurrences) is COMMITTED in `7ba77d3` (verified via
  diffstat + zero `current_user()` template occurrences). The tail's "staged,
  commit deferred" self-report was stale — the disk state was already correct.

## New failure class

FC62 (jinja2 dict-method key shadowing) appended to ~/.claude/docs/agent-pitfalls.md
with template-worker rule + post-assembly scan rule.
