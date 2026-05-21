---
title: Pre-Swarm Spec Completeness Checker
date: 2026-05-21
status: brainstorm-revised-r2
trigger: Analysis of runs 046-052 showing 6 failure classes recurring despite documented agent-level rules
scope: New agent (.claude/agents/spec-completeness-checker.md) + spec template additions + autopilot step
feed_forward:
  risk: "False positives from the completeness checker may block valid specs that use unconventional structure"
  verify_first: true
---

# Pre-Swarm Spec Completeness Checker

## What We're Solving

Six failure classes keep producing P1s across builds despite being documented in agent-pitfalls.md with explicit agent rules:

| FC | Name | Builds hit (recent) | Root cause |
|----|------|---------------------|------------|
| FC1 | Naming divergence | Run 052 (supplier /new vs /create) | Export Names Table incomplete |
| FC3 | Dead wiring | Run 050 (delivered_delta) | Wiring table missing entries |
| FC4 | Validation gaps | Runs 048, 049, 052 (int() cast, FK delete) | No prescribed error handling |
| FC5 | Coordination gaps | Run 051 (DB lock registration) | Registration points not enumerated |
| FC29 | Transaction boundary | Run 052 (BEGIN vs IMMEDIATE) | No commit/no-commit annotation |
| FC35 | IDOR ownership | Runs 049, 050 (5+1 P1s) | No ownership check per route |

**Root cause is spec-level, not agent-level.** Agents follow the spec exactly. The spec author doesn't prescribe everything. Agent-level rules in pitfalls.md can't fix spec-level omissions.

The existing spec-consistency-checker (Step 9w.5) catches internal contradictions (name mismatches, type mismatches) but NOT coverage completeness (did the spec author annotate every route, every model function).

## Why This Approach

### Approach C: Mandatory spec sections + separate completeness checker (Codex-recommended)

Two changes:

1. **Add mandatory coverage tables to the spec template** -- force the spec author to think about ownership checks, transaction contracts, export names, form fields, registration points during authoring.

2. **Add a spec-completeness-checker agent** as a separate pre-swarm hard gate -- cross-references the main route/function/export lists against the coverage tables. Fails on omissions.

### Why not extend the existing spec-consistency-checker

- The existing checker is scoped to cross-section contradictions, not omission coverage (spec-consistency-checker.md:10).
- "Contradiction" and "missing prescription" are different failure types with different fixes.
- Coupling them makes the report harder to interpret and future tuning harder.
- Codex reviewed this and recommended the separate agent explicitly.

### Why not template-only (no checker)

Templates help by forcing the author to think about coverage. But templates don't prove coverage. A spec author can still forget one route, one function, or one registration point -- that's exactly the failure mode driving this change.

## What We're Building

### Phase 1 (this build): Core 6 coverage surfaces

One check category per failure class family. Hard gate, abort on FAIL.

#### Coverage Surface 1: Export Names (FC1 prevention)

Every exported symbol that crosses an agent boundary must appear in an authoritative table:

- Blueprint names
- Endpoint names (url_for targets)
- Template filenames
- Model function names
- Form field names (HTML `name` attributes)
- Route path helpers

**Check:** For every route, model function, and template referenced in the spec's main sections, verify it appears in the Export Names Table. FAIL on any symbol referenced but not registered.

**Boundary with Surface 2:** Export Names checks that symbols have canonical names. Wiring Completeness checks that cross-boundary calls have declared producers and consumers. A model function appears in Export Names (for its name) AND in Wiring (for its caller/callee relationship). No duplication -- different questions about the same symbol.

#### Coverage Surface 2: Wiring Completeness (FC3 prevention)

Every cross-boundary producer must have a declared consumer. Every consumer dependency must have a declared producer.

**Check:** For every entry in the Cross-Boundary Wiring Table, verify:
- The producer function exists in the producing module's file list
- At least one consumer is declared
- The consumer's file is listed in the spec

FAIL on orphaned producers or undeclared dependencies.

**Ordering note:** This check runs at Step 9w.6, AFTER swarm-planner (Step 7w) has produced agent assignments. The checker can cross-reference wiring entries against the assignment table.

#### Coverage Surface 3: Input Validation Prescriptions (FC4 prevention)

Every parsed numeric/date/id field must have prescribed validation behavior. Every FK delete path must specify failure handling if RESTRICT can fire.

**Check:** For every route that parses user input (form fields, URL params, query params):
- Numeric fields: spec prescribes try/except or validation with error response
- FK delete routes: spec prescribes handling for IntegrityError/RESTRICT
- Date/time fields: spec prescribes format validation

FAIL on any route with parsed input but no validation prescription. N/A for routes with no user input.

**Note:** This is the broadest surface and has the highest false-positive risk. The plan should define what counts as "parsed input" narrowly (form fields, URL params with type conversion) to avoid flagging every route that reads `request.args`.

#### Coverage Surface 4: Registration Points (FC5 prevention)

Every registration point must be enumerated in a Coordinated Behaviors or Registration Points table:

- App factory blueprint registration (every blueprint registered in `create_app`)
- Navbar/dashboard/home links (every blueprint has a nav entry)
- Role-to-dashboard maps (if multi-role)
- CLI/worker/cron registration (if present)

**Check:** For every blueprint in the spec, verify it appears in the registration table. For every nav link target, verify the target blueprint exists. FAIL on unregistered blueprints or dead nav links.

#### Coverage Surface 5: Transaction Contracts (FC29 prevention)

Every model/helper function that writes to the database must declare its transaction contract:

- "commits internally" -- function manages its own transaction
- "does NOT commit -- caller commits" -- function participates in caller's transaction
- "requires BEGIN IMMEDIATE" -- function needs exclusive lock (with concurrency scenario)

**Check:** For every function in the spec's model/helper sections that contains INSERT, UPDATE, or DELETE, verify it has a transaction annotation. FAIL on any write function without an annotation.

#### Coverage Surface 6: Authorization Mode (FC35 prevention)

Every auth-protected detail/edit/delete/action route must declare its authorization mode:

- public -- no auth required
- role-only -- role check sufficient (e.g., admin-only dashboard)
- role + ownership -- role check AND resource ownership check required
- admin-only -- admin role required

**Check:** For every non-public route in the spec, verify it has an authorization annotation. For routes annotated "role + ownership," verify the spec prescribes the specific ownership check (which field, which comparison). FAIL on any auth-protected route without an annotation.

### Phase 2 (future, after 1-2 validation runs): Extended coverage

Additive -- same checker, new check categories:

- FC9: Form field coverage (every POST route has explicit accepted field names)
- FC38: CSP/CDN coverage (CDN URLs have matching CSP allowlist)
- FC40: SQLite connection path coverage (every connection path has required PRAGMAs)
- Worker/background: bootstrap/registration/transaction rules for workers, queues, crons

Phase 2 surfaces are feature-conditional (N/A when the feature class isn't in the build).

### Report Format (stable from v1, extensible for v2)

```markdown
# Spec Completeness Check -- <project name>

**Status:** PASS | FAIL
**Date:** <date>
**Plan:** <plan path>

## Results

| Surface | Status | Findings |
|---------|--------|----------|
| Export Names (FC1) | PASS/FAIL/N/A | <count> symbols checked, <count> missing |
| Wiring Completeness (FC3) | PASS/FAIL/N/A | <count> entries, <count> orphaned |
| Input Validation (FC4) | PASS/FAIL/N/A | <count> routes, <count> unvalidated |
| Registration Points (FC5) | PASS/FAIL/N/A | <count> blueprints, <count> unregistered |
| Transaction Contracts (FC29) | PASS/FAIL/N/A | <count> functions, <count> unannotated |
| Authorization Mode (FC35) | PASS/FAIL/N/A | <count> routes, <count> unannotated |

## Details

### [Surface Name]: FAIL

| Item | Location | Issue |
|------|----------|-------|
| <symbol/route/function> | <spec section> | Missing from <table name> |
```

One row per finding. The spec author reads the report and adds the missing prescriptions before re-running.

### Gate Behavior

- **FAIL:** Any surface has missing coverage. Abort swarm launch. Spec author fixes omissions and re-runs.
- **WARN:** Coverage present but ambiguous (e.g., ownership annotation says "check owner" but doesn't name the field). WARNs do NOT block -- swarm proceeds. WARNs are logged in the report for the spec author to address during the next retry or post-swarm review.
- **N/A:** Surface not applicable to this build (e.g., no auth-protected routes, no workers).
- **PASS:** All applicable surfaces have complete coverage.

### Autopilot Integration

New step in autopilot SKILL.md, between Step 9w.5 (consistency check) and Step 10w (swarm launch):

```
### Step 9w.6: Spec Completeness Gate (MANDATORY -- SWARM ONLY)

Launch spec-completeness-checker agent with the plan path.
Read the report at docs/reports/<run-id>/spec-completeness-check.md.

If STATUS: FAIL -- fix the spec omissions, re-run Step 9w.6. Max 1 retry.
If still FAIL after retry -- abort with "SPEC INCOMPLETE: <surface> has <N> omissions."
If STATUS: PASS -- proceed to Step 10w.
```

Grouped with the consistency checker under "Pre-Swarm Structural Gates" for UX clarity.

### Spec Template Changes

Add these as mandatory sections in every swarm plan's shared interface spec. There is no physical template file -- these are conventions the plan author must include (same as Export Names Table and Coordinated Behaviors are conventions today). The completeness checker validates they exist.

1. **Export Names Table** -- already common but not mandatory. Make it required.
2. **Cross-Boundary Wiring Table** -- already common. Make it required.
3. **Input Validation Prescriptions** -- new section. One row per route with parsed input.
4. **Registration Points** -- exists as Coordinated Behaviors in some specs. Standardize.
5. **Transaction Contracts** -- new column in model function tables ("Commits: yes/no/immediate").
6. **Authorization Matrix** -- new section. One row per auth-protected route.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Extend existing checker vs new agent | New agent | Different concern (completeness vs consistency). Codex recommended. |
| All 10 surfaces vs core 6 | Core 6 first | Covers all recent P1s. Validates mechanism before expanding. |
| Hard gate vs advisory | Hard gate (FAIL aborts) | Spec omissions at swarm scale produce predictable P1s. Stopping is cheaper than fixing. |
| Template-only vs template + checker | Both | Template forces authoring. Checker verifies coverage. Neither alone is sufficient. |
| Report format | Stable from v1, extensible | Phase 2 adds rows to the same table. No schema changes. |
| Retry on FAIL | Max 1 retry | Same pattern as spec-consistency-checker. |

## Open Questions

1. **Parsing strategy:** How does the checker enumerate routes/functions/exports from a markdown spec? Options for the plan to decide:
   - **A) Require standardized table formats** -- every spec uses the same heading names and table columns. Checker finds them by heading. Pro: reliable, simple parsing. Con: constrains spec authoring.
   - **B) Heuristic markdown parsing** -- regex/pattern matching for tables, code blocks, headers. Pro: flexible. Con: fragile, varies across specs.
   - **C) Hybrid** -- require a small set of canonical table headings (Export Names, Authorization Matrix, Transaction Contracts) but allow flexible content within them. Pro: balances reliability with flexibility.

   Recommendation: C. The existing consistency checker already relies on finding specific spec sections by heading name. Extending that convention is lower-risk than inventing a general parser.

2. **Who fills the mandatory sections in autopilot?** Plan deepening agents currently add corrections to existing spec sections. The new mandatory sections need to be authored during planning (Step 5 or Step 6) so they exist before deepening. Deepening can then refine them, and the completeness checker validates at Step 9w.6.

## Resolved Questions

1. **Which approach?** C -- separate agent + mandatory template sections. (Codex review)
2. **Scope?** Core 6 first, Phase 2 adds 4 more after validation. (Codex review)
3. **Hard gate or advisory?** Hard gate. Cost of stopping < cost of predictable P1s. (Codex review)
4. **Template alone sufficient?** No. Templates don't prove coverage. Checker cross-references. (Codex review)

## Prior Lessons Applied

- autopilot-skips-non-step-instructions (2026-05-06): Gate must be a numbered step with MANDATORY label
- compound-bash-instruction-refactor (2026-04-09): Report format uses structural tables, not prose
- sandbox-autonomy-hardening (2026-05-13): Extraction pattern for verify-self-audit informs agent structure
- spec-convergence-loop (2026-04-30): Human verification catches P0s AI misses -- this checker handles the structural subset that IS automatable

## Feed-Forward

- **Hardest decision:** Scoping to core 6 instead of all 10. The extra 4 are real problems but feature-conditional. Adding them now risks false positives on builds without those features.
- **Rejected alternatives:** Extending the existing spec-consistency-checker (couples concerns, harder to tune). Template-only without checker (doesn't prove coverage). All 10 surfaces in v1 (broader than evidence requires).
- **Least confident:** Whether the completeness checker can reliably parse spec structure. See Open Question 1 for candidate strategies. The hybrid approach (canonical headings, flexible content) is the recommended starting point. First run validates false-positive rate.
