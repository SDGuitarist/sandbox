---
title: "Run 080 Review Summary"
run_id: "080"
date: 2026-07-04
project: ShelfTrack (Flask + SQLite reading-list; G1+G3 coexistence validation vehicle)
review_target: shelftrack/ (multi-user reading list; source no longer on disk — see Provenance)
provenance: reconstructed-from-record
verdict: 0 P1, 2 P2 (both deferred per plan)
---

# Review Summary — ShelfTrack (Run 080)

> ## ⚠️ Provenance — READ FIRST (this artifact resolves [080-W2])
>
> **This is a RECONSTRUCTION, not a freshly-run review.** It was authored
> **2026-07-04** to close deferred item **[080-W2, HIGH]** — the run-080 review was
> conducted as **inline parallel agent calls within the tail-runner context window
> and never persisted to disk**, so the "0 P1, 2 P2" verdict and "IDOR flow-trace
> confirmed" assertion in BUILD_TRACKING and the solution doc had no backing
> artifact. This file consolidates the review evidence that **does** exist on disk
> into the canonical `review-summary.md` location and format.
>
> **What this artifact IS:** a faithful transcription of the recorded review
> findings, reviewer roster, scope, and P0/P1/P2 counts, drawn from
> `docs/reports/080/self-audit.md`, `docs/reports/080/disconfirmer.md`,
> `docs/reports/080/contract-check.md`, and the run-080 solution doc.
>
> **What this artifact is NOT:** a fresh, independent re-review. The ShelfTrack
> **source code no longer exists on disk** — it lived on the throwaway branch
> `feat/shelftrack-reading-list`, deleted in Step 4 of the run-080 teardown (only a
> stale `shelftrack/__pycache__/` remains on master). The findings below therefore
> **cannot be re-derived from source**; they are reproduced from the durable record.
>
> **Honesty caveat carried from the self-audit (080-W4, HIGH):** the original review
> was **static-only**. The dynamic IDOR-404 acceptance test (`test_smoke.py`) was
> `FIREBREAK_DEFERRED` during the governed tail and did not run *during* the review.
> Dynamic coverage was obtained **later**, post-teardown: `test_smoke.py` re-ran
> **16/16 PASS** including the IDOR-404 ownership check — evidence in
> `docs/reports/080/smoke-rerun-postteardown.md` ([SMOKE-080] CLOSED).

## Review Agents Used (2 — inline, tail-runner context)

Per the self-audit 080-W2 disposition, the run-080 review was conducted as two
parallel inline agent calls (not the full multi-agent review roster used on
production builds like Run 061's 7 agents). This lighter roster was a deliberate
consequence of ShelfTrack being a throwaway governance-validation vehicle with a
highly prescriptive spec and ownership-baked SQL — but the thin roster is itself
part of why [080-W2] was raised.

1. **Security flow-trace agent** — traced the IDOR / ownership-scoping data path
   across all 5 book routes; CSRF token coverage; session handling; SECRET_KEY
   behavior.
2. **Learnings researcher** — cross-referenced prior solution-doc lessons
   (IDOR canonical cases: `2026-05-20-venueconnect-25-agent-swarm-build.md`;
   `2026-05-21-spec-completeness-checker-pre-swarm-gate.md`).

## Feed-Forward Risk Resolution

**Risk (plan Feed-Forward, `verify_first`):** "A book route queries by `id` alone
(not `id AND user_id`) → silent IDOR. Ownership must be enforced IN the SQL WHERE of
every book route."

**Resolution:** DENIED across all 5 book routes. Ownership was baked into the SQL
WHERE of every book DML statement (`AND user_id = ?`), with `session['user_id']`
sourced from the authenticated session — never from a URL param or form field. The
`fetch-by-id → check-owner-in-Python` pattern (TOCTOU-prone, forgettable) was
rejected at plan time. Confirmed statically by both the flow-trace review and the
contract check (FC35). See the flow-trace table below. **Residual:** confirmation
was static at review time; dynamic confirmation came from the post-teardown smoke
re-run (16/16, including user-B → 404 on user-A's book).

## Findings Summary

- **Total Findings:** 2
- **P0 (Blocker):** 0
- **P1 (Critical):** 0
- **P2 (Important):** 2 — both DEFERRED per the plan's Deferred Hardening section
  (throwaway validation build; not a production deployment)
- **P3 (Nice-to-Have):** 0 recorded

### P1 — Critical (0)

None. No P1 review findings. (Note: this is the "0 P1" claim that [080-W2] flagged
as unbacked; it is now backed by this consolidation of the self-audit + contract
check + flow-trace record.)

### P2 — Important (2, both deferred)

| ID | Finding | Self-Audit Key | Re-entry Point | Disposition |
|----|---------|----------------|----------------|-------------|
| P2-1 | `SESSION_COOKIE_SECURE` conditioned on the `FLASK_ENV` string (fragile — string-compare gates a security flag) | 080-W6 | Set unconditionally / derive from a robust config, not a string match | DEFERRED per plan (no production path) |
| P2-2 | Password minimum is 6 characters (NIST SP 800-63B recommends 8+) | 080-W7 | WTForms `Length(min=8)` on the registration form | DEFERRED per plan (throwaway build) |

## IDOR Flow-Trace (the primary security check — all 5 routes PASS)

Source: solution doc "Review (flow-trace)" table + `contract-check.md` FC35
(both static, on assembled code).

| Route | books.py call | SQL WHERE clause | IDOR verdict |
|-------|---------------|-----------------|--------------|
| GET /books | `get_books_for_user(db, session['user_id'], status)` | `WHERE user_id = ?` | PASS |
| POST /books | `create_book(db, session['user_id'], ...)` | INSERT with user_id | PASS |
| GET /books/<id>/edit | `get_book_for_user(db, book_id, session['user_id'])` | `WHERE id=? AND user_id=?` | PASS |
| POST /books/<id>/edit | `update_book(db, book_id, session['user_id'], ...)` | `WHERE id=? AND user_id=?` | PASS |
| POST /books/<id>/delete | `delete_book(db, book_id, session['user_id'])` | `WHERE id=? AND user_id=?` | PASS |

No route queries by `id` alone. Ownership failures return `abort(404)` (never 403 —
avoids leaking resource existence). **IDOR risk: FULLY MITIGATED (static).**

## Static Contract-Check Coverage (14/14 invariants PASS)

The review's static assurance was backed by `contract-check.md` (STATUS: PASS,
14/14), which grepped the assembled code for:

- **FC35 IDOR ownership scoping** — all 5 book DB calls include `user_id` (above)
- **CSRF tokens** — `{{ csrf_token() }}` on all 5 POST forms incl. `base.html` logout
- **`session.clear()`** on both login (before setting keys) and logout
- **SECRET_KEY fail-closed** — `__init__.py` raises `RuntimeError` if absent (no dev fallback)
- **Blueprint names / registration**, **cross-boundary import paths**, **authorization
  matrix** (all 6 book routes `@login_required`), **route-method disjointness**,
  **password hashing**, **`autocommit=True`**, **StrictUndefined** — all PASS
- **Flash categories** — 1 issue found + FIXED inline (8 error `flash()` calls missing
  the `'error'` category → CSS class break); fixed on first retry, commit `7f08f0e`

## Method & Limitations

- **Method:** static analysis only (flow-trace + contract-check grep) at review time.
- **Not covered at review time:** boot-time failures (init_db wiring, blueprint
  registration at runtime, SECRET_KEY env behavior), and the dynamic IDOR-404
  acceptance criterion — all `FIREBREAK_DEFERRED` during the governed tail.
- **Closed later:** post-teardown smoke re-run, **16/16 PASS**, incl. IDOR-404
  (`docs/reports/080/smoke-rerun-postteardown.md`). One test-harness bug found+fixed
  there (missing `os.unlink` → init guard skipped); app code was correct.
- **Roster gap:** 2 inline agents vs. a full 5–7 agent review roster. For a
  throwaway vehicle this was tolerable; for future governance-validation runs the
  review should use the standard roster AND produce this artifact **during** the run.

## Sources (durable record this reconstruction draws from)

- `docs/reports/080/self-audit.md` — 080-W2/W4 dispositions, skeptical Q&A (Q3 IDOR), roster
- `docs/reports/080/disconfirmer.md` — D2 (missing review artifact), D4 (zero dynamic tests)
- `docs/reports/080/contract-check.md` — FC35 + 13 other invariants, STATUS: PASS
- `docs/reports/080/smoke-rerun-postteardown.md` — post-teardown dynamic coverage (16/16)
- `docs/solutions/2026-06-30-shelftrack-run-080-g1-g3-coexistence-revalidation.md` — flow-trace table, P2 items
