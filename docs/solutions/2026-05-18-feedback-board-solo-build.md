---
title: "Feedback Board Solo Build"
category: flask-sqlite-builds
tags: [flask, sqlite, jinja2, csrf, upvote-dedup, admin-auth, csv-export, solo-autopilot]
module: feedback-board
date: 2026-05-18
run_id: "045"
build_method: autopilot-solo
---

# Feedback Board Solo Build

## What Was Built

A lightweight feedback/suggestion board: Flask + SQLite + Jinja2, no external APIs. Anonymous users submit ideas and upvote. Single admin manages via basic-auth dashboard with status tracking, filtering, and CSV export.

**Run ID:** 045 (solo autopilot)
**Files:** 16 created, 4 modified during review
**Commits:** 7 (4 feature + 1 chore + 1 docs + 1 review fixes)

## Key Technical Decisions

1. **Jinja2 over separate Express frontend** -- eliminates cross-stack failure classes (FC28, FC30) entirely. Single stack = fewer integration seams.

2. **Atomic upvote dedup** -- `INSERT OR IGNORE` on UNIQUE(feedback_id, ip_address) + `cursor.rowcount == 0` check + SQL `vote_count = vote_count + 1` increment. Confirmed via empirical testing during plan deepening that `rowcount` returns 0 for ignored rows.

3. **`before_request` hook for admin auth** -- cleaner than per-route `require_admin()` calls. CSRF validation fires first (Flask-WTF registers at app-level, which runs before blueprint-level hooks). Documented the ordering dependency in a code comment.

4. **Fail-closed startup checks** -- SECRET_KEY crashes if missing in production. ADMIN_PASSWORD rejects known weak values. Both prevent silent misconfiguration.

## What the Review Found

| Agent | P1 | P2 | P3 | Key Findings |
|-------|----|----|-----|-------------|
| security-sentinel | 0 | 2 | 4 | CSRF/auth hook ordering fragility; "change-me" false positive (already in blocklist) |
| kieran-python-reviewer | 2 | 3 | 3 | init_db FD leak; bare dict/list types; duplicated query building |
| learnings-researcher | 0 | 0 | 0 | Zero violations of prior solution doc patterns |

**Total: 2 P1, 5 P2, 7 P3.** All P1s and P2s fixed. P3s deferred (CSP header, HSTS, deferred import).

## Lessons Learned

1. **`init_db` needs the same connection discipline as `get_db`** -- wrapping in try/finally prevents FD leaks on startup schema errors. This is easy to miss because init_db runs once and "always works."

2. **Security reviewers can produce false positives on blocklists** -- the security agent claimed "change-me" wasn't in the weak password blocklist, but it was. Always verify findings against actual code before fixing.

3. **INSERT OR IGNORE + rowcount is safe in SQLite** -- empirically confirmed during plan deepening. `cursor.rowcount` returns 0 when the row is ignored. This resolves the Feed-Forward risk from brainstorm.

4. **`FLASK_ENV` is dead code in Flask 3.0+** -- deprecated since 2.3. Use `app.debug` (set via `FLASK_DEBUG=1`) instead.

5. **before_request hook ordering between app and blueprint levels** is safe but undocumented by Flask. App-level hooks (where Flask-WTF registers CSRF) fire before blueprint-level hooks (where admin auth lives). Document this dependency with a comment.

## Risk Resolution

| Risk (from Feed-Forward) | What Happened | What Was Learned |
|--------------------------|---------------|------------------|
| vote_count desync under concurrent upvotes | Not tested under concurrent load, but BEGIN IMMEDIATE + SQL atomic increment is the established pattern. rowcount confirmed correct. | The risk was lower than feared -- SQLite's write serialization + the atomic pattern make this robust at workshop scale. |
| before_request auth/CSRF ordering | Confirmed safe: app-level hooks run before blueprint-level. | Fragile by design -- document the dependency, don't rely on it silently. |

## Patterns Worth Reusing

- **IP-based upvote dedup pattern:** INSERT OR IGNORE + rowcount check + atomic SQL increment. Portable to any voting/like system.
- **Flask startup validation pattern:** Crash on missing SECRET_KEY, reject weak ADMIN_PASSWORD. Prevents silent misconfiguration.
- **CSV formula injection sanitizer:** Strip null bytes, check leading characters after whitespace stripping. Prefix dangerous chars with `'`.
- **Brute-force dict with eviction cap:** defaultdict(list) with sliding window + MAX_TRACKED_IPS to prevent memory leak.

## Feed-Forward

- **Hardest decision:** Whether the CSRF/auth hook ordering was a P1 (requires code fix) or P2 (requires documentation). Chose P2 -- it's safe today and breaking it requires a code change.
- **Rejected alternatives:** Moving auth to app-level (would break other blueprints), manual CSRF check in admin routes (over-engineering), redis for brute-force tracking (overkill at scale).
- **Least confident:** Whether the brute-force eviction strategy (evict IP with oldest last attempt) is optimal under a distributed attack. The 10K cap prevents memory exhaustion, but an attacker could theoretically evict a legitimate lockout entry by flooding with unique IPs.
