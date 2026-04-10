# Smoke Test Report -- contact-book

**STATUS: PASS**

**Date:** 2026-04-09
**App:** contact-book
**Base URL:** http://127.0.0.1:5000

## Results

| # | Test | Expected | Actual | Result |
|---|------|----------|--------|--------|
| 1 | GET / | 200 | 200 | PASS |
| 2 | GET /add | 200 | 200 | PASS |
| 3 | CSRF token extraction | non-empty | 64 chars | PASS |
| 4 | POST /add (with form data + CSRF) | 302 | 302 | PASS |
| 5 | GET /edit/1 | 200 | 200 | PASS |
| 6 | POST /edit/1 (with form data + CSRF) | 302 | 302 | PASS |
| 7 | POST /delete/1 (with CSRF) | 302 | 302 | PASS |

## Notes

- AirPlay occupies port 5000 on macOS via IPv6 (::1). Tests used 127.0.0.1 explicitly to reach Flask.
- CSRF tokens are session-based; a requests.Session was used to persist cookies across calls.
- All CRUD operations (create, read, update, delete) completed successfully.
- Flask ran in debug mode on the default port 5000.
