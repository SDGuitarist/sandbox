---
status: complete
priority: p3
issue_id: "060"
tags: [code-review, quality, callsheets, run-063]
dependencies: []
---

# 060 — generate_call_sheet stores location.nearest_hospital in weather_note column

## Problem Statement

`generate_call_sheet` (callsheet_models.py line 113) inserts the location's
`nearest_hospital` value into the `weather_note` column of call_sheets:

```python
INSERT INTO call_sheets (project_id, sheet_number, shoot_date, weather_note, ...)
VALUES (?, ?, ?, ?, ...)
# weather_note receives: location['nearest_hospital'] if location else None
```

This is semantically wrong: `weather_note` should store weather conditions,
not hospital proximity. The call sheet detail template displays it as
"Weather:" (line 47).

## Findings

- **File:** `app/models/callsheet_models.py` line 113–116
- **Schema:** `call_sheets` has separate `general_notes TEXT` and `weather_note TEXT`
  columns. There is no `nearest_hospital` column on call_sheets.
- **Impact:** Users see hospital location displayed under "Weather:" on call sheets.
  Cosmetically wrong but data is not lost — it's stored, just misattributed.
- **Comment in code:** A comment acknowledges this: `# weather_note left NULL; hospital stored separately`
  but the code contradicts the comment — it stores hospital in weather_note.

## Proposed Solutions

### Option A: Store hospital in general_notes (Recommended)
```python
# Use general_notes for hospital proximity; weather_note stays NULL
general_notes=f'Nearest hospital: {location["nearest_hospital"]}' if location and location.get('nearest_hospital') else None,
weather_note=None,
```
Effort: Trivial.

### Option B: Add nearest_hospital column to call_sheets
More architecturally correct but requires a schema migration.
Effort: Small.

### Option C: Display-only fix in template
Show the field as "Location Notes:" instead of "Weather:".
Effort: Trivial but misleading.

## Recommended Action

Option A — store hospital note in general_notes with a label prefix.
Low risk, no schema changes.

## Technical Details

- **Affected:** `app/models/callsheet_models.py` lines 113–116
- **Also update:** `app/templates/callsheets/detail.html` line 47 (`weather_note` display)

## Acceptance Criteria

- [ ] `nearest_hospital` stored in `general_notes` not `weather_note`
- [ ] Template shows "Notes:" label for general_notes section
- [ ] Smoke test continues to pass

## Work Log

- 2026-06-02: Found during Run 063 callsheet flow trace review
