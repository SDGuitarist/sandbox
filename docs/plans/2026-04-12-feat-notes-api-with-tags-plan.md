---
title: "feat: Notes API with Tags"
type: feat
status: active
date: 2026-04-12
swarm: true
origin: docs/brainstorms/2026-04-12-notes-api-brainstorm.md
feed_forward:
  risk: "Whether the swarm build pattern translates cleanly from Flask to Node/Express -- first Node swarm build, untested stack switch"
  verify_first: true
---

# feat: Notes API with Tags

REST API for managing notes with tags. Node/Express + SQLite (better-sqlite3).
First Node/Express swarm build in the sandbox -- validates stack-agnostic claim.

(see brainstorm: docs/brainstorms/2026-04-12-notes-api-brainstorm.md)

## Enhancement Summary

**Deepened on:** 2026-04-12
**Review agents used:** architecture-strategist, security-sentinel, performance-oracle, code-simplicity-reviewer, Context7 (Express, better-sqlite3, Jest)

### Key Improvements
1. Error handler no longer leaks internal SQLite messages (Security P1)
2. Input validation adds type checks and rejects over-length instead of silent truncation (Security P2)
3. Explicit body size limit on express.json() (Security P2)
4. Explicit prohibition rule against importing db.js in route files (Architecture)
5. Concrete route handler example added to spec (Architecture)
6. Default LIMIT on list queries as safety net (Performance)
7. Removed redundant Endpoint Registry, express.urlencoded(), getDb() singleton (Simplicity)

## Acceptance Criteria

- [ ] Create, read, update, delete notes (title required, content optional)
- [ ] Create, read, update, delete tags (name required, unique)
- [ ] Add tag to note, remove tag from note
- [ ] GET note returns inline tags array
- [ ] GET /api/tags/:id/notes returns notes for a tag
- [ ] Input validation at handler boundary (lengths, types, required fields)
- [ ] Consistent JSON error responses (`{ "error": "message" }`)
- [ ] ON DELETE CASCADE on junction table FKs
- [ ] Composite PK on note_tags (no surrogate ID)
- [ ] All tests pass with Jest + supertest
- [ ] App starts and all routes respond in smoke test

## File List

```
notes-api/
  app.js                  # Express app factory (createApp)
  server.js               # Entry point (app.listen)
  db.js                   # better-sqlite3 connection + schema init
  schema.sql              # SQLite CREATE TABLEs
  package.json            # Dependencies + scripts
  models/
    notes.js              # Note CRUD + note_tags write functions
    tags.js               # Tag CRUD + read notes-by-tag
  routes/
    notes.js              # /api/notes routes + /api/notes/:id/tags
    tags.js               # /api/tags routes + /api/tags/:id/notes
  tests/
    notes.test.js         # Note + association endpoint tests
    tags.test.js          # Tag endpoint tests
```

## Shared Interface Spec

### Database Schema

```sql
-- schema.sql
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS note_tags (
    note_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (note_id, tag_id),
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_note_tags_tag_id ON note_tags(tag_id);
```

### Database Module

```javascript
// db.js
const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

function createDb(dbPath) {
  if (!dbPath) {
    dbPath = process.env.DATABASE_PATH || path.join(__dirname, 'data', 'app.db');
  }

  // :memory: needs no directory
  if (dbPath !== ':memory:') {
    fs.mkdirSync(path.dirname(dbPath), { recursive: true });
  }

  const db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');

  // Run schema on creation
  const schema = fs.readFileSync(path.join(__dirname, 'schema.sql'), 'utf-8');
  db.exec(schema);

  return db;
}

// For tests: create isolated in-memory DB
function createTestDb() {
  return createDb(':memory:');
}

module.exports = { createDb, createTestDb };
```

**Rules:**
- `better-sqlite3` is synchronous. No callbacks, no promises, no async/await for DB calls.
- `PRAGMA foreign_keys = ON` is per-connection (not persistent like WAL). It MUST be set in `createDb`.
- `createTestDb()` returns an isolated `:memory:` database for tests.
- `server.js` calls `createDb()` directly -- no singleton pattern.

### App Factory

```javascript
// app.js
const express = require('express');
const helmet = require('helmet');

function createApp(db) {
  if (!db) throw new Error('db argument is required');

  const app = express();

  // Make db available to routes via app.locals
  app.locals.db = db;

  // Middleware (order matters)
  app.use(helmet());
  app.use(express.json({ limit: '50kb' }));

  // Mount routers
  app.use('/api/notes', require('./routes/notes'));
  app.use('/api/tags', require('./routes/tags'));

  // 404 handler (after all route mounts)
  app.use((req, res) => {
    res.status(404).json({ error: 'Not found' });
  });

  // Error handler (must have 4 args for Express to recognize it)
  // Never leak internal error messages -- only pass through errors with explicit status
  app.use((err, req, res, next) => {
    console.error(err.stack);
    const status = err.status || 500;
    const message = status === 500 ? 'Internal server error' : err.message;
    res.status(status).json({ error: message });
  });

  return app;
}

module.exports = createApp;
```

**Rules:**
- `createApp(db)` requires a `db` argument. It does NOT import db.js or call getDb().
- Routes access the database via `req.app.locals.db`.
- Route handler paths are RELATIVE to the mount prefix. Use `router.get('/')` not `router.get('/api/notes/')`.
- **Route files MUST NOT `require('../db')` or call `createDb()`.** They access the database exclusively via `req.app.locals.db`. Importing db.js in a route file will break test isolation.

```javascript
// server.js
const createApp = require('./app');
const { createDb } = require('./db');

const PORT = process.env.PORT || 3000;
const db = createDb();
const app = createApp(db);

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
```

### Data Ownership

| Table | Owner (writes) | Read By |
|-------|---------------|---------|
| notes | models/notes.js | routes/notes.js |
| tags | models/tags.js | routes/tags.js |
| note_tags | models/notes.js | models/tags.js (read-only), routes/notes.js |

Routes NEVER write SQL directly. All writes go through model functions.
`models/tags.js` may READ from `note_tags` (for notes-by-tag query) but NEVER writes to it.

### Model Functions -- notes (models/notes.js)

All functions take `db` (better-sqlite3 Database instance) as first argument.

```javascript
// models/notes.js
// Access db from route handler: const db = req.app.locals.db;

/**
 * Get all notes (without tags)
 * @param {Database} db
 * @returns {Object[]} Array of note rows
 *
 * Usage:
 *   const notes = getAllNotes(db);
 *   res.json({ notes });
 */
function getAllNotes(db) {
  return db.prepare('SELECT * FROM notes ORDER BY created_at DESC LIMIT 200').all();
}

/**
 * Get a single note by ID
 * @param {Database} db
 * @param {number} id
 * @returns {Object|undefined} Note row or undefined
 *
 * Usage:
 *   const note = getNoteById(db, id);
 *   if (!note) return res.status(404).json({ error: 'Note not found' });
 *   res.json({ note });
 */
function getNoteById(db, id) {
  return db.prepare('SELECT * FROM notes WHERE id = ?').get(id);
}

/**
 * Create a new note
 * @param {Database} db
 * @param {string} title
 * @param {string} content
 * @returns {number} The new note's ID (plain integer, NOT an object)
 *
 * Usage:
 *   const noteId = createNote(db, title, content);
 *   res.status(201).json({ id: noteId });
 */
function createNote(db, title, content) {
  const result = db.prepare(
    'INSERT INTO notes (title, content) VALUES (?, ?)'
  ).run(title, content);
  return result.lastInsertRowid;
}

/**
 * Update an existing note
 * @param {Database} db
 * @param {number} id
 * @param {string} title
 * @param {string} content
 * @returns {number} Number of rows changed (0 if not found, 1 if updated)
 *
 * Usage:
 *   const changes = updateNote(db, id, title, content);
 *   if (changes === 0) return res.status(404).json({ error: 'Note not found' });
 */
function updateNote(db, id, title, content) {
  const result = db.prepare(
    "UPDATE notes SET title = ?, content = ?, updated_at = datetime('now') WHERE id = ?"
  ).run(title, content, id);
  return result.changes;
}

/**
 * Delete a note (cascades to note_tags)
 * @param {Database} db
 * @param {number} id
 * @returns {number} Number of rows deleted (0 if not found, 1 if deleted)
 *
 * Usage:
 *   const changes = deleteNote(db, id);
 *   if (changes === 0) return res.status(404).json({ error: 'Note not found' });
 *   res.status(204).end();
 */
function deleteNote(db, id) {
  return db.prepare('DELETE FROM notes WHERE id = ?').run(id).changes;
}

/**
 * Get tags for a single note
 * @param {Database} db
 * @param {number} noteId
 * @returns {Object[]} Array of tag rows [{id, name, created_at}]
 *
 * Usage:
 *   const tags = getTagsForNote(db, noteId);
 *   res.json({ note: { ...note, tags } });
 */
function getTagsForNote(db, noteId) {
  return db.prepare(
    `SELECT t.id, t.name, t.created_at
     FROM tags t
     JOIN note_tags nt ON t.id = nt.tag_id
     WHERE nt.note_id = ?
     ORDER BY t.name`
  ).all(noteId);
}

/**
 * Add a tag to a note (write to note_tags junction table)
 * @param {Database} db
 * @param {number} noteId
 * @param {number} tagId
 * @returns {boolean} true if inserted, false if already existed
 *
 * Usage:
 *   const added = addTagToNote(db, noteId, tagId);
 *   if (!added) return res.status(409).json({ error: 'Tag already assigned to this note' });
 *   res.status(201).json({ note_id: noteId, tag_id: tagId });
 */
function addTagToNote(db, noteId, tagId) {
  try {
    db.prepare('INSERT INTO note_tags (note_id, tag_id) VALUES (?, ?)').run(noteId, tagId);
    return true;
  } catch (err) {
    if (err.code === 'SQLITE_CONSTRAINT_PRIMARYKEY') {
      return false;
    }
    throw err;
  }
}

/**
 * Remove a tag from a note (idempotent)
 * @param {Database} db
 * @param {number} noteId
 * @param {number} tagId
 * @returns {void}
 *
 * Usage:
 *   removeTagFromNote(db, noteId, tagId);
 *   res.status(204).end();
 */
function removeTagFromNote(db, noteId, tagId) {
  db.prepare('DELETE FROM note_tags WHERE note_id = ? AND tag_id = ?').run(noteId, tagId);
}

module.exports = {
  getAllNotes,
  getNoteById,
  createNote,
  updateNote,
  deleteNote,
  getTagsForNote,
  addTagToNote,
  removeTagFromNote
};
```

### Model Functions -- tags (models/tags.js)

```javascript
// models/tags.js

/**
 * Get all tags
 * @param {Database} db
 * @returns {Object[]} Array of tag rows
 *
 * Usage:
 *   const tags = getAllTags(db);
 *   res.json({ tags });
 */
function getAllTags(db) {
  return db.prepare('SELECT * FROM tags ORDER BY name LIMIT 200').all();
}

/**
 * Get a single tag by ID
 * @param {Database} db
 * @param {number} id
 * @returns {Object|undefined} Tag row or undefined
 *
 * Usage:
 *   const tag = getTagById(db, id);
 *   if (!tag) return res.status(404).json({ error: 'Tag not found' });
 */
function getTagById(db, id) {
  return db.prepare('SELECT * FROM tags WHERE id = ?').get(id);
}

/**
 * Create a new tag
 * @param {Database} db
 * @param {string} name
 * @returns {number} The new tag's ID (plain integer, NOT an object)
 *
 * Usage:
 *   const tagId = createTag(db, name);
 *   res.status(201).json({ id: tagId });
 */
function createTag(db, name) {
  const result = db.prepare('INSERT INTO tags (name) VALUES (?)').run(name);
  return result.lastInsertRowid;
}

/**
 * Update a tag name
 * @param {Database} db
 * @param {number} id
 * @param {string} name
 * @returns {number} Number of rows changed (0 if not found)
 *
 * Usage:
 *   const changes = updateTag(db, id, name);
 *   if (changes === 0) return res.status(404).json({ error: 'Tag not found' });
 */
function updateTag(db, id, name) {
  return db.prepare('UPDATE tags SET name = ? WHERE id = ?').run(name, id).changes;
}

/**
 * Delete a tag (cascades to note_tags)
 * @param {Database} db
 * @param {number} id
 * @returns {number} Number of rows deleted (0 if not found)
 *
 * Usage:
 *   const changes = deleteTag(db, id);
 *   if (changes === 0) return res.status(404).json({ error: 'Tag not found' });
 *   res.status(204).end();
 */
function deleteTag(db, id) {
  return db.prepare('DELETE FROM tags WHERE id = ?').run(id).changes;
}

/**
 * Get notes for a tag (READ ONLY from note_tags -- does not write)
 * @param {Database} db
 * @param {number} tagId
 * @returns {Object[]} Array of note rows
 *
 * Usage:
 *   const notes = getNotesForTag(db, tagId);
 *   res.json({ notes });
 */
function getNotesForTag(db, tagId) {
  return db.prepare(
    `SELECT n.id, n.title, n.content, n.created_at, n.updated_at
     FROM notes n
     JOIN note_tags nt ON n.id = nt.note_id
     WHERE nt.tag_id = ?
     ORDER BY n.created_at DESC`
  ).all(tagId);
}

module.exports = {
  getAllTags,
  getTagById,
  createTag,
  updateTag,
  deleteTag,
  getNotesForTag
};
```

### Route Table

| Method | Path | Handler | Status | Response |
|--------|------|---------|--------|----------|
| GET | /api/notes | notes.list | 200 | `{ "notes": [...] }` |
| POST | /api/notes | notes.create | 201 | `{ "id": number }` |
| GET | /api/notes/:id | notes.get | 200 | `{ "note": {..., "tags": [...]} }` |
| PUT | /api/notes/:id | notes.update | 200 | `{ "note": {...} }` |
| DELETE | /api/notes/:id | notes.delete | 204 | (empty) |
| POST | /api/notes/:id/tags | notes.addTag | 201 | `{ "note_id": number, "tag_id": number }` |
| DELETE | /api/notes/:id/tags/:tagId | notes.removeTag | 204 | (empty) |
| GET | /api/tags | tags.list | 200 | `{ "tags": [...] }` |
| POST | /api/tags | tags.create | 201 | `{ "id": number }` |
| GET | /api/tags/:id | tags.get | 200 | `{ "tag": {...} }` |
| PUT | /api/tags/:id | tags.update | 200 | `{ "tag": {...} }` |
| DELETE | /api/tags/:id | tags.delete | 204 | (empty) |
| GET | /api/tags/:id/notes | tags.getNotes | 200 | `{ "notes": [...] }` |

**CRITICAL:** Route handler paths are RELATIVE to the mount prefix. The notes router is mounted at `/api/notes`, so use `router.get('/')` NOT `router.get('/api/notes')`.

### Example Route Handler

This concrete example shows the correct pattern for all route handlers. Agents MUST follow this pattern:

```javascript
// routes/notes.js (example: GET /api/notes/:id with inline tags)
const express = require('express');
const router = express.Router();
const { getNoteById, getTagsForNote } = require('../models/notes');

// GET /:id -- note that this is RELATIVE to mount prefix /api/notes
router.get('/:id', (req, res) => {
  const db = req.app.locals.db;  // <-- ALWAYS get db this way, NEVER import db.js

  const id = Number(req.params.id);
  if (!Number.isInteger(id) || id < 1) {
    return res.status(400).json({ error: 'Invalid ID' });
  }

  const note = getNoteById(db, id);
  if (!note) return res.status(404).json({ error: 'Note not found' });

  const tags = getTagsForNote(db, id);
  res.json({ note: { ...note, tags } });
});

module.exports = router;
```

### JSON Response Shapes

```javascript
// GET /api/notes
// 200:
{ "notes": [{ "id": 1, "title": "My Note", "content": "...", "created_at": "2026-04-12 00:00:00", "updated_at": "2026-04-12 00:00:00" }] }

// POST /api/notes
// 201:
{ "id": 1 }

// GET /api/notes/:id
// 200:
{ "note": { "id": 1, "title": "My Note", "content": "...", "created_at": "...", "updated_at": "...", "tags": [{ "id": 1, "name": "urgent", "created_at": "..." }] } }

// PUT /api/notes/:id
// 200:
{ "note": { "id": 1, "title": "Updated", "content": "...", "created_at": "...", "updated_at": "..." } }

// DELETE /api/notes/:id
// 204: (empty body)

// POST /api/notes/:id/tags
// Request body: { "tag_id": 5 }
// 201:
{ "note_id": 1, "tag_id": 5 }
// 409 (already assigned):
{ "error": "Tag already assigned to this note" }

// DELETE /api/notes/:id/tags/:tagId
// 204: (empty body, idempotent)

// GET /api/tags
// 200:
{ "tags": [{ "id": 1, "name": "urgent", "created_at": "..." }] }

// POST /api/tags
// Request body: { "name": "urgent" }
// 201:
{ "id": 1 }
// 409 (duplicate name):
{ "error": "Tag name already exists" }

// GET /api/tags/:id
// 200:
{ "tag": { "id": 1, "name": "urgent", "created_at": "..." } }

// PUT /api/tags/:id
// Request body: { "name": "new-name" }
// 200:
{ "tag": { "id": 1, "name": "new-name", "created_at": "..." } }

// DELETE /api/tags/:id
// 204: (empty body)

// GET /api/tags/:id/notes
// 200:
{ "notes": [{ "id": 1, "title": "...", "content": "...", "created_at": "...", "updated_at": "..." }] }

// Error responses (all endpoints):
// 400: { "error": "Title is required" }
// 404: { "error": "Note not found" }
// 409: { "error": "Tag name already exists" }
// 500: { "error": "Internal server error" }
```

### Input Validation Rules

Apply at the handler boundary, inline in the route handler:

```javascript
// Note title: type check, trim, required, max 200 chars (reject, don't truncate)
if (typeof req.body.title !== 'string') {
  return res.status(400).json({ error: 'Title must be a string' });
}
const title = req.body.title.trim();
if (!title) return res.status(400).json({ error: 'Title is required' });
if (title.length > 200) return res.status(400).json({ error: 'Title must be 200 characters or less' });

// Note content: type check, trim, optional (defaults to ''), max 10000 chars
const rawContent = req.body.content;
if (rawContent !== undefined && typeof rawContent !== 'string') {
  return res.status(400).json({ error: 'Content must be a string' });
}
const content = (rawContent || '').trim();
if (content.length > 10000) return res.status(400).json({ error: 'Content must be 10000 characters or less' });

// Tag name: type check, trim, required, max 50 chars
if (typeof req.body.name !== 'string') {
  return res.status(400).json({ error: 'Name must be a string' });
}
const name = req.body.name.trim();
if (!name) return res.status(400).json({ error: 'Name is required' });
if (name.length > 50) return res.status(400).json({ error: 'Name must be 50 characters or less' });

// ID param: must be a positive integer
const id = Number(req.params.id);
if (!Number.isInteger(id) || id < 1) {
  return res.status(400).json({ error: 'Invalid ID' });
}

// tag_id in request body (for POST /api/notes/:id/tags):
if (typeof req.body.tag_id !== 'number') {
  return res.status(400).json({ error: 'tag_id must be a number' });
}
const tagId = req.body.tag_id;
if (!Number.isInteger(tagId) || tagId < 1) {
  return res.status(400).json({ error: 'Invalid tag_id' });
}
```

### Middleware Chain

```javascript
// In createApp(), middleware registered in this order:
// 1. helmet()               -- security headers
// 2. express.json({limit})   -- parse JSON bodies (50kb limit)
// 3. app.use('/api/notes', require('./routes/notes'))
// 4. app.use('/api/tags', require('./routes/tags'))
// 5. 404 handler             -- catch unmatched routes
// 6. Error handler           -- catch thrown errors (4 args, never leaks internal messages)
```

### Test Structure

```javascript
// tests/notes.test.js (pattern for both test files)
const createApp = require('../app');
const { createTestDb } = require('../db');
const request = require('supertest');

let db;
let app;

beforeEach(() => {
  db = createTestDb();       // Fresh in-memory DB per test
  app = createApp(db);       // Inject test DB into app
});

afterEach(() => {
  db.close();                // Clean up connection
});

describe('GET /api/notes', () => {
  it('returns empty list initially', async () => {
    const res = await request(app).get('/api/notes');
    expect(res.status).toBe(200);
    expect(res.body.notes).toEqual([]);
  });
});
```

**Rules:**
- Tests import `createApp` and `createTestDb`, NOT `server.js`.
- Each test gets a fresh in-memory DB via `createTestDb()`.
- `afterEach` closes the DB connection.
- No shared state between tests.

### package.json

```json
{
  "name": "notes-api",
  "version": "1.0.0",
  "description": "REST API for notes with tags",
  "main": "server.js",
  "scripts": {
    "start": "node server.js",
    "test": "jest --verbose"
  },
  "dependencies": {
    "better-sqlite3": "^11.0.0",
    "express": "^4.21.0",
    "helmet": "^8.0.0"
  },
  "devDependencies": {
    "jest": "^29.7.0",
    "supertest": "^7.0.0"
  }
}
```

## Design Decisions (resolved from SpecFlow analysis)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Association request body | `{ "tag_id": 5 }` | Client creates tag first, then associates. Simple, no find-or-create logic. |
| Cascade behavior | ON DELETE CASCADE on both FKs | Deleting a note removes its associations. Deleting a tag removes its associations. Neither deletes the other entity. |
| Tag name uniqueness | UNIQUE constraint, 409 on duplicate | Prevents duplicate tags. Clear error for clients. |
| Update semantics | PUT (full replacement) | Title required, content required. Simpler than PATCH for MVP. |
| Duplicate association | 409 Conflict | Clear signal to client. `addTagToNote` catches SQLITE_CONSTRAINT_PRIMARYKEY. |
| Tags in list response | NOT included in GET /api/notes | Only in GET /api/notes/:id. Keeps list query simple. |
| Delete association | Idempotent (204 always) | DELETE /api/notes/:id/tags/:tagId returns 204 even if association didn't exist. |
| Content field | Optional, defaults to '' | Quick capture -- a note with just a title is valid. |
| DELETE response | 204 No Content | No body returned. |
| Timestamps | ISO 8601 strings via SQLite datetime() | Consistent with sandbox pattern. |
| Test isolation | `createTestDb()` returns `:memory:` DB | Each test gets a fresh DB injected into `createApp(db)`. |
| PRAGMA foreign_keys | Set per-connection in `createDb()` | Not persistent -- must be set every time. Required for CASCADE. |
| Tag creation behavior | 409 on duplicate (not upsert) | Brainstorm suggested upsert but plan chose strict reject -- clearer API semantics, clients know exactly what happened. Deviation acknowledged. |
| Synchronous DB | Acceptable for MVP | better-sqlite3 blocks the event loop during queries. Fine for single-user; would need worker threads or async driver for concurrent load. |
| List query safety | Default LIMIT 200 | Prevents accidental performance cliff if data grows. Not full pagination -- just a safety net. |
| Error handler | Never leaks internal messages | 500 errors always return generic "Internal server error". Only errors with explicit `err.status` pass through `err.message`. |

## Plan Quality Gate

1. **What exactly is changing?** New `notes-api/` directory with 11 files (app, server, db, schema, package.json, 2 model files, 2 route files, 2 test files).
2. **What must not change?** No files outside `notes-api/`. No changes to autopilot skill, agents, or templates.
3. **How will we know it worked?** All 13 endpoints return expected status codes in smoke test. Jest tests pass. `npm start` starts without errors.
4. **What is the most likely way this plan is wrong?** The `createApp(db)` injection pattern and `req.app.locals.db` access may not work as expected in the route files -- this is the novel untested pattern for Node swarm builds. If routes import `db.js` directly instead of using `req.app.locals.db`, test isolation breaks.

## Feed-Forward

- **Hardest decision:** How to handle test DB isolation in Node. Chose `createApp(db)` parameter injection with `app.locals.db`, similar to Flask's app factory pattern. This avoids routes importing the db module directly.
- **Rejected alternatives:** (1) Environment variable override for DB path in tests -- fragile, doesn't support parallel tests. (2) Jest module mocking -- brittle, hides real behavior. (3) Global test setup/teardown -- shares state between tests.
- **Least confident:** Whether `req.app.locals.db` works correctly when routes are loaded via `require('./routes/notes')` in the app factory. The routes module is required once but executed per-request -- `req.app.locals.db` should resolve to the injected DB each time. But this pattern has never been tested in this repo's swarm builds. If it fails, the fix is to pass `db` as a parameter to a router factory function instead.

## Swarm Agent Assignment

**Total agents:** 3
**Total files:** 11
**Validation:** No file appears in multiple assignments

### Shared Interface Spec (included in every agent's context)

All agents receive the full Shared Interface Spec from this plan (Database Schema, Database Module, App Factory, Data Ownership, Model Functions, Route Table, Example Route Handler, JSON Response Shapes, Input Validation Rules, Middleware Chain, Test Structure, package.json). This is the coordination contract -- agents must not deviate from it.

### Agent: core

**Files:**
- `notes-api/app.js`
- `notes-api/server.js`
- `notes-api/db.js`
- `notes-api/schema.sql`
- `notes-api/package.json`

**Responsibility:** Build the Express app factory, server entry point, database module (with `createDb` and `createTestDb` -- no singleton), SQLite schema, and package.json -- exactly matching the shared interface spec.

---

### Agent: notes

**Files:**
- `notes-api/models/notes.js`
- `notes-api/routes/notes.js`
- `notes-api/tests/notes.test.js`

**Responsibility:** Build note CRUD model functions, note_tags write functions (`addTagToNote`, `removeTagFromNote`, `getTagsForNote`), all `/api/notes` route handlers (including `/api/notes/:id/tags` sub-routes), and tests for all note and association endpoints. Access DB via `req.app.locals.db`. Route paths are RELATIVE to mount prefix.

---

### Agent: tags

**Files:**
- `notes-api/models/tags.js`
- `notes-api/routes/tags.js`
- `notes-api/tests/tags.test.js`

**Responsibility:** Build tag CRUD model functions, `getNotesForTag` (read-only from note_tags), all `/api/tags` route handlers (including `/api/tags/:id/notes`), and tests for all tag endpoints. Access DB via `req.app.locals.db`. Route paths are RELATIVE to mount prefix. Does NOT write to note_tags table.

---

STATUS: PASS

## Sources

- **Origin brainstorm:** [docs/brainstorms/2026-04-12-notes-api-brainstorm.md](docs/brainstorms/2026-04-12-notes-api-brainstorm.md) -- key decisions: nested association routes, composite PK, no auth, no pagination
- **Spec template:** [docs/templates/shared-spec-node.md](docs/templates/shared-spec-node.md)
- **Prior lessons:** recipe-organizer (composite PK), bookmark-manager (tag queries, endpoint registry), autopilot-swarm-orchestration (scalar returns, data ownership), express-handler-boundary-validation (input validation), flask-swarm-acid-test (test isolation, usage examples), personal-finance-tracker (route prefix doubling)
