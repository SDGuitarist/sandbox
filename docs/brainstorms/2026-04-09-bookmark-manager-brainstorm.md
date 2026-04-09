---
title: "Bookmark Manager with Tags, Search, and User Preferences"
date: 2026-04-09
status: complete
type: brainstorm
---

# Bookmark Manager

## What We're Building

A personal web bookmark manager built with Flask + SQLite, following the sandbox's established app factory pattern. Users can save URLs with titles, descriptions, and free-form tags, then search across all fields and customize display preferences.

## Why This Approach

- **Web UI** -- consistent with task-tracker and other sandbox apps; proven Flask + Jinja2 pattern
- **Free-form tags** -- no predefined list; tags created on the fly via a many-to-many relationship (bookmarks <-> tags junction table)
- **LIKE-based search** -- searches title, URL, and tag names without extra dependencies (no FTS5 needed for personal-scale data)
- **Display + default preferences** -- items per page, default sort order, list/card view toggle, default tags for new bookmarks, auto-fetch page titles from URLs

## Key Decisions

1. **Single-user, no auth** -- personal tool, no login system
2. **Free-form tags with junction table** -- `bookmarks`, `tags`, `bookmark_tags` tables; tags are deduplicated by name
3. **LIKE search across title + URL + tags** -- simple SQL JOIN with WHERE LIKE clauses
4. **User preferences in a key-value table** -- `preferences(key TEXT PRIMARY KEY, value TEXT)`; avoids schema changes when adding new prefs
5. **Auto-fetch page titles** -- when saving a URL, attempt to fetch the page title via `urllib.request`; fall back to manual entry on failure
6. **WAL mode + atomic SQL** -- per solution doc lessons, enable WAL in init_db and use atomic updates

## Scope

### In Scope
- CRUD for bookmarks (URL, title, description, tags)
- Tag management (create-on-save, remove unused, browse by tag)
- Search bar filtering across title, URL, and tags
- Preferences page (items per page, sort order, view mode, default tags, auto-title toggle)
- Pagination

### Out of Scope
- Multi-user / authentication
- Import/export (browser bookmark files)
- Favicon fetching
- Bookmark folders or hierarchical organization
- Full-text search (FTS5)

## Data Model Sketch

- **bookmarks**: id, url, title, description, created_at, updated_at
- **tags**: id, name (UNIQUE)
- **bookmark_tags**: bookmark_id, tag_id (composite PK, foreign keys)
- **preferences**: key (PK), value

## Prior Art (from solution docs)

- WAL mode + timeout=10 for concurrent writes (url-shortener)
- Atomic SQL for counters, not read-modify-write (url-shortener)
- Deduplicate before count math; prefer computed over stored derived values (habit-tracker)
- Spec scalar return types explicitly if using swarm (task-tracker)
- Guard empty list before max() (todo-app)

## Open Questions

None -- all key decisions resolved during brainstorm dialogue.

## Feed-Forward

- **Hardest decision:** Whether to use FTS5 or LIKE-based search. Chose LIKE for simplicity since this is single-user, personal-scale data. FTS5 would be overkill.
- **Rejected alternatives:** Predefined categories (too rigid), CLI interface (inconsistent with sandbox patterns), tag-only filtering (too limited without free-text search).
- **Least confident:** Auto-fetch page titles via urllib -- could be slow or fail on many sites. Needs a timeout and graceful fallback. This should be verified early in the work phase.
