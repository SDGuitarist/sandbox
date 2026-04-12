---
title: "test: Error Injection -- Swarm Pipeline Failure Paths"
type: test
status: active
date: 2026-04-12
swarm: true
origin: docs/brainstorms/2026-04-12-error-injection-brainstorm.md
feed_forward:
  risk: "Whether assembly-fix agent can correct a spec violation from a contract-check report alone"
  verify_first: true
---

# test: Error Injection -- Swarm Pipeline Failure Paths

Minimal bookmark app with a DELIBERATE spec violation injected into the routes
agent. Tests whether the verification pipeline detects and recovers.

## Acceptance Criteria

- [ ] Spec-contract-checker detects the function name mismatch
- [ ] Assembly-fix agent corrects the error
- [ ] Smoke test passes after fix
- [ ] App works end-to-end after recovery

## File List

```
error-test-app/
  app.py              # Flask app factory
  schema.sql          # Single table
  requirements.txt    # Flask, flask-wtf
  models.py           # get_all_bookmarks, create_bookmark, delete_bookmark
  routes.py           # List, create, delete routes
  templates/
    base.html         # Minimal base
    list.html         # Bookmark list with add/delete
```

## Shared Interface Spec

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### App Factory

```python
import os, sqlite3
from flask import Flask, g

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('bookmarks.db')
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db: db.close()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev')
    app.teardown_appcontext(close_db)
    from flask_wtf import CSRFProtect
    CSRFProtect(app)
    with app.app_context():
        db = get_db()
        with open('schema.sql') as f:
            db.executescript(f.read())
    from routes import bp
    app.register_blueprint(bp)
    return app

if __name__ == '__main__':
    create_app().run(debug=True)
```

### Model Functions (models.py)

```python
def get_all_bookmarks(db):
    """Returns: list[Row] -- all bookmarks ordered by created_at DESC"""
    return db.execute('SELECT * FROM bookmarks ORDER BY created_at DESC').fetchall()

def create_bookmark(db, url, title):
    """Returns: int (new bookmark ID)
    Usage: bookmark_id = create_bookmark(db, url, title)
    """
    cursor = db.execute('INSERT INTO bookmarks (url, title) VALUES (?, ?)', (url, title))
    db.commit()
    return cursor.lastrowid

def delete_bookmark(db, bookmark_id):
    """Returns: None"""
    db.execute('DELETE FROM bookmarks WHERE id = ?', (bookmark_id,))
    db.commit()
```

### Route Table

| Method | Path | Handler | Status | Template |
|--------|------|---------|--------|----------|
| GET | / | index | 200 | list.html |
| POST | /add | add | 302 | redirect to / |
| POST | /delete/\<int:bookmark_id\> | delete | 302 | redirect to / |

### Template Render Context

```python
# list.html expects:
render_template('list.html', bookmarks=get_all_bookmarks(db))
```

### Data Ownership

| Table | Owner | Read By |
|-------|-------|---------|
| bookmarks | models.py | routes.py |

## ERROR INJECTION INSTRUCTIONS

**Agent: routes** will be given WRONG function names in its prompt:
- Instead of `get_all_bookmarks` → told to use `get_all_items`
- Instead of `create_bookmark` → told to use `add_item`
- Instead of `delete_bookmark` → told to use `remove_item`

This simulates the most common real swarm failure: agents inventing their own names instead of following the spec.

**Expected pipeline behavior:**
1. Spec-contract-checker reads routes.py and models.py, detects mismatched names → STATUS: FAIL
2. Assembly-fix reads the contract-check report + plan, corrects routes.py → STATUS: FIXED
3. Re-run contract check → STATUS: PASS
4. Smoke test → STATUS: PASS

## Swarm Agent Assignment

**Total agents:** 3
**Total files:** 7

### Agent: core

**Files:**
- error-test-app/app.py
- error-test-app/schema.sql
- error-test-app/requirements.txt
- error-test-app/templates/base.html

**Responsibility:** App factory, schema, requirements, base template. Normal instructions -- no errors injected.

---

### Agent: models

**Files:**
- error-test-app/models.py

**Responsibility:** Model functions: get_all_bookmarks, create_bookmark, delete_bookmark. Normal instructions -- CORRECT function names per spec.

---

### Agent: routes (ERROR INJECTION TARGET)

**Files:**
- error-test-app/routes.py
- error-test-app/templates/list.html

**Responsibility:** Routes and list template. DELIBERATELY given WRONG function names to trigger spec violation. Uses `get_all_items`, `add_item`, `remove_item` instead of spec names.

---

## Plan Quality Gate

1. **What exactly is changing?** New error-test-app/ directory with 7 files, one containing deliberate errors.
2. **What must not change?** No files outside error-test-app/. Pipeline infrastructure unchanged.
3. **How will we know it worked?** Contract checker catches the error. Assembly-fix corrects it. Smoke test passes after fix.
4. **What is the most likely way this plan is wrong?** Assembly-fix may not have enough context from the contract-check report to know the correct function names. It needs both the report AND the plan's model function signatures.

## Feed-Forward

- **Hardest decision:** What error to inject. Function name mismatch is the highest-value test because it's the actual failure mode seen in prior builds.
- **Rejected alternatives:** Syntax errors (trivial), missing CSRF (caught at runtime not contract check), wrong return types (too subtle).
- **Least confident:** Whether the assembly-fix → re-check → smoke-test pipeline actually works end-to-end. It's never been exercised.
