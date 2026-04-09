# Smoke Test Report: Recipe Organizer

**Date:** 2026-04-09
**STATUS: PASS**
**Tests:** 16/16 passed

## Environment

- Python venv at `recipe-organizer/.venv`
- Flask 3.1.3, Werkzeug 3.1.8
- App started on `127.0.0.1:5050` (port 5000 occupied by macOS AirPlay)

## Route Tests (9/9 passed)

| # | Method | Path | Expected | Actual | Status |
|---|--------|------|----------|--------|--------|
| 1 | GET | `/` | 302 | 302 | PASS |
| 2 | GET | `/recipes/` | 200 | 200 | PASS |
| 3 | GET | `/recipes/new` | 200 | 200 | PASS |
| 4 | GET | `/recipes/999` | 404 | 404 | PASS |
| 5 | GET | `/ingredients/` | 200 | 200 | PASS |
| 6 | GET | `/ingredients/new` | 200 | 200 | PASS |
| 7 | GET | `/ingredients/999/edit` | 404 | 404 | PASS |
| 8 | GET | `/search/` | 200 | 200 | PASS |
| 9 | GET | `/search/?q=test` | 200 | 200 | PASS |

## CRUD Flow Tests (7/7 passed)

| # | Action | Method | Path | Expected | Actual | Status |
|---|--------|--------|------|----------|--------|--------|
| 1 | Create ingredient "Chicken" | POST | `/ingredients/new` | 302 | 302 | PASS |
| 2 | Create ingredient "Garlic" | POST | `/ingredients/new` | 302 | 302 | PASS |
| 3 | Create recipe "Garlic Chicken" | POST | `/recipes/new` | 302 | 302 | PASS |
| 4 | View recipe detail | GET | `/recipes/1` | 200 | 200 | PASS |
| 5 | Search for "chicken" | GET | `/search/?q=chicken` | 200 | 200 | PASS |
| 6 | Delete recipe | POST | `/recipes/1/delete` | 302 | 302 | PASS |
| 7 | Verify deletion | GET | `/recipes/1` | 404 | 404 | PASS |

## CSRF Verification

- CSRF tokens are present in all forms (confirmed by extracting from HTML)
- POST requests without valid CSRF token return 403 (enforced by `before_request` hook)
- Session-based CSRF protection is working correctly

## Notes

- macOS Sonoma/Sequoia uses port 5000 for AirPlay Receiver, so the app was tested on port 5050. The default `run.py` binds to port 5000 -- this will collide if AirPlay is enabled.
- Recipe title "Garlic Chicken" was confirmed present in both the detail page and search results.
- After deletion, the recipe correctly returns 404.
