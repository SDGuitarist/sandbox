# Deepening Applied -- Run 054

**Date:** 2026-05-21
**Agents:** 4 (Flask researcher, architecture reviewer, security reviewer, learnings checker)

## Changes Applied

### P1 Fixes (4)

1. **get_db() docstring** — Removed contradictory `with get_db() as conn:` example.
   Changed to `conn = get_db()` pattern. (Architecture + Flask researcher both flagged)

2. **check_password timing attack** — Changed `==` to `hmac.compare_digest`.
   Added `import hmac` to auth.py spec. (Security reviewer: CRITICAL)

3. **Startup guards** — Added RuntimeError for default SECRET_KEY in production.
   Added ADMIN_PASSWORD startup guard comment for core agent. (Security reviewer: HIGH)

4. **search_members missing from wiring** — Added to Cross-Boundary Wiring for
   member_routes. (Architecture reviewer: P1)

### P2 Fixes (6)

5. **Phantom Export Names** — Fixed `get_attendance_by_member` (changed to
   attendance_routes), `get_payment` (internal only), `get_schedule_attendance_count`
   (removed dashboard_routes).

6. **Data Ownership** — Removed phantom `billing_routes` from membership_types
   readers.

7. **search_members SQL injection note** — Added explicit parameterized LIKE
   example in docstring.

8. **Money parsing hardening** — Added NaN/Inf guards and $999,999.99 cap to
   the prescribed money parsing pattern.

9. **ON DELETE behavior** — Added explicit ON DELETE clauses to all foreign keys:
   - membership_type_id: SET NULL (member keeps record, type removed)
   - class_type_id: RESTRICT (can't delete type with schedules)
   - trainer_id: SET NULL (schedule/assessment keeps record, trainer removed)
   - member_id on attendance: CASCADE (delete member deletes attendance)
   - class_schedule_id on attendance: CASCADE (delete schedule deletes attendance)
   - equipment_id on maintenance: CASCADE (delete equipment deletes maintenance log)
   - member_id on invoices: RESTRICT (can't delete member with invoices)
   - invoice_id on payments: CASCADE (delete invoice deletes payments)
   - member_id on assessments: CASCADE (delete member deletes assessments)

## Not Applied (out of scope or already present)

- Scheduled billing (explicitly out of scope for MVP)
- Export Names Table, Transaction Contracts, Authorization Matrix (already in plan)
- HTTPS production note (low priority, not spec-level)
