---
title: Prompting Dashboard Engine (Run 064)
date: 2026-06-02
status: complete
type: brainstorm
---

# Prompting Dashboard Engine (Run 064) — Brainstorm

## What We're Building

A Flask + SQLite + Jinja2 + Bootstrap 5 web app for Amplify AI that turns Alex's 12-component expert-led prompting method into a guided dashboard. Three access modes: anonymous shared-template visitors, authenticated workshop users, and one admin (Alex).

**Core workflow:** Select industry -> choose template or blank wizard -> fill 12 components in order -> see live completeness -> generate clean copy-ready prompt -> save/export/share -> later grade the outcome.

**Target user:** Non-technical creative professionals attending Alex's workshops. Calm, plain-English UX. NOT a chatbot, NOT an LLM tool, NOT a marketplace. Creates, stores, formats, shares, and grades prompts only.

**This is NOT the same app as Run 061.** Run 061 was a single-user prompt testing workbench with Claude API integration. Run 064 is a multi-user guided prompting methodology dashboard with encryption, sharing, grading, and admin. Different app, different architecture, different tables.

## Why This Approach

### Architecture: Blueprint-based modular Flask (10 blueprints)

Ten modules map to 10 blueprints: auth, wizard, components, templates, library, grading, sharing, admin, search, export. Each blueprint owns its routes and model functions. Proven pattern from 20+ prior sandbox builds.

**Why 10 blueprints, not fewer?** The spec requires strict IDOR prevention across prompts, components, grades, exports, templates, and share tokens. Each resource type needs its own ownership checks. Smaller blueprints = clearer ownership boundaries = fewer FC35 (IDOR) bugs.

### Database: 12 tables with Fernet encryption

Required tables: users, industries, component_definitions, industry_guidance, prompt_templates, template_components, prompts, prompt_components, prompt_grades, share_tokens, audit_events, saved_exports.

**Fernet encryption:** Prompt content and component answers encrypted at rest using `PROMPT_ENCRYPTION_KEY` from environment. Encrypt on write, decrypt on read. This means encrypted fields cannot be searched with SQL LIKE — FTS5 must index plaintext, but the actual stored content is encrypted.

**Why Fernet, not application-level AES?** Fernet is authenticated encryption (HMAC + AES-CBC). It prevents both reading and tampering. Python's `cryptography` library provides it. Single key from environment, deterministic test key in tests.

### The 12 Components (4 Clusters)

Exactly as specified:
1. **Your Reality:** Role, Background, Client Context
2. **Your Assignment:** Task, Goal, Audience
3. **Your Voice:** Key Complexity, Tone, Avoid
4. **Your Contract:** Definition of Done, Format, Process

Components are stored in `component_definitions` with cluster assignment. No component is mandatory. Completeness = `filled_components / 12` where filled = trimmed text length > 0.

### Three Access Modes

1. **Anonymous:** Can open shared template URLs via token, fill wizard, generate/copy/export. Must log in to save.
2. **Authenticated:** CRUD own prompts only. Save, resume, edit, generate, export, grade.
3. **Admin (Alex):** Create templates, define industry guidance, view all prompts, review grades, revoke tokens, export library.

### Share Token Design

- Random token generated (32+ bytes)
- Token HASHED in database (SHA-256) — raw token only shown once
- Scoped to one template
- Read-only access (can fill wizard, generate, export — cannot save)
- Revocable by admin
- Anonymous visitors use the token URL without login

### Completeness Tracking

- **Client-side:** JavaScript counts filled textareas in real time, updates progress bar per cluster and overall percentage
- **Server-side:** On save, recount from stored component answers. Must match client-side value.
- **Weakest cluster:** UI highlights which of the 4 clusters has the lowest fill rate

### Outcome Grading

- 1-5 score
- `worked_well` (text)
- `needs_improvement` (text)
- `notes` (text)
- Linked to prompt via FK

## Key Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Architecture | 10 blueprints | Clean IDOR boundaries per resource type |
| 2 | Encryption | Fernet from `cryptography` | Authenticated encryption, Python native |
| 3 | Auth | Flask sessions + bcrypt | Simple, no OAuth needed for workshops |
| 4 | Share tokens | SHA-256 hashed in DB | Token shown once, revocable, not reversible |
| 5 | Completeness | Client JS + server recount | Real-time UX + integrity on save |
| 6 | Search | SQLite FTS5 on decrypted fields | Index plaintext, store encrypted |
| 7 | CSRF | flask-wtf CSRFProtect | All POST/PUT/DELETE forms (FC1) |
| 8 | UI | Bootstrap 5 (CDN) | Calm, professional look for creative users |
| 9 | Wizard state | Session or form hidden fields | Anonymous users have no DB record until save |
| 10 | Industry guidance | Admin-editable per component per industry | Rich text tips shown alongside wizard fields |

## Resolved Questions

1. **How does anonymous wizard state work?** → Wizard form posts all 12 component answers on submit. No server-side session needed for anonymous users. The wizard is a single long form with sections, not a multi-page wizard with server state. "Skip" means leaving a textarea empty.

2. **Template vs prompt data separation?** → Templates (`prompt_templates` + `template_components`) define starter content. When a user starts from a template, components are COPIED to `prompt_components`. After that, the prompt is independent of the template. Template changes don't affect existing prompts.

3. **Encrypted-field filtering?** → Cannot filter encrypted content with SQL. Admin filtering works on non-encrypted metadata (industry, user, date, completeness score). Search uses FTS5 which indexes plaintext at insert/update time.

4. **Partial saves?** → Every save writes all 12 component answers (empty string for unfilled). No partial saves — always a complete snapshot. Completeness recalculated on every save.

5. **Share-token lifecycle?** → Admin creates template -> optionally generates share token -> token URL is shared -> anonymous user fills wizard from template -> user can export/copy immediately -> must log in to save -> admin can revoke token (deletes hash from DB, URL stops working).

6. **Markdown seed import?** → Seed data loaded via Python seed script, not markdown. 12 component definitions, 4 clusters, 4+ industries, admin user, normal user, 1 template, 5 graded prompts.

7. **Generic error handling?** → Flask errorhandlers for 400, 403, 404, 500. All return HTML pages. No JSON error responses (this is a Jinja2 app, not an API).

## Scope Boundaries

**In scope (MVP — this build):**
- 12-component wizard with 4 clusters
- Live completeness tracking (client + server)
- Prompt generation (formatted text output)
- User library with search and filtering
- Outcome grading (1-5 + text fields)
- Share tokens (generate, use, revoke)
- Admin: templates, guidance, all-prompts, export
- Fernet encryption at rest
- CSRF, IDOR prevention, escaped output
- Seed data (12 components, 4 industries, users, template, graded prompts)

**Out of scope (Phase 2+):**
- LLM/AI API integration (this is NOT an AI tool)
- Prompt marketplace
- Model selector
- Real-time collaboration
- Prompt versioning/history
- OAuth / social login
- Email notifications
- File attachments

## Technical Constraints (from prior solution docs)

- **SECRET_KEY** from environment — no dev fallback (FC10)
- **PROMPT_ENCRYPTION_KEY** from environment — Fernet key
- **CSRF** on all POST forms — `{{ csrf_token() }}` with parentheses (FC1)
- **FTS5 sanitization** — strip operators before MATCH (FC36)
- **PRAGMA WAL + busy_timeout + foreign_keys** on every connection (FC40)
- **get_db() with context manager** — `with get_db() as conn:` usage pattern (FC2)
- **FK REFERENCES with ON DELETE** on every FK column (FC46)
- **No `|safe` or `Markup()` with user content** — autoescaping only (FC47)
- **No `isolation_level=None`** — use autocommit=True parameter (FC29 recurrence)
- **No global SQLite connection** — per-request via flask.g
- **No `row_factory` on shared connection** — set on the connection object returned by get_db
- **init_db() uses raw sqlite3.connect()** — not get_db() (executescript implicit commit)
- **SESSION_COOKIE_SECURE conditional** on environment (FC scaffold/auth)
- **IDOR: role + ownership** — check both on every detail/edit/delete route (FC35)
- **Do not log** raw prompt content, component answers, share tokens, passwords, or encryption keys
- **Smoke tests use tempfile** — not `:memory:` (FC49)
- **One command per Bash call** — no chaining (FC8)

## Lessons Applied from Prior Builds

1. **CSRF with parentheses** (`{{ csrf_token() }}`) in ALL templates — from CoWorkFlow FC1 variant
2. **Context manager usage examples** in spec — from Flask Acid Test FC2 (all 3 agents missed `with`)
3. **Template Render Context** section (~150 lines) — from Flask Acid Test (Python specs 3x larger)
4. **Endpoint registry table** — from Solopreneur Command Center (50+ routes need naming discipline)
5. **IDOR ownership checks** on every detail route — from VenueConnect FC35 (5 of 8 P1s)
6. **Form parsing deduplication** — from Prompting Dashboard Run 061 FC17 (18 identical lines)
7. **FTS5 BEFORE triggers** (not AFTER) — from Run 061 (corrupted index)
8. **Transaction contracts** per model function — from Workshop Registration Hub FC29
9. **Ghost file cleanup** pre-swarm — from Film PM Run 063 FC48 (42 ghost files)
10. **Prescriptive code blocks** for app factory — from Flask Acid Test (eliminates mismatches)
11. **WTForms field names** in spec for test agents — from Invoice & CRM FC9
12. **Fernet encryption** is new territory — no prior solution doc. Must be thorough in spec.

## Feed-Forward

- **Hardest decision:** How to handle search on encrypted content. FTS5 requires plaintext for indexing, but content is Fernet-encrypted at rest. Decision: FTS5 indexes plaintext at insert/update time (triggers), actual content column stores ciphertext. This means the FTS5 index IS effectively a plaintext cache — acceptable for a workshop tool, but worth noting.
- **Rejected alternatives:** (1) Encrypt everything including FTS5 — makes search impossible. (2) Skip encryption — violates spec requirement. (3) Use application-level search without FTS5 — too slow for large libraries, and we have the FC36 pattern ready.
- **Least confident:** The Fernet encryption/decryption integration with the wizard form flow. Every read decrypts, every write encrypts. If the encryption key is wrong or missing, all saved prompts become unreadable. Need fail-closed behavior: if `PROMPT_ENCRYPTION_KEY` is missing, app should refuse to start (like SECRET_KEY).
