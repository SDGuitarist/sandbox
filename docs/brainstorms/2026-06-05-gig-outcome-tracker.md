# Brainstorm: Gig Outcome Tracker

**Date:** 2026-06-05
**Mode:** Autopilot (simplest-option discipline) — driven by
`docs/briefs/2026-06-05-gig-outcome-tracker-autopilot-brief.md` (complete spec)
**Build method:** autopilot-swarm, 12 agents, Flask + SQLite + Jinja2

## Problem

After every gig, Alex records voice notes about the performance. PF-Intel
captures venue/contact intelligence, but nothing captures the *performance
story*: which songs worked, how the audience responded, what contacts were
made, what was learned. The Gig Outcome Tracker fills that gap — a searchable
intelligence database of gig outcomes built over time.

## Why This Build Matters (Meta-Goal)

This is the **first real swarm build validating the 3-stage context-death
delegation architecture** (no-read discipline + deepen-merge-runner +
swarm-runner). Success = fully unattended completion with
`final_status: DONE` and `manual_resume: false` in BUILD_TRACKING.md. The app
is real and useful, but the architecture validation is the primary objective.

## Chosen Approach (simplest option at every fork)

- **Single-user app, session-only auth.** No `user_id` columns on domain
  tables. Auth provides session security only. (Brief is explicit; adding
  multi-user scoping is YAGNI for this build.)
- **Flask + SQLite + Jinja2**, the sandbox standard. Model/route vertical
  split across 12 agents (6 model agents, 5 route-blueprint agents, 1
  scaffold, 1 dashboard).
- **Money in cents** (integer ≥ 0), two-column pattern (amount + payment
  status) with paired CHECK — matches PF-Intel mesh convention.
- **8-char UUID hex IDs**, ISO-8601 dates, `datetime('now')` timestamps —
  mesh-compatible with GigPrep/PF-Intel.
- **No AI parsing** of debriefs — plain text storage + case-insensitive
  `LIKE` keyword search (no FTS5, sidesteps FC36 operator injection).
- **No soft deletes.** FK `ON DELETE RESTRICT`/`SET NULL` per the brief's
  table; delete rules enforced at route level where status matters.

## Rejected Alternatives

- **FTS5 search** — rejected. `LIKE` is sufficient for single-user scale and
  avoids FTS5 MATCH operator-injection (FC36) and tokenizer complexity.
- **Multi-user / user_id scoping now** — rejected. YAGNI; deferred to future
  mesh phase. Adding it now would require compound unique constraints
  everywhere for zero current benefit.
- **AI debrief parsing into structured fields** — rejected. PF-Intel owns
  voice→structure; this build only stores and searches text.
- **Solo build** — rejected. The explicit purpose is to validate the swarm
  delegation architecture at 12-agent scale.

## Lessons Applied from Prior Builds

- **CSRF `{{ csrf_token() }}` (with parens)** in Coordinated Behaviors (FC1
  variant, CoWorkFlow run 055).
- **SECRET_KEY fail-closed** — `raise RuntimeError` if env var missing; never
  a dev fallback (FC10, Client Intake run 058).
- **Transaction contracts prescribe the error-handling wrapper** —
  try/except/ROLLBACK alongside any BEGIN IMMEDIATE (FC29 variant, GymFlow
  run 054). Most CRUD here is single-statement and can use `with conn:`.
- **`datetime('now')` in SQL, never Python `datetime.now()`** (GymFlow).
- **PRAGMA per-connection** — every `sqlite3.connect()` sets the same PRAGMAs
  (`foreign_keys=ON`, etc.) (FC40, GigSheet).
- **Negative constraints** — "DO NOT set row_factory in models" type rules to
  prevent divergence (GymFlow).
- **Smoke tests use a temp file, never `:memory:`** (FC49, Film PM run 063);
  app factory maps `os.environ['DATABASE']` → `app.config['DATABASE']`.
- **Ghost-file cleanup before swarm launch** (FC48). Step 9w.9 gate.
- **Flow-trace review** for cross-file key mismatches (schema↔model↔template).
- **Phantom FK guard** (FC46) — every `*_id` column has `REFERENCES`. Brief's
  schema already does this.

## In Scope / Out of Scope

In scope: auth, venues, gigs, outcomes (1:1), contacts + follow-ups, debriefs
(1:1) + search, dashboard. Out of scope: voice/Whisper, AI parsing, mesh
integration, set-list songs, real-time, export/API, multi-user.

## Feed-Forward

- **Hardest decision:** Whether to run this as a swarm at all given the brief
  is already a near-complete plan. Chose swarm because the *point* is to
  validate the delegation architecture under realistic 12-agent coordination
  load, not just to ship a CRUD app. The risk this trades into: orchestrator
  context survival through inline deepen + 12-agent spawn.
- **Rejected alternatives:** FTS5 search, multi-user scoping now, AI debrief
  parsing, solo build (all rejected above for YAGNI / scope / purpose).
- **Least confident:** Dashboard aggregation query correctness. No prior
  solution doc covers dashboard-specific GROUP BY / COALESCE / paid-only
  revenue logic. The brief's deterministic fixture (3 played, $880 revenue,
  4.5 avg energy, 8000 tips) is the verification anchor — the smoke test must
  seed it and assert the rendered totals.

## Refinement Findings (brainstorm-refinement agent, STATUS: PASS)

Four gaps surfaced from prior solution docs — all fold into the plan's
Coordinated Behaviors and Input Validation sections:

1. **SESSION_COOKIE_SECURE must be env-gated** (Film PM run 063) —
   `SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'`.
   Unconditional `True` breaks local HTTP dev sessions.
2. **`with conn:` is the only reliable transactional write pattern**
   (Prompting Dashboard run 064) — in Python 3.14+, explicit
   `BEGIN`/`commit` with `autocommit=True` silently drops data. Mandate
   `with conn:` for ALL transactional writes, not as one option among several.
3. **Jinja2 custom filters returning `Markup()` need `markupsafe.escape()`**
   (Client Intake run 058, FC47) — status badges / rating labels / debrief
   excerpts are XSS surfaces. Negative constraint: "DO NOT use Markup() in
   filters without escaping inputs first."
4. **Date validation `re.match(r'^\d{4}-\d{2}-\d{2}$', value)` on every
   date-accepting route** (Film PM run 063, FC4/FC27) — gig date, follow-up
   date. Enumerate each in Input Validation Prescriptions, not just note the
   convention.
