# Brainstorm: Contact Book App

**Date:** 2026-04-09
**Status:** Complete
**Purpose:** Verification build -- testing zero permission prompts after compound bash instruction refactor

## What We're Building

A simple contact book app. Single user, Flask + SQLite + Jinja2. CRUD operations
on contacts (name, email, phone, optional notes) plus search by name.

## Why This Approach

Standard sandbox Flask app pattern. Simplest possible swarm build to verify
the bash instruction refactor works end-to-end with zero permission prompts.

## Key Decisions

1. **Flask + SQLite + Jinja2** -- sandbox standard stack
2. **No auth** -- single user, no login needed
3. **CSRF on all POST forms** -- lesson from prior builds
4. **SECRET_KEY from env** -- lesson from prior builds
5. **Search by name only** -- YAGNI, no full-text search

## Out of Scope

- Tags/groups, import/export, profile photos, pagination, auth

## Feed-Forward

- **Hardest decision:** None -- this is a well-understood pattern from 5 prior builds.
- **Rejected alternatives:** None -- standard approach, no design ambiguity.
- **Least confident:** Whether the refactored bash instructions will produce
  zero permission prompts during the swarm build. This IS the test.
