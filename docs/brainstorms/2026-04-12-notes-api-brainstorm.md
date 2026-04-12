---
title: "Notes API with Tags -- Node/Express REST API"
date: 2026-04-12
status: complete
type: brainstorm
---

# Notes API

## What We're Building

A REST API for managing notes with tags, built with Node/Express + SQLite (better-sqlite3). This is the first Node/Express build in the sandbox -- all prior builds used Flask. The API supports CRUD for notes, CRUD for tags, and many-to-many note-tag associations. No frontend, no auth -- pure JSON API.

## Why This Approach

- **Node/Express + better-sqlite3** -- description explicitly requests Node/Express; better-sqlite3 is synchronous which eliminates async coordination bugs in swarm builds
- **REST JSON API** -- no server-side rendering; clean separation makes testing straightforward with supertest
- **Swarm-compatible** -- the shared-spec-node.md template exists and the architecture (app factory, separate models/routes/tests) maps cleanly to agent file assignments
- **SQLite** -- consistent with all sandbox apps; WAL mode for safe concurrent reads during testing

## Key Decisions

1. **Pure REST API, no frontend** -- JSON in, JSON out. All responses wrapped in named keys (`{ "notes": [...] }`, `{ "note": {...} }`)
2. **Three tables: notes, tags, note_tags** -- `note_tags` uses composite PRIMARY KEY (note_id, tag_id), no surrogate ID (lesson from recipe-organizer)
3. **Input validation at handler boundary** -- body-shape check, per-field length caps (title: 200 chars, content: 10000 chars, tag name: 50 chars), ID param as positive integer (lesson from express-handler-boundary-validation)
4. **Tags deduplicated by name** -- UNIQUE constraint on `tags.name`; creating a tag that exists returns the existing one (upsert or lookup pattern)
5. **Association endpoints on notes** -- `POST /api/notes/:id/tags` to add, `DELETE /api/notes/:id/tags/:tagId` to remove. Tags for a note returned inline with GET note.
6. **No pagination for MVP** -- single-user, personal-scale data; list endpoints return all records
7. **Scalar returns documented with usage examples** -- every model function that returns a number includes usage showing it's a plain integer (lesson from autopilot-swarm-orchestration)

## Scope

### In Scope
- CRUD for notes (title, content, timestamps)
- CRUD for tags (name, timestamps)
- Note-tag associations (add, remove, list tags per note, list notes per tag)
- Input validation (lengths, types, required fields)
- Error responses (400, 404, 500) with consistent JSON shape
- Test suite with Jest + supertest
- helmet for security headers

### Out of Scope
- Authentication / authorization
- Full-text search
- Pagination / sorting / filtering
- Rate limiting
- Frontend / UI
- WebSocket notifications

## Data Model Sketch

- **notes**: id (INTEGER PK), title (TEXT NOT NULL), content (TEXT NOT NULL DEFAULT ''), created_at (TEXT), updated_at (TEXT)
- **tags**: id (INTEGER PK), name (TEXT UNIQUE NOT NULL), created_at (TEXT)
- **note_tags**: note_id (FK), tag_id (FK), composite PRIMARY KEY (note_id, tag_id)

## API Endpoints Sketch

| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/notes | List all notes |
| POST | /api/notes | Create note |
| GET | /api/notes/:id | Get note (with tags) |
| PUT | /api/notes/:id | Update note |
| DELETE | /api/notes/:id | Delete note (cascades tags) |
| GET | /api/tags | List all tags |
| POST | /api/tags | Create tag |
| GET | /api/tags/:id | Get tag (with note count) |
| PUT | /api/tags/:id | Update tag name |
| DELETE | /api/tags/:id | Delete tag (cascades associations) |
| POST | /api/notes/:id/tags | Add tag to note |
| DELETE | /api/notes/:id/tags/:tagId | Remove tag from note |
| GET | /api/tags/:id/notes | List notes for a tag |

## Prior Art (from solution docs)

- Composite PK on junction tables, no surrogate ID (recipe-organizer-swarm-build)
- Handler-boundary validation: body-shape, field lengths, ID params (express-handler-boundary-validation)
- EXISTS subqueries for tag lookups, batch-fetch tags for lists (bookmark-manager-swarm-build)
- Scalar return usage examples mandatory in spec (autopilot-swarm-orchestration)
- Data ownership table in spec -- one writer per table (autopilot-swarm-orchestration)
- Endpoint Registry for swarm builds (bookmark-manager-swarm-build)

## Open Questions

None -- all key decisions resolved from the brief and prior lessons.

## Feed-Forward

- **Hardest decision:** Whether to nest tag operations under `/api/notes/:id/tags` or have a flat `/api/note-tags` endpoint. Chose nested routes because they express the relationship naturally and match REST conventions. The trade-off is slightly more complex routing but clearer API semantics.
- **Rejected alternatives:** (1) GraphQL -- overkill for a simple CRUD app. (2) Sequelize/Knex ORM -- adds complexity; raw better-sqlite3 is simpler and synchronous. (3) MongoDB -- SQLite is the sandbox standard and relational data (tags, associations) fits naturally. (4) Flat tag-to-note endpoint -- less RESTful than nested resources.
- **Least confident:** Whether the swarm build pattern translates cleanly from Flask to Node/Express. The shared-spec-node.md template exists but has never been tested end-to-end. The app factory pattern (`createApp()`) and synchronous better-sqlite3 should make it work, but the first real swarm build on this stack may surface unexpected issues with module resolution, test isolation, or middleware ordering.

## Refinement Findings

**Gaps found:** 4 (all addressed in plan phase)

1. **Transaction wrapper pattern** -- Spec must show exact `db.transaction(() => { ... })()` usage, not just function signatures. Prior Flask swarm builds where context manager usage was unspecified caused all agents to misuse it identically. (from: flask-swarm-acid-test)

2. **Route prefix doubling** -- Express route handler paths must be RELATIVE to the router mount prefix. Use `router.get('/')` not `router.get('/api/notes/')` when mounted at `app.use('/api/notes', router)`. Same bug hit Flask finance tracker. (from: personal-finance-tracker-swarm-build)

3. **Test database isolation** -- `createApp()` must accept a `dbPath` or `db` argument so tests can inject `:memory:` or temp file. Without this, models agent and test agent will make incompatible assumptions. (from: flask-swarm-acid-test, task-tracker-categories-swarm)

4. **PRAGMA foreign_keys is per-connection** -- WAL is persistent, but `foreign_keys = ON` must be set on every connection. Without it, ON DELETE CASCADE on `note_tags` silently won't fire. (from: recipe-organizer-swarm-build)
