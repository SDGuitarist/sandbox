# Spec Contract Check Report -- Run 030

## Results: 15 checks, 9 PASS, 6 FAIL

All 6 failures in error-test-app/routes.py -- wrong function names:

| Line | Current (wrong) | Required (spec) |
|------|----------------|-----------------|
| 3 | from models import get_all_items, add_item, remove_item | from models import get_all_bookmarks, create_bookmark, delete_bookmark |
| 10 | get_all_items(db) | get_all_bookmarks(db) |
| 21 | add_item(db, url, title) | create_bookmark(db, url, title) |
| 28 | remove_item(db, bookmark_id) | delete_bookmark(db, bookmark_id) |

models.py is correct. Only routes.py needs fixing.

STATUS: FAIL
