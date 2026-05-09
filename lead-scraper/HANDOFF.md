# Browser Outreach Sender -- Work Phase Handoff

**Phase:** Work (Phase 1 of 4)
**Date:** 2026-05-08
**Plan:** docs/plans/2026-05-08-feat-browser-outreach-sender-plan.md
**Brainstorm:** docs/brainstorms/2026-05-08-browser-outreach-sender-brainstorm.md

## Next Action

Implement Phase 1: Foundation (Days 1-2).

## Prompt for New Session

Read docs/plans/2026-05-08-feat-browser-outreach-sender-plan.md.

Implement Phase 1: Foundation (Days 1-2).

**Scope:**
1. Schema migration in db.py: _create_sender_accounts(), _migrate_needs_review_status(), restructure migrate_db() so sender migrations run independently
2. account.py (new module): CRUD + state machine for sender_accounts table
3. Account CLI in run.py: account add/list/login/confirm-risk/cooldown/disable/enable subcommands
4. Playwright setup: Add playwright>=1.40 to requirements.txt, add ~/.browser-profiles/ to .gitignore

**Critical rules:**
- NEVER run concurrent processes on leads.db (lost 1,093 leads TWICE previously)
- Back up before migration -- WAL-safe via sqlite3.backup()
- Pre-migration row count must equal post-migration row count (assert)
- Commit each file separately (~50-100 lines each). Do NOT start Phase 2 (browser_sender.py) this session.
- Follow existing patterns: _migrate_outreach_statuses() for table recreation, cmd_campaign() for CLI dispatch, get_db() context manager for DB access
- All state transitions use atomic UPDATE WHERE status=X + rowcount > 0 assertion

**Key files to read first:**
- docs/plans/2026-05-08-feat-browser-outreach-sender-plan.md (Phase 1 section, lines 98-333)
- db.py (migration patterns, get_db context manager, _migrate_outreach_statuses)
- run.py (CLI dispatch pattern, cmd_campaign subcommand structure, argparse subparsers)
- campaign.py (atomic update pattern with WHERE + rowcount check, approve_message example)

**Feed-Forward risk (from plan):**
"Meta publishes no safe DM thresholds. Restriction signals must be discovered during spike test. Playwright selectors are fragile against Meta UI changes."

This applies to Phase 2+. Phase 1 is schema/account setup and manual login only -- no automated sends yet.

**Done when:**
- db.py migrations complete with pre/post row count assertions
- account.py module has all 10 functions (add, list, get_active, increment_sends, mark_restricted, set_cooldown, check_cooldown_expired, disable, enable, confirm_risk)
- run.py account command group fully wired with help text
- requirements.txt updated
- .gitignore updated
- First schema migration runs without error
- Second migration run is idempotent (verified by print output)
- All atomic UPDATEs in account.py use rowcount > 0 check

## Solution Docs to Reference During Implementation

- **Schema migration chains** (gigprep): key-existence checks, pre/post row count assertions
- **Atomic claim** (gig-lead-responder): UPDATE WHERE status=X + rowcount > 0
- **DB Safety** (memory): NEVER concurrent on leads.db. Back up before every op.
- **Reliability hardening** (lead-scraper): inline retry, tier=-1 sentinel, never persist transient failures

## Phase Sequence

- [x] Brainstorm (2 Codex reviews, all blockers fixed)
- [x] Plan (3 Codex reviews, all blockers fixed)
- [ ] **Work Phase 1: Foundation** <-- YOU ARE HERE
- [ ] Work Phase 2: Minimal Sender + Spike Test
- [ ] Work Phase 3: Quality Gate
- [ ] Work Phase 4: Full CLI Integration + Ramp
- [ ] Review
- [ ] Compound

## Prior Handoff (Reliability Hardening -- 2026-05-06)

- Inline retry loop, circuit breakers, manual_approved column, 12 new tests
- 8-agent review: 1 P1 + 4 P2 fixed
- Solution doc: docs/solutions/2026-05-06-reliability-hardening.md
