---
project: restaurant-kitchen-mgmt
date: 2026-05-21
run: "052"
app: RestaurantOps
tech_stack: Flask + SQLite + Jinja2
build_method: swarm
agent_count: 29
files: 98
loc: 8178
merge_conflicts: 0
fc37_failures: 0
p1_findings: 8
p2_findings: 16
status: complete
tags: [flask, sqlite, swarm, restaurant, inventory, orders, reservations]
---

# Solution: RestaurantOps -- 29-Agent Swarm Build

## What Was Built

A single-location restaurant operations management system with 14 feature domains:
menu management, recipes with ingredients, allergen tracking, ingredient-level
inventory with stock movements, supplier management, purchase orders with receipt
workflow, customer orders with kitchen prep status, table management, reservations,
staff scheduling, daily specials, and customer reviews.

**Key metrics:** 98 files, ~8,178 LOC, 29 swarm agents, 0 merge conflicts,
0 FC37 failures (all agents committed), 34/34 smoke tests passed.

## What Went Right

### 1. Zero FC37 Failures (0% vs 56% in Run 049)

Every swarm agent committed its files. The explicit commit instruction in
each agent brief ("MUST git add + git commit") plus the FC37 warning
eliminated the pattern that caused 14/25 failures in VenueConnect.

### 2. Zero Merge Conflicts at 29 Agents

The model/route split (each domain gets two agents: one for models, one for
routes+templates) kept file ownership clean. No two agents touched the same
substantive file. The only overlaps were empty `__init__.py` files.

### 3. Deepening Caught P0 Before Swarm Launch

The best-practices-researcher found that `BEGIN IMMEDIATE` is incompatible
with Python's default `isolation_level`. Without `isolation_level=None` in
`get_db()`, every order preparation and cancellation would have crashed at
runtime. This was caught and fixed in the plan before any agent saw the spec.

### 4. Spec Consistency Checker Caught 3 Cross-Section Contradictions

The pre-swarm gate found: (1) menu.detail cost function pointed to wrong
module, (2) orders.prepare wiring bypassed the transaction-owning function,
(3) orders.cancel wiring bypassed conditional inventory restore. All fixed
before agents launched.

### 5. Prescriptive Coordinated Behaviors

The 10-item Coordinated Behaviors table (flash messages, form styling, table
styling, empty states, database connection pattern, status badges, etc.) kept
all 14 blueprints consistent. The Python reviewer found only 1 flash category
inconsistency (P2) across 14 blueprints -- the prescriptive code blocks work.

## What Went Wrong

### 1. Supplier Routes Agent Diverged from Spec (FC1 Instance)

The supplier_routes agent used `/new` instead of `/create` for the create
form URL, `supplier_id` instead of `id` for URL parameters, and `update`
instead of `edit` for the edit function name. This despite the spec having
an explicit url_for Name Registry. The agent also omitted length truncation
on all form fields.

**Root cause:** The agent brief mentioned FC1 but the supplier form fields
are simpler than other blueprints (no parallel arrays, no money fields),
so the agent took shortcuts on naming convention.

**Lesson:** FC1 violations scale with agent count. At 29 agents, even one
divergent agent creates assembly work.

### 2. Security Review Found 3 P1s in Shared Infrastructure

The scaffold/core agent did not: (a) make logout a POST route (CSRF-driven
session kill via GET), (b) add admin password blocklist (default 'admin'),
(c) set SESSION_COOKIE_SECURE. These are all standard security patterns
present in prior builds (gigsheet, venueconnect).

**Root cause:** The core agent brief focused on the plan's App Configuration
section, which didn't prescribe logout method or admin password blocklist.
These were omitted from the plan because the brainstorm chose "single shared
password" auth and didn't think through the security implications.

**Lesson:** Auth security checklist should be in the spec template, not
left to the brainstorm's auth decision. Add to shared-spec-flask.md:
"Logout must be POST. Password-based auth needs a blocklist check.
SESSION_COOKIE_SECURE = not app.debug."

### 3. Order Status Transitions Used BEGIN Instead of BEGIN IMMEDIATE

The order_routes agent used plain `BEGIN` for ready/serve/close transitions.
Under concurrent kitchen board usage, this allows a race condition where two
users read the same status before either locks. The `prepare` and `cancel`
routes were correct (model functions use BEGIN IMMEDIATE) but the simpler
transitions weren't.

**Root cause:** The spec's Coordinated Behaviors #8 showed `BEGIN IMMEDIATE`
only for "atomic multi-table operations." The agent interpreted single-table
status updates as not requiring IMMEDIATE. But the real criterion is
"read-then-write with validation" -- any status transition that reads current
status before updating needs IMMEDIATE to prevent TOCTOU races.

**Lesson:** The Coordinated Behaviors table should say "All status transitions
use BEGIN IMMEDIATE" not just "multi-table operations."

## Risk Resolution

**Risk from brainstorm Feed-Forward:** "Whether 30+ agents at this feature
breadth will produce consistent UX patterns across 14 blueprints."

**What actually happened:** The Coordinated Behaviors table worked. With 10
prescriptive code blocks covering flash messages, form styling, table styling,
empty states, error handling, database connection pattern, status badges, and
navigation, the 14 blueprints came out consistent. The Python reviewer found
only 1 flash category inconsistency (P2-5: `close_order` used `success`
instead of `info`). The prescriptive approach scales -- 29 agents produced
nearly identical UX patterns.

**Delta between expectation and reality:** The risk was about UX consistency.
The actual problems were about spec completeness (security patterns not
prescribed, BEGIN IMMEDIATE criteria unclear, supplier naming divergence).
The Coordinated Behaviors table prevented the feared "14 UX dialects" but
couldn't prevent individual agents from diverging on paths not covered by the
table.

## Key Patterns for Future Builds

1. **Model/route split for swarm builds:** Each domain gets 2 agents (models + routes). Keeps file ownership clean, eliminates merge conflicts. Trade-off: 29 agents instead of 14, but each agent is smaller and simpler.

2. **isolation_level=None is mandatory for Flask + SQLite:** Python's default `isolation_level=""` creates implicit transactions that conflict with manual `BEGIN IMMEDIATE`. Always use `isolation_level=None` and explicit `BEGIN`/`conn.commit()`.

3. **Pre-swarm spec consistency gate catches cross-section bugs:** The 3 contradictions caught would have affected all 29 agents. Gate cost: ~3 minutes. Bug cost if missed: hours of assembly debugging.

4. **Prescriptive Coordinated Behaviors scale to 29 agents:** 10 code-block patterns produced 14 consistent blueprints. The key is showing exact code, not just describing the pattern.

5. **Auth security checklist belongs in the spec template:** Logout method, password blocklist, session cookie security should be prescribed, not left to individual agents.

## Feed-Forward

- **Hardest decision:** Model/route split (29 agents) vs single-agent-per-domain (14 agents). The split worked -- zero conflicts, clean ownership -- but doubled the agent count.
- **Rejected alternatives:** Single agent per domain (too many files per agent), adding rate limiting (decided MVP doesn't need it), CSP header (conflicts with Bootstrap CDN).
- **Least confident:** Whether the P2 findings (16 deferred) will cause runtime issues. The broad `except Exception` pattern (P2-1) masks programming errors during development. The missing field length limits on suppliers (P2-4) could allow DoS via large payloads.
