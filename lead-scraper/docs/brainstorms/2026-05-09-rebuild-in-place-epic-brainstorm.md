---
title: "Rebuild Lead Scraper In Place Without Stopping Feature Delivery"
type: brainstorm
status: active
date: 2026-05-09
origin: CODEX-HANDOFF-DB-SAFETY.md + Codex DB safety stabilization session
---

# Brainstorm: Rebuild Lead Scraper In Place Without Stopping Feature Delivery

## Why This Exists

The lead-scraper production database has been wiped at least 3 times across different sessions. Each incident lost real leads that cost money (Apify credits) to re-scrape. The most recent incident (May 8-9, 2026) lost 1,690 leads during migration work for the browser outreach sender feature. A workshop on May 30 requires 3,000+ leads in pipeline.

Patching after each incident has not prevented the next one. The architecture itself permits data destruction through normal code paths. A structural rebuild is required -- but a big-bang rewrite would halt feature delivery during the most time-sensitive period (22 days to workshop).

## Current Problem

The root architectural flaw: **production data is treated as a default file**, not as a protected asset.

Specific failure modes that enabled data loss:
1. `init_db()` ran on every CLI invocation, executing the full migration chain each time
2. Destructive migrations (DROP TABLE + RENAME) could fire from ordinary startup
3. `executescript()` has implicit COMMITs -- mid-script failure leaves partial state
4. No separation between "bootstrap a new DB" and "migrate an existing DB with data"
5. Test verification ran against production DB by default (no explicit test isolation)
6. No global DB job lock prevented concurrent access

## Decision

Do **not** do a big-bang rewrite.
Do **not** keep patching forever.

Use a **multi-phase rebuild-in-place epic**, where each phase gets its own full compound engineering cycle:

`Brainstorm -> Plan -> Plan Review -> Work -> Review -> Compound`

Each phase ships independently. Feature delivery continues between phases as long as new features plug into approved safe boundaries.

## Rebuild Principle

**Production data is a protected asset, not a default file.**

Every operation that touches `leads.db` must:
- Prove it cannot destroy data before it runs
- Require explicit human authorization for destructive operations
- Be blocked by default if safety cannot be proven

## Phase Sequence

### Phase 0 -- Architecture Freeze / Safety Doctrine

Establish the rules that all subsequent phases must follow. Define what "safe" means. Lock the current working state as the baseline. No code changes -- pure documentation and policy.

Deliverables:
- Safety doctrine document (what is and isn't allowed)
- Inventory of all DB-touching code paths
- Classification of each path as safe / unsafe / needs-rebuild
- Decision log for which patterns to keep vs replace

### Phase 1 -- Environment and DB Boundary

Separate production DB access from development/test DB access at the infrastructure level. Make it physically impossible for test code to touch production data.

Deliverables:
- Hard boundary between production and test DB paths
- Environment-aware DB path resolution
- Tests that verify the boundary holds
- Migration of all tests to explicit tmp_path usage

### Phase 2 -- Migration Rebuild

Replace the current migration system (which runs on every startup and uses DROP TABLE) with an explicit, versioned migration system that only runs when invoked directly.

Deliverables:
- Migration runner as a separate explicit command
- Version tracking (which migrations have run)
- Non-destructive migrations by default (ALTER TABLE only)
- Destructive migrations require explicit flag + pre-migration data verification
- Rollback capability or at minimum verified backup before any destructive operation

### Phase 3 -- Config and Targeting Rebuild

Externalize all scraper targeting configuration so that expanding lead sources never requires code changes or DB operations.

Deliverables:
- All scraper targets in external config (already partially done via sources.overrides.json)
- Validation layer for config mutations
- No Python source edits needed for target additions
- Source-list caps enforced at config layer

### Phase 4 -- Natural Language Planner / Executor Split

Separate intent recognition from execution so that NL commands cannot trigger unsafe operations.

Deliverables:
- Planner: translates NL to a structured action plan (read-only)
- Executor: runs only allowlisted actions from the plan
- Preview mode: show what would happen without doing it
- Audit log for all NL-triggered actions

### Phase 5 -- Workflow and Operations Unification

Unify the various CLI commands, workflow commands, and NL paths into a single coherent operations layer with consistent safety guarantees.

Deliverables:
- Single entry point for all operations
- Consistent locking, backup, and verification across all paths
- Daily operational playbook that cannot accidentally destroy data
- Monitoring: alert if DB size drops unexpectedly

## What Must Not Change During The Rebuild

- Production leads.db data (1,211 leads currently, target 3,000+)
- Existing campaign workflow (create -> assign -> generate -> gate -> send)
- Scraper functionality (Eventbrite, Facebook, Instagram, LinkedIn, Meetup)
- Enrichment pipeline (bio, website, crawl, hunter, segment, hook, verify, screen)
- Template system and opener generation
- Flask web UI (read-only)

## Allowed Feature Work During The Epic

Feature work IS allowed between rebuild phases, but only if it:
1. Does not add new DB migration code
2. Does not modify `init_db()` or `migrate_db()`
3. Plugs into existing approved safe boundaries (e.g., new CLI commands that only READ data)
4. Uses the `get_db()` context manager without `allow_create=True`
5. Has tests that run against tmp_path databases only

Examples of allowed work:
- Running scrapers to rebuild lead count (uses existing safe paths)
- Quality gate improvements (reads DB, writes through campaign.py)
- Browser sender selector updates (reads DB, writes through campaign.py)
- New enrichment steps (uses existing enrich.py patterns)
- Report/export commands (read-only)

## Forbidden Feature Work During The Epic

- Any new DROP TABLE operation
- Any modification to schema files without a rebuild phase plan
- Running `init_db()` against production outside the explicit migrate command
- Adding new tables without going through Phase 2 migration system
- Any code that opens `leads.db` without going through `get_db()`

## Main Tradeoff

**Speed vs safety.** The rebuild takes time (5 phases, each with a full compound cycle). During that time, feature delivery is constrained to safe-only paths. The workshop deadline (May 30) means some feature work must proceed in parallel.

Resolution: Phase 0 and Phase 1 are the minimum viable safety floor. If only those two complete before the workshop, the system is safe enough for daily operations. Phases 2-5 can continue after the workshop.

## Biggest Risk

The biggest risk is that during the rebuild, someone (Claude Code or a future agent) runs untested code against production and wipes the DB again. The current guard (`_destructive_migration_allowed`) plus the explicit `migrate` command are the first line of defense, but they only protect against one failure mode (DROP TABLE in migrations). Other wipe vectors may exist that haven't been discovered yet.

Mitigation: Phase 0 must inventory ALL code paths that write to `leads.db`, not just migrations. Any path that could result in data loss must be identified and guarded before Phase 1 work begins.

## Suggested Compound Sequence

```
Phase 0: Safety Doctrine
  Brainstorm -> Plan -> Plan Review -> Work -> Review -> Compound
  (Est: 1 session, documentation only)

Phase 1: Environment and DB Boundary
  Brainstorm -> Plan -> Plan Review -> Work -> Review -> Compound
  (Est: 1-2 sessions, test infrastructure changes)

--- Workshop prep can proceed safely here ---

Phase 2: Migration Rebuild
  Brainstorm -> Plan -> Plan Review -> Work -> Review -> Compound
  (Est: 2-3 sessions, core architecture change)

Phase 3: Config and Targeting Rebuild
  Brainstorm -> Plan -> Plan Review -> Work -> Review -> Compound
  (Est: 1-2 sessions, mostly done already)

Phase 4: NL Planner / Executor Split
  Brainstorm -> Plan -> Plan Review -> Work -> Review -> Compound
  (Est: 1-2 sessions)

Phase 5: Workflow Unification
  Brainstorm -> Plan -> Plan Review -> Work -> Review -> Compound
  (Est: 1-2 sessions)
```

## Go / No-Go Check Before Starting Phase 0

Before Phase 0 begins, verify:
- [ ] Production DB has been restored and verified (currently 1,211 leads)
- [ ] `leads.backup-SAFE-DO-NOT-DELETE.db` exists and matches production
- [ ] All tests pass (221 pass, 1 pre-existing failure)
- [ ] No pending code changes that touch DB logic
- [ ] The explicit `migrate` command works: `python run.py migrate --allow-destructive-production`
- [ ] Normal CLI commands work without triggering migrations

## Feed-Forward

- **Hardest decision:** Whether to rebuild in place vs rewrite. Rebuild wins because the workshop deadline makes feature-delivery continuity non-negotiable.
- **Rejected alternatives:** (1) Big-bang rewrite -- too risky during workshop crunch. (2) Keep patching -- three incidents prove patches don't hold. (3) Switch to a different DB tool (e.g., Alembic) -- adds complexity and a new dependency without addressing the architectural flaw.
- **Least confident:** Whether the current safety guards (from Codex stabilization session) are sufficient to prevent another wipe during the rebuild itself. Phase 0 must answer this question before any code changes begin.
