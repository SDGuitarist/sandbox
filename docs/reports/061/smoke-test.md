# Smoke Test Report

**Plan:** 2026-06-01-feat-prompting-dashboard-engine-plan.md
**Tested:** 2026-06-01

## App Startup

- **Command:** `.venv/bin/python test_smoke.py` (uses Flask test client, no server process)
- **Status:** started
- **Time to ready:** < 1 second (test client, no network binding required)

## Route Results

| # | Method | Path | Expected | Actual | Status |
|---|--------|------|----------|--------|--------|
| 1 | GET | `/` | 200 | 200 | PASS |
| 2 | GET | `/prompts/new` | 200 | 200 | PASS |
| 3 | GET | `/prompts/new` (CSRF check) | csrf_token in form | found | PASS |
| 4 | POST | `/prompts/create` | 302 | 302 | PASS |
| 5 | GET | `/prompts/1` | 200 | 200 | PASS |
| 6 | GET | `/prompts/1` (content check) | "Smoke Test Prompt" in body | found | PASS |
| 7 | GET | `/` (after create) | "Smoke Test Prompt" in body | found | PASS |
| 8 | GET | `/` (navbar check) | href= in body | found | PASS |
| 9 | GET | `/prompts/1/edit` | 200 | 200 | PASS |
| 10 | GET | `/prompts/1/versions` | 200 | 200 | PASS |
| 11 | GET | `/?q=Smoke` | 200 | 200 | PASS |
| 12 | GET | `/testing/1` | 200 | 200 | PASS |
| 13 | POST | `/prompts/1/delete` | 302 | 302 | PASS |

## Summary

- **Total routes:** 13
- **PASS:** 13
- **FAIL:** 0

STATUS: PASS
