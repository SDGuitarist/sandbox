# Pre-Swarm Spec Consistency Check

**Plan:** docs/plans/film-production-pm-plan.md
**Checked:** 2026-06-02

## Results

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| 1 | Export vs Wiring | Export Names: `get_cast_members` Used By `cast routes` | Wiring Table (Schedule/Reports): `cast_models -> reports routes` via `get_cast_members` | FAIL | `reports routes` missing from Export Names consumer column |
| 2 | Export vs Wiring | Export Names: `get_schedule_entries` Used By `schedule routes, callsheet_models` | Wiring Table (Schedule/Reports): `schedule_models -> reports routes` via `get_schedule_entries` | FAIL | `reports routes` missing from Export Names consumer column |
| 3 | Route Table vs Auth Matrix | Route Table crew/expenses rows use shorthand `dept_head` | Auth Matrix uses `department_head` (the exact SQL CHECK value) | WARN | Notation differs; no functional contradiction, but agents must use `department_head` in `require_role()` calls |
| 4 | Route Table vs Auth Matrix | All 55 routes spot-checked for method/path/role consistency | Auth Matrix entries | PASS | Every Route Table row has a matching Auth Matrix row with consistent roles |
| 5 | Transaction Contracts vs Model Fns | `assign_department_head` docstring: "commits internally" | Transaction Contracts: BEGIN IMMEDIATE, YES | PASS | |
| 6 | Transaction Contracts vs Model Fns | `update_scene` docstring: "does NOT commit" | Transaction Contracts: none, NO | PASS | |
| 7 | Transaction Contracts vs Model Fns | `delete_schedule_entry` docstring: "does NOT commit" | Transaction Contracts: none, NO | PASS | |
| 8 | Transaction Contracts vs Model Fns | All other 21 write function annotations checked | Transaction Contracts table | PASS | No Transaction Contract vs model annotation mismatches found |
| 9 | Schema col vs Return Keys | `scenes.page_count_eighths` | `get_scenes` return key `page_count_eighths` | PASS | |
| 10 | Schema col vs Return Keys | `cast_members.cast_id_number` | `get_cast_for_scenes` return key `cast_id_number` | PASS | |
| 11 | Schema col vs Return Keys | No schema column `strip_color_class` | `get_schedule_entries` return key `strip_color_class` | WARN | Computed/derived field; no schema column with this name. Spec does not document the derivation logic, but this is not a contradiction |
| 12 | Export vs Wiring | Export Names: `get_scenes_by_ids` Used By `callsheet_models` | Wiring Table: `scene_models -> callsheet_models` | PASS | Consistent |
| 13 | Export vs Wiring | Export Names: `get_departments` Used By `departments routes, callsheets routes, crew routes` | Wiring Table: all three consumers present | PASS | Consistent |

## Summary

- **Total checks:** 13
- **PASS:** 9
- **FAIL:** 2
- **WARN:** 2
- **N/A (section absent):** 0

## Notes on FAILs

Checks 1 and 2 are the same class of error: the Export Names Table consumer columns were not updated when the Schedule/Reports Wiring subsection was added to the Cross-Boundary Wiring Table. The spec author must add `reports routes` to the Used By column for both `get_cast_members` and `get_schedule_entries` in the Export Names Table before the swarm launches.

STATUS: FAIL -- 2 contradictions found
