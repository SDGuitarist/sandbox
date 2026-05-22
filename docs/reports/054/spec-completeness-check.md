# Pre-Swarm Spec Completeness Check

**Plan:** 2026-05-21-gym-manager-plan.md
**Checked:** 2026-05-21

## Results

| Surface | Status | Findings |
|---------|--------|----------|
| Export Names (FC1) | FAIL | 11 url_for endpoints + 0 route paths checked (WARN: path column unrecognized), 1 missing endpoint |
| Cross-Boundary Wiring (FC3) | FAIL | 87+ cross-boundary functions checked, 3 missing from wiring table |
| Input Validation (FC4) | FAIL | 35 qualifying POST routes checked, 7 missing from validation table |
| Registration Points (FC5) | PASS | 13 blueprints, 0 unregistered |
| Transaction Contracts (FC29) | PASS | 34 write functions, 0 unannotated |
| Authorization Mode (FC35) | PASS | All routes covered by blanket login-required + 2 public exceptions |

## Details

### Export Names (FC1): FAIL

The Export Names heading was found. The Route Table column "Route Path" does not match any accepted path-column header (`Path`, `URL`, `Route`, `Flask Path`) -- the actual header is "Route Path". Route paths are skipped.

The following `url_for(...)` reference appears in a code block but is absent from the Export Names table:

| Item | Location | Issue |
|------|----------|-------|
| `auth.login` | Line 1033 -- comment in `### auth/login.html` template context block: `# No context variables. Form posts to url_for('auth.login').` | Endpoint referenced in code block but not listed in Export Names table |

WARN: Route table column "Route Path" (line 950) is not an accepted path column header. Accepted headers are: `Path`, `URL`, `Route`, `Flask Path`. Route paths were not checked for this table.

### Cross-Boundary Wiring (FC3): FAIL

The Cross-Boundary Wiring heading was found. The following cross-boundary functions appear in the Export Names table with a non-owner "Used By" agent but are absent from the corresponding wiring table row:

| Item | Location | Issue |
|------|----------|-------|
| `get_invoices_by_member` | Export Names table line 1309: used by `billing_routes` | Missing from billing wiring row (line 1369). Billing row lists: `create_invoice, get_invoice, get_all_invoices, get_invoices_by_status, update_invoice, delete_invoice, get_all_members, get_payments_by_invoice, get_invoice_paid_amount` -- `get_invoices_by_member` is absent |
| `get_attendance` | Export Names table line 1288: used by `attendance_routes` | Missing from attendance wiring row (line 1366). Attendance row lists: `check_in_class, check_in_open_gym, check_out, get_today_checkins, delete_attendance, get_all_members, get_schedules_by_date` -- `get_attendance` is absent |
| `get_attendance_by_member` | Export Names table line 1290: used by `attendance_routes` | Missing from attendance wiring row (line 1366). Same row -- `get_attendance_by_member` is absent |

### Input Validation (FC4): FAIL

The Input Validation Prescriptions heading was found. The following qualifying POST routes (non-delete edit routes and one action route) are absent from the validation table. The blanket "ALL `<int:*_id>` URL params" rule at line 1428 covers URL parameter existence checks, but form-field validation rules for these routes are not prescribed:

| Item | Location | Issue |
|------|----------|-------|
| `POST /membership-types/<int:type_id>/edit` | Route table line 975 | No validation row in Input Validation table. Edit submits same fields as create (name, duration_months, price, description, is_active) but no error-response spec |
| `POST /class-types/<int:type_id>/edit` | Route table line 981 | No validation row. Edit submits same fields as create (name, description, duration_minutes, default_capacity) but no error-response spec |
| `POST /schedules/<int:schedule_id>/edit` | Route table line 988 | No validation row. Edit submits same fields as create (class_type_id, trainer_id, session_date, start_time, end_time, capacity, notes) but no error-response spec |
| `POST /attendance/<int:attendance_id>/check-out` | Route table line 994 | No validation row. Route has URL param and may accept no form input, but absence is not documented |
| `POST /equipment/<int:equipment_id>/edit` | Route table line 1001 | No validation row. Edit submits same fields as create (name, category, serial_number, purchase_date, purchase_price, status, location, notes) but no error-response spec |
| `POST /maintenance/<int:maintenance_id>/edit` | Route table line 1007 | No validation row. Edit submits same fields as create (equipment_id, description, maintenance_date, cost, performed_by, next_due_date) but no error-response spec |
| `POST /assessments/<int:assessment_id>/edit` | Route table line 1025 | No validation row. Edit submits same fields as create (member_id, trainer_id, assessment_date, weight_kg, height_cm, body_fat_pct, resting_heart_rate, notes) but no error-response spec |

Note: The members edit (`POST /members/<int:member_id>/edit`), trainers edit, and billing edit routes ARE explicitly covered because their edit forms have a different field (`status`) from their create forms. The 7 missing routes listed above lack any dedicated edit-route row.

## Summary

- **Total checks:** 6
- **PASS:** 3
- **FAIL:** 3
- **WARN:** 1 (route-path column "Route Path" not recognized; route paths not checked)
- **N/A:** 0
- **BLOCKED:** 0

STATUS: FAIL -- 11 omissions found across 3 surfaces
