STATUS: FAIL noted (non-blocking — pre-diagnosed P1 defect)

# Test Suite Results — Run 069

Command: `PYTHONPATH=cpaa-replay pytest cpaa-replay/tests/ -v --tb=short`

## Summary

| Outcome | Count |
|---------|-------|
| PASSED | 8 |
| SKIPPED | 1 |
| ERROR (setup) | 22 |
| Total collected | 31 |

## Passing Tests (8)

Pure unit tests that do not require `create_app()`:
- `test_determinism.py::test_empty_projection_hash_is_well_formed_literal` — PASS
- `test_isolation.py::test_ro_connection_rejects_writes` — PASS
- `test_isolation.py::test_ro_connection_can_read` — PASS
- `test_isolation.py::test_live_content_hash_stable` — PASS
- `test_patch_semantics.py::test_parse_patch_present_value_is_kept` — PASS
- `test_patch_semantics.py::test_parse_patch_explicit_null_becomes_none` — PASS
- `test_patch_semantics.py::test_parse_patch_absent_key_is_omitted` — PASS
- `test_patch_semantics.py::test_parse_patch_only_returns_allowed_keys` — PASS

## Skipped Test (1 — expected)

- `test_determinism.py::test_golden_corpus_projection_hash_anchor` — SKIPPED
  (DEFECT 3: `GOLDEN_PROJECTION_HASH` not yet in constants.py; F1 skips gracefully
  as designed — see known-integration-defects.md §DEFECT 3)

## Error Tests (22 — all same root cause)

All 22 errors in `conftest.py` setup (`app` fixture calls `create_app()`):
```
app/ingest_routes.py:9: in <module>
    from app.ingest import ingest
ImportError: cannot import name 'ingest' from 'app.ingest'
```

Same P1 DEFECT 1 as smoke test. One-line fix in `ingest_routes.py` will unblock
all 22 tests. After fix, DEFECT 2 (C1/C6 arity) will need a second fix before
replay-dependent tests pass.

## Non-Blocking Classification

Failures are pre-diagnosed P1 defects documented in
`docs/reports/069/known-integration-defects.md`. Assembly continues per
CLAUDE.md escalation rules (smoke/test failures non-blocking).
