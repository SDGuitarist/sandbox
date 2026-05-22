---
title: "BrewOps: 21-Agent Swarm Build with Derived State Validation"
date: 2026-05-22
run_id: "057"
app: BrewOps (Craft Brewery Manager)
tags: [flask, sqlite, swarm, derived-state, toctou, transactions, review]
agents: 21
files: 54
loc: 4343
smoke_tests: "61/61"
review_findings: "7 P1, 6 P2, 4 P3"
p1_resolved: 7
validation_targets: [concurrency-contract, defense-in-depth, derived-state]
---

# BrewOps: 21-Agent Swarm Build with Derived State Validation

## Context

Run 057 built a craft brewery management app (recipes, ingredients, batches with lifecycle state machine, tanks, taps, sales with derived state cascade, staff). 21 swarm agents, 54 files, ~4,343 LOC. The build validated 3 new mandatory spec sections introduced in Run 056: Concurrency Contract, Defense-in-Depth Matrix, and Derived State.

## Problem

Prior runs (054-056) showed that derived state -- fields computed from cross-table relationships -- was the hardest thing to get right in swarm builds. The `create_sale` function had a 4-step side effect chain (sale -> decrement volume -> check empty -> update batch status -> clear tap) that required atomic execution. The plan's Feed-Forward risk flagged this as the highest-risk area.

## Solution

### What Worked

1. **Derived State Table in the spec** prescribed ownership: `create_sale()` owns the volume->empty->tap cascade. This prevented ambiguity about which agent handles what.

2. **Concurrency Contract** prescribed `BEGIN IMMEDIATE` for 4 functions with `try/except/ROLLBACK` error handling. All 21 agents followed this correctly -- 0 FC29 (transaction boundary) violations.

3. **Defense-in-Depth Matrix** aligned every CHECK constraint in schema.sql with app-level validation. Review confirmed 100% alignment.

4. **TOCTOU Fence pattern** (from Run 056) was correctly applied in all 4 transactional functions -- re-reading authoritative state inside BEGIN IMMEDIATE.

### What the Review Found

7 P1 findings, all resolved:

| # | Finding | Root Cause | Fix |
|---|---------|-----------|-----|
| 031 | tapped->empty via advance locks tap permanently | VALID_TRANSITIONS allowed a path that bypassed create_sale's tap-clear logic | Removed 'empty' from VALID_TRANSITIONS['tapped'] |
| 032 | tanks.current_batch_id no FK to batches | Schema gap -- column had no REFERENCES clause | Added FK with ON DELETE SET NULL |
| 033 | No UNIQUE on recipe_ingredients(recipe_id, ingredient_id) | Schema gap -- duplicates cause double stock decrement | Added UNIQUE constraint |
| 034 | isolation_level=None makes conn.commit() no-op | Known pattern from Run 056 | Removed isolation_level=None (use default DEFERRED) |
| 035 | Tank/staff delete missing IntegrityError guard | Swarm inconsistency (5 of 7 delete routes had it, 2 didn't) | Added try/except to both |
| 036 | Dead code: app/app.py + app/routes.py (162 LOC) | Leftover from prior project in same repo | Deleted both files |
| 037 | Recipe ingredient removal lacks ownership check | ri_id not verified against recipe_id | Added AND recipe_id = ? to DELETE |

### Risk Resolution

**Feed-Forward risk:** "sale_models derived state chain: 4-step side effect in one transaction."

**Resolution:** The create_sale function correctly implements all 7 steps of the derived state chain inside a single BEGIN IMMEDIATE transaction with float clamping (max(0,...)) and proper ROLLBACK on exception. Flow-trace reviewer confirmed all steps present and correctly ordered.

**New risk found during review:** The `advance_batch_status` function allowed manual tapped->empty transition without clearing the tap. This was a spec gap -- the Derived State table correctly assigned ownership to create_sale, but VALID_TRANSITIONS didn't enforce that boundary. Fixed by removing 'empty' from VALID_TRANSITIONS['tapped'].

## Key Lessons

### 1. Derived State Ownership Must Be Enforced at the Transition Level
**Problem:** The spec correctly documented that create_sale owns the tapped->empty transition. But VALID_TRANSITIONS independently allowed the same transition through advance_batch_status, creating a second path that bypassed the derived state cascade.

**Lesson:** When a Derived State section assigns ownership of a transition to a specific function, the VALID_TRANSITIONS map (or equivalent) must NOT allow that same transition through any other path. Add a "Blocked Transitions" column to the Derived State table.

**Failure class:** New -- FC45: "Derived state bypass via alternative transition path."

### 2. Schema FK Gaps Are Invisible Until Delete
**Problem:** `tanks.current_batch_id` was `INTEGER UNIQUE` with no `REFERENCES`. This worked fine for all creation and update flows. The gap only manifested on delete -- deleting a batch left the tank permanently occupied.

**Lesson:** Every integer column that stores an ID from another table needs a REFERENCES clause. Add a "FK Audit" checklist item to the spec-completeness-checker: "every *_id column has REFERENCES."

**Failure class:** FC46: "Phantom FK -- integer column stores ID but has no REFERENCES constraint."

### 3. The isolation_level=None Pattern Persists Across Builds
**Problem:** This is the same conn.commit() no-op issue found in Run 056 (CoWorkFlow). The pattern recurred because the db.py template used by the scaffold agent still had `isolation_level=None`.

**Lesson:** Update the db.py template in the scaffold agent's brief to use default isolation_level. This is now a 3-build recurrence (054, 056, 057).

### 4. Delete Route Guards Need a Consistency Checklist
**Problem:** 5 of 7 delete routes had IntegrityError handling; 2 didn't. Plus, occupied tank/tap deletion should be blocked at the app level, not just by FK constraints.

**Lesson:** Add a "Delete Guards" row to the Coordinated Behaviors spec section. Every delete route must have: (1) entity-not-found -> 404, (2) active-reference -> flash error, (3) IntegrityError -> flash error.

## Validation Results

| Target | Result | Evidence |
|--------|--------|----------|
| Concurrency Contract | PASS | All 4 BEGIN IMMEDIATE functions have try/except/ROLLBACK |
| Defense-in-Depth Matrix | PASS | All 12 CHECK constraints mirrored at app level |
| Derived State | PARTIAL -> PASS after fix | create_sale cascade correct; advance_batch_status gap fixed (#031) |

## Stats

- Swarm agents: 21
- Files created: 54
- Lines of code: ~4,343
- Smoke tests: 61/61
- Review findings: 17 (7 P1, 6 P2, 4 P3)
- P1s resolved: 7/7
- New failure classes: 2 (FC45, FC46)
- Known pattern recurrences: 1 (isolation_level=None, 3rd occurrence)

## Feed-Forward

- **Hardest decision:** Whether to add tap-clear logic to advance_batch_status (Option B) or remove the transition entirely (Option A). Chose Option A because the Derived State table explicitly assigns ownership to create_sale -- adding a second code path would violate that ownership.
- **Rejected alternatives:** Adding a JSON API layer (agent-native review suggested it, but this is a single-admin web app -- deferred to P3).
- **Least confident:** The isolation_level change from None to DEFERRED. The BEGIN IMMEDIATE functions explicitly manage their own transactions, so they should work with either mode. But if any code path was accidentally relying on autocommit behavior, the change could surface bugs not covered by the 61 smoke tests.
