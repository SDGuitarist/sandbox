# BUILD_TRACKING.md

## Run Info

| Field | Value |
|-------|-------|
| Project | Client Music Planner |
| Spec | docs/plans/client-music-planner-plan.md |
| Date | 2026-05-19 |
| Phases | 6 (brainstorm, plan, spec-convergence, swarm-work, review, compound) |
| Total Agents | 20 |
| Build Method | autopilot-swarm |
| Run ID | 048 |
| Reports | docs/reports/048/ |
| Self-Audit | docs/reports/048/self-audit.md |

---

## AGENT_STATUS

### core-infra
- **Status:** COMPLETED
- **Files created:** 10 (app factory, db, models, decorators, filters, schema, config, run, requirements, gitignore)
- **Issues encountered:** none
- **Commit:** 687d1d3

### auth
- **Status:** COMPLETED
- **Files created:** 4
- **Issues encountered:** none
- **Commit:** a23b058

### layout-static
- **Status:** COMPLETED
- **Files created:** 4
- **Issues encountered:** none
- **Commit:** ccc9592

### repertoire
- **Status:** COMPLETED
- **Files created:** 5
- **Issues encountered:** none
- **Commit:** c4bcee0

### repertoire-import
- **Status:** COMPLETED (assembly fix required)
- **Files created:** 4
- **Issues encountered:** Exported wrong bp name, missing login_required, called nonexistent function, no db.commit()
- **Commit:** 9721c43

### events
- **Status:** COMPLETED
- **Files created:** 5
- **Issues encountered:** none
- **Commit:** b6e2734

### event-dashboard
- **Status:** COMPLETED
- **Files created:** 3
- **Issues encountered:** none
- **Commit:** a5e3b8f

### event-export
- **Status:** COMPLETED
- **Files created:** 3
- **Issues encountered:** none
- **Commit:** 4b101bb

### portal-browse
- **Status:** COMPLETED
- **Files created:** 4
- **Issues encountered:** none
- **Commit:** 70dc7ec

### portal-playlist
- **Status:** COMPLETED (assembly fix -- full rewrite)
- **Files created:** 3
- **Issues encountered:** 13 contract failures: hardcoded url_prefix, wrong column names, bypassed models, no commits, wrong template block, nonexistent blueprint refs
- **Commit:** 51ba9b6

### portal-flags
- **Status:** COMPLETED
- **Files created:** 2
- **Issues encountered:** none
- **Commit:** e1bc3f1

### portal-requests
- **Status:** COMPLETED
- **Files created:** 3
- **Issues encountered:** none
- **Commit:** 20fcc60

### portal-approve
- **Status:** COMPLETED
- **Files created:** 3
- **Issues encountered:** none
- **Commit:** f18cfc8

### portal-layout
- **Status:** COMPLETED
- **Files created:** 3
- **Issues encountered:** none
- **Commit:** 01462b4

### dashboard
- **Status:** COMPLETED
- **Files created:** 3
- **Issues encountered:** none
- **Commit:** 911eb42

### api-playlist
- **Status:** COMPLETED
- **Files created:** 2
- **Issues encountered:** none
- **Commit:** 7a98046

### api-filters
- **Status:** COMPLETED
- **Files created:** 2
- **Issues encountered:** none
- **Commit:** 566f1fc

### static-assets
- **Status:** COMPLETED
- **Files created:** 4
- **Issues encountered:** none
- **Commit:** f0b91ea

### tests
- **Status:** COMPLETED
- **Files created:** 7 (81 tests)
- **Issues encountered:** none
- **Commit:** 68a7b85

### seed-data
- **Status:** COMPLETED
- **Files created:** 1
- **Issues encountered:** none
- **Commit:** 624066c

---

## FAILURES

### Assembly Fix -- portal_playlist + repertoire_import
**Phase:** Assembly (post-merge)
**Severity:** P1
**Agents:** portal_playlist (13 failures), repertoire_import (5 failures)
**Error:** portal_playlist ignored spec: wrong column names, bypassed models, no commits, wrong template block. repertoire_import: wrong export name, missing auth, wrong function call.
**Root cause:** portal_playlist agent generated code from feature description rather than reading spec's Cross-Boundary Wiring code blocks.
**Resolution:** Single assembly-fix agent pass rewrote both modules per spec.
**Time to resolve:** ~3 min
**Failure class:** FC4 (validation gap), FC1 (naming divergence), FC29 (no transaction boundary)

### Review P1-1 -- Bare except Exception
**Phase:** Review
**Severity:** P1
**Agent:** portal_playlist (assembly fix)
**Error:** `except Exception` in add_to_playlist caught all errors, reported as "already in playlist"
**Resolution:** Changed to `except sqlite3.IntegrityError`
**Failure class:** FC4 variant

### Review P1-2 -- Raw exception flash
**Phase:** Review
**Severity:** P1
**Agent:** repertoire-import
**Error:** `flash(f"Import failed: {e}")` leaked internal error messages
**Resolution:** Changed to generic user message
**Failure class:** Info leak (no specific FC)

### Review P1-3 -- CSS class mismatch
**Phase:** Review
**Severity:** P1
**Agent:** portal-playlist (template) + static-assets (JS)
**Error:** Template `btn-move-up` vs JS `.move-up` -- move buttons permanently dead
**Resolution:** Changed template class to `move-up`/`move-down`
**Failure class:** FC31 (cross-flow data integrity)

### Review P1-4 -- Energy range inconsistency
**Phase:** Review
**Severity:** P1
**Agent:** repertoire-import
**Error:** Import validated energy 0-10 but schema CHECK is 1-5
**Resolution:** Changed import validation to 1-5
**Failure class:** FC4 (validation gap)

---

## RUN_METRICS

### Final Build Metrics

| Metric | Value |
|--------|-------|
| Total agents | 20 |
| Total files | 75 |
| Total lines | ~5,600 |
| Merge conflicts | 0 |
| Assembly fixes | 1 (23 contract failures in 2 agents) |
| Smoke test | 11/11 PASS |
| Test suite | 81/81 PASS |
| Total commits | 24 (20 agent + 1 assembly-fix + 1 assembly-merge + 1 P1-fix + 1 compound) |
| P1 findings (review) | 4 (all fixed) |
| P2 findings (review) | ~14 (deferred) |
| P3 findings (review) | ~16 (deferred) |
| All P1s fixed | yes |

### Agent Performance Summary

| Agent | Findings Caused | Failure Classes Hit | Notes |
|-------|----------------|--------------------|----|
| portal-playlist | 13 contract + 2 P1 | FC1, FC4, FC29, FC31 | Full rewrite needed. Ignored spec entirely. |
| repertoire-import | 5 contract + 2 P1 | FC4 | Wrong export name, missing auth, wrong function |
| static-assets | 1 P1 (shared) | FC31 | CSS class mismatch with portal-playlist template |
| All others (17) | 0 | none | Clean output |

### Lessons for Next Build

1. Portal/auth agent-type rules added to agent-pitfalls.md (catch sqlite3.IntegrityError, use g.portal_event)
2. Flow-trace reviewer is mandatory for any HTML+JS+Python feature
3. CSS class names between templates and JS must be prescribed in spec (not just behavior)
4. 5% assembly fix rate (1/20 agents) is acceptable; budget for it in planning

---

## Template Version

v1.0 — 2026-05-03 (created after WRC Build #7)
