# Shared Interface Spec -- [App Name]

Use this template when writing a shared interface spec for a Node/Express swarm
build. Every section is mandatory. Agents rely on exact names, signatures, and
examples.

## App Configuration

```javascript
// app.js -- Express app factory (do NOT start the server here)
const express = require('express');
const helmet = require('helmet');
const db = require('./db');

function createApp() {
  const app = express();

  // Security headers
  app.use(helmet());

  // Parse JSON and URL-encoded bodies
  app.use(express.json());
  app.use(express.urlencoded({ extended: false }));

  // Mount routers
  // app.use('/api/[resource]', require('./routes/[resource]'));

  // Error handler (must be last)
  app.use((err, req, res, next) => {
    console.error(err.stack);
    res.status(err.status || 500).json({ error: err.message || 'Internal server error' });
  });

  return app;
}

module.exports = createApp;
```

```javascript
// server.js -- Entry point (starts the server)
const createApp = require('./app');

const PORT = process.env.PORT || 3000;
const app = createApp();

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
```

**Requirements:** Include `express`, `helmet`, `better-sqlite3` in package.json.

**Rule:** `createApp()` is a factory function. Tests import it directly without
starting a server. `server.js` is the only file that calls `app.listen()`.

## Database Schema

```sql
-- Define all tables with explicit types and constraints
-- Include indexes on foreign key columns

CREATE TABLE IF NOT EXISTS [table] (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- columns...
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_[child]_[parent]_id ON [child]([parent]_id);
```

## Database Module

```javascript
// db.js -- Single shared database connection
const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const DB_PATH = process.env.DATABASE_PATH || path.join(__dirname, 'data', 'app.db');

// Ensure data directory exists
fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

// Run schema on first require
const schema = fs.readFileSync(path.join(__dirname, 'schema.sql'), 'utf-8');
db.exec(schema);

module.exports = db;
```

**Rule:** `better-sqlite3` is synchronous. No callbacks, no promises, no async/await
for database calls. This is intentional -- it simplifies agent code and avoids
async coordination bugs.

## Data Ownership

Define which module is the SOLE writer for each table. No two modules may
write to the same table.

| Table | Owner Module | Read By |
|-------|-------------|---------|
| [table] | models/[module].js | [list of readers] |

## Model Functions

For every function, include:
1. Full signature with JSDoc types
2. Return type
3. **Usage example** (critical for scalar returns and object shapes)

```javascript
// models/[resource].js

/**
 * Create a new project
 * @param {string} name
 * @param {string} color - hex color like '#6366f1'
 * @returns {number} The new project's ID
 *
 * Usage:
 *   const projectId = createProject(name, color);
 *   res.status(201).json({ id: projectId });
 */
function createProject(name, color) {
  const stmt = db.prepare('INSERT INTO projects (name, color) VALUES (?, ?)');
  const result = stmt.run(name, color);
  return result.lastInsertRowid;
}

/**
 * Get a project by ID
 * @param {number} id
 * @returns {Object|undefined} Project row or undefined if not found
 *
 * Usage:
 *   const project = getProject(id);
 *   if (!project) return res.status(404).json({ error: 'Not found' });
 *   res.json(project);
 */
function getProject(id) {
  return db.prepare('SELECT * FROM projects WHERE id = ?').get(id);
}
```

**Rule:** Every function that returns a scalar (number, string, boolean) MUST
include a usage example showing correct variable naming. Without this, agents
assume object returns and access `.id` on numbers.

**Rule:** `better-sqlite3` returns `undefined` (not `null`) when no row is found.
Always check with `if (!result)`, never `if (result === null)`.

## Route Table

| Method | Path | Handler | Status | Response |
|--------|------|---------|--------|----------|
| GET | /api/projects | projects.list | 200 | `{ projects: [...] }` |
| POST | /api/projects | projects.create | 201 | `{ id: number }` |
| GET | /api/projects/:id | projects.get | 200 | `{ project: {...} }` |
| PUT | /api/projects/:id | projects.update | 200 | `{ project: {...} }` |
| DELETE | /api/projects/:id | projects.delete | 204 | (empty) |

**Rule:** All routes return JSON. No HTML templates. No server-side rendering.

## JSON Response Shapes

For every route, specify the exact response shape:

```javascript
// GET /api/projects
// 200:
{ "projects": [{ "id": 1, "name": "My Project", "color": "#6366f1", "created_at": "2026-04-12 00:00:00" }] }

// POST /api/projects
// 201:
{ "id": 1 }

// GET /api/projects/:id
// 200:
{ "project": { "id": 1, "name": "My Project", "color": "#6366f1", "created_at": "2026-04-12 00:00:00" } }

// 404:
{ "error": "Not found" }
```

**Rule:** Response shapes are contracts. Agents must match these exactly. Wrap
single resources in a named key (`{ "project": {...} }`), wrap lists in a
named array (`{ "projects": [...] }`). Never return bare arrays or bare objects.

## Middleware Chain

Define the middleware order. Express applies middleware in registration order,
so this is a contract:

```javascript
// In createApp(), middleware is registered in this order:
// 1. helmet()               -- security headers
// 2. express.json()          -- parse JSON bodies
// 3. express.urlencoded()    -- parse form bodies
// 4. Route mounts            -- app.use('/api/...', router)
// 5. 404 handler             -- catch unmatched routes
// 6. Error handler           -- catch thrown errors
```

**Rule:** The 404 handler goes AFTER all route mounts but BEFORE the error
handler:

```javascript
// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Not found' });
});

// Error handler (4 args required for Express to recognize it)
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(err.status || 500).json({ error: err.message || 'Internal server error' });
});
```

## Input Validation

Define validation rules inline with route specs:

```javascript
// Name: trim whitespace, max 100 chars, required
const name = (req.body.name || '').trim().slice(0, 100);
if (!name) {
  return res.status(400).json({ error: 'Name is required' });
}

// Color: must be valid hex (#RRGGBB)
const COLOR_RE = /^#[0-9a-fA-F]{6}$/;
const color = COLOR_RE.test(req.body.color) ? req.body.color : '#6366f1';

// ID param: must be a positive integer
const id = Number(req.params.id);
if (!Number.isInteger(id) || id < 1) {
  return res.status(400).json({ error: 'Invalid ID' });
}
```

**Rule:** Validate in the route handler, not in middleware. Keep validation
visible and co-located with the route logic.

## Async Error Handling

Express does not catch errors in async handlers by default. Wrap async
route handlers:

```javascript
// Use this wrapper for any async route handler
function asyncHandler(fn) {
  return (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);
}

// Usage in routes:
router.get('/', asyncHandler(async (req, res) => {
  // ...
}));
```

**Rule:** Since `better-sqlite3` is synchronous, most handlers will NOT need
async. Only use `asyncHandler` if the route does async work (file I/O, HTTP
calls). Do not wrap synchronous handlers in `asyncHandler` unnecessarily.

## Test Structure

```javascript
// tests/[resource].test.js
const createApp = require('../app');
const request = require('supertest');
const db = require('../db');

// Reset database before each test
beforeEach(() => {
  db.exec('DELETE FROM [table]');
});

describe('GET /api/[resource]', () => {
  it('returns empty list', async () => {
    const res = await request(createApp()).get('/api/[resource]');
    expect(res.status).toBe(200);
    expect(res.body.[resource]).toEqual([]);
  });
});
```

**Requirements:** Include `jest` and `supertest` as devDependencies.

**Rule:** Tests import `createApp` (the factory), not `server.js`. Each test
gets a fresh app instance. Tests run against the same SQLite database but
clean tables in `beforeEach`.

## File Assignment Boundaries

List all files and which agent owns them. No file appears in two agents.

| File | Agent |
|------|-------|
| app.js | core |
| server.js | core |
| db.js | core |
| schema.sql | core |
| package.json | core |
| models/[resource].js | [resource] |
| routes/[resource].js | [resource] |
| tests/[resource].test.js | [resource] |
