# Assembly Fix Report -- Run 030

## Fix Attempt

**Errors addressed:** 6 (all 4 changed lines cover the 6 reported mismatches)
**Files modified:**
- `error-test-app/routes.py` -- replaced wrong function names on import line and 3 call sites

**Fixes applied:**
1. Line 3: `from models import get_all_items, add_item, remove_item` → `from models import get_all_bookmarks, create_bookmark, delete_bookmark`
2. Line 10: `get_all_items(db)` → `get_all_bookmarks(db)`
3. Line 21: `add_item(db, url, title)` → `create_bookmark(db, url, title)`
4. Line 28: `remove_item(db, bookmark_id)` → `delete_bookmark(db, bookmark_id)`

**Commit:** `4301642` -- fix(error-test-app): correct function names in routes.py to match spec

STATUS: FIXED
