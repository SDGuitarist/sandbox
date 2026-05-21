---
title: "feat: Pre-Swarm Spec Completeness Checker"
type: feat
status: active
date: 2026-05-21
origin: docs/brainstorms/2026-05-21-spec-completeness-checker-brainstorm.md
swarm: false
feed_forward:
  risk: "FC4 (Input Validation) surface is the broadest and most likely to produce false positives. Narrow definition of 'parsed input' is load-bearing."
  verify_first: true
---

# feat: Pre-Swarm Spec Completeness Checker

## Enhancement Summary

**Deepened on:** 2026-05-21
**Research agents used:** heading-pattern validator (18 plans), FC4 scope calibrator (3 plans), consistency-checker overlap analyzer

### Key Improvements
1. Heading matching validated against all 18 existing swarm plans -- zero false positives, zero edge cases
2. FC4 narrow scope confirmed: covers ~50% of routes (all state-changing), GET routes have 0 P1 history across all builds
3. N/A strategy clarified: two distinct N/A types (section-absent vs condition-absent) with different implications

## Overview

Add a spec-completeness-checker agent as a hard pre-swarm gate (Step 9w.6) that catches spec-level omissions before agents launch. Six coverage surfaces targeting 6 recurring failure classes (FC1, FC3, FC4, FC5, FC29, FC35) that keep producing P1s despite documented agent-level rules.

(see brainstorm: docs/brainstorms/2026-05-21-spec-completeness-checker-brainstorm.md for full analysis, Codex review, and all design decisions)

## Problem Statement

Agent-level rules in pitfalls.md can't fix spec-level omissions. When the spec doesn't prescribe a route's ownership check, no agent rule can make the agent add one -- the agent follows the spec. Analysis of runs 046-052 shows 6 failure classes recurring because specs are incomplete, not because agents disobey.

The existing spec-consistency-checker (Step 9w.5) catches contradictions (name A != name B). It does NOT catch omissions (name A is never declared). This is a different concern requiring a separate gate.

## What Must Not Change

- The spec-consistency-checker agent and its Step 9w.5 placement
- The swarm-planner, contract-checker, and other existing gates
- The autopilot flow for solo builds (completeness check is swarm-only)
- Existing plan section naming that already works (Export Names Table, Cross-Boundary Wiring Table, Coordinated Behaviors)
- Backwards compatibility: specs without the new sections should get FAIL (forcing adoption), not silent PASS

## Proposed Solution

Three artifacts, ordered by dependency:

### Task 1: Write the spec-completeness-checker agent

**File:** `.claude/agents/spec-completeness-checker.md`

**Structure:** Follows the exact pattern of spec-consistency-checker.md (read-only agent, receives plan path + reports dir, writes structured report, PASS/FAIL/WARN/N/A status).

**Frontmatter:**

```yaml
---
name: spec-completeness-checker
description: Pre-swarm gate that checks whether a spec prescribes complete coverage for 6 critical surfaces (export names, wiring, validation, registration, transactions, authorization). Catches omissions that produce predictable P1s at swarm scale.
tools: Read, Grep, Glob, Write
model: sonnet
---
```

**Inputs:** Same as consistency checker:
1. Path to the plan document
2. Path to the reports directory

**Parsing strategy (resolves brainstorm Open Question 1):** Option C -- Hybrid.

The agent finds coverage sections by searching for canonical heading prefixes. Heading matching is case-insensitive and ignores suffixes (e.g., "(FC1 Prevention)"). The agent searches for these prefixes:

| Canonical Prefix | Matches |
|---|---|
| `Export Names` | "Export Names Table", "Export Names Table (FC1 Prevention)" |
| `Cross-Boundary Wiring` | "Cross-Boundary Wiring Table", "Cross-Boundary Wiring Section" |
| `Input Validation Prescriptions` | new section -- exact match |
| `Coordinated Behaviors` | "Coordinated Behaviors Table", "Coordinated Behaviors (MANDATORY for all agents)" |
| `Transaction` (followed by `Boundary` or `Contract`) | "Transaction Boundary Annotations", "Transaction Boundary Rules", "Transaction Contracts" |
| `Authorization Matrix` | "Authorization Matrix" |

This matches the existing consistency checker's approach (it finds sections by heading name). No general markdown parser needed.

**Validation evidence:** All 6 patterns tested against all 18 existing swarm plans. Zero false positives, zero false negatives. Patterns handle trailing annotations like "(FC1 Prevention)", "(MANDATORY for all agents)", and variant suffixes ("Table", "Section", "Rules", "Annotations"). Only 1/18 plans (GigSheet) has all 4 existing sections -- this reflects recent standard adoption, not pattern failure.

**N/A strategy (unified control flow for all 6 surfaces):**

Every surface follows the same decision tree:

1. **Enumerate the qualifying items** (functions, routes, blueprints) that the surface covers.
2. **If zero qualifying items:** N/A. The surface doesn't apply to this build. Stop.
3. **If qualifying items exist:** find the canonical heading.
4. **If heading missing:** FAIL with "[section] not found. <N> items require coverage."
5. **If heading found:** evaluate row-by-row coverage. Missing rows = FAIL.

This means:
- Surfaces 1, 2, 4, 5 (Export Names, Wiring, Registration, Transactions) will almost always have qualifying items in swarm builds, so missing headings produce FAIL.
- Surfaces 3, 6 (Input Validation, Authorization) may have zero qualifying items in builds without parsed input or auth routes, producing N/A.
- No surface ever produces N/A for "heading not found" -- that's always FAIL when qualifying items exist.

**Main section enumeration:** The agent also needs to identify routes and model functions from the spec's main body. These are found by searching for:
- Route tables: headings containing "Route" or "Endpoint" followed by markdown tables with columns like `Method`, `Path`, `Handler`
- Model function definitions: headings containing "Model" or "Schema" or function signature code blocks within `### <blueprint>_models.py` or `### models/` sections
- Blueprint sections: any `### <name>/` or `## <name> Blueprint` heading

**The 6 check implementations:**

#### Check 1: Export Names Coverage (FC1)

**Scope:** The checker enumerates three identifier classes deterministically. Other identifier types (template filenames, CSS classes, form field names) are not reliably enumerable from markdown specs and are excluded from automated checking.

**Identifier classes checked:**

| Class | Enumeration rule | Where found in spec |
|-------|-----------------|-------------------|
| Model functions | Lines matching `def <name>(` inside python code blocks | `### *_models.py` or `### models/` sections |
| Endpoint names | `url_for('<blueprint>.<function>')` patterns in code blocks | Route handler sections |
| Blueprint names | `### <name>/` section headings or entries in file inventory tables | File inventory, blueprint sections |

**Steps:**

1. Find the Export Names section by canonical prefix.
2. If section missing: FAIL with "Export Names section not found."
3. Extract all names from the Export Names table (column 1).
4. Enumerate identifiers using the three rules above.
5. For each enumerated identifier NOT in the Export Names table: FAIL.
6. Count: `<N> identifiers checked, <M> missing`.

#### Check 2: Wiring Coverage (FC3)

**Scope:** Does every cross-boundary function appear in the wiring table? This is a COVERAGE check -- "is the function declared in the wiring table at all?" The consistency checker (Category 6) already verifies that declared wiring entries have matching consumers. This check catches functions that are MISSING from the table entirely.

1. Find the Cross-Boundary Wiring section by canonical prefix.
2. If section missing: FAIL with "Cross-Boundary Wiring section not found."
3. Extract all function names from the wiring table (producer column).
4. Extract all functions from the Export Names table that have a "Used By" column listing consumers in other agents (cross-boundary functions).
5. For each cross-boundary function in the Export Names table: verify it also appears in the Cross-Boundary Wiring table as a producer.
6. For any cross-boundary function missing from the wiring table: FAIL.
7. Count: `<N> cross-boundary functions, <M> missing from wiring table`.

**Boundary with consistency checker:** Completeness asks "is this function in the wiring table?" Consistency asks "do the names in the wiring table match the export names?" No overlap.

#### Check 3: Input Validation Prescriptions (FC4)

**Control flow (explicit, no ambiguity):**

1. **Enumerate qualifying routes first.** Scan the route table for routes matching the narrow definition of "parsed input":
   - Routes with `methods=['POST']` or `methods=['PUT', 'PATCH']` (form submissions)
   - Routes with `<int:id>` or `<int:*>` URL parameters (type-converted params)
   - Routes with DELETE method that reference a resource by ID (FK delete paths)
   - **Exclude:** GET routes with only string query params (no type conversion)
2. **If zero qualifying routes found:** mark surface as N/A. Stop.
3. **If qualifying routes exist:** find the Input Validation Prescriptions section by canonical prefix.
4. **If section missing:** FAIL with "Input Validation Prescriptions section not found. <N> routes require validation prescriptions."
5. **If section exists:** for each qualifying route, verify it appears in the table with at least one validation rule specifying: what input is validated, how (try/except, regex, allowlist), and what error response (400, flash, redirect).
6. For any qualifying route missing from the table: FAIL.
7. Count: `<N> qualifying routes, <M> unvalidated`.

**Scope calibration (validated against 3 recent plans):**

| Plan | Total Routes | Flagged | % Examined |
|------|-------------|---------|------------|
| GigSheet (31 agents) | 70 | 35 | 50% |
| VenueConnect (25 agents) | 42 | 18 | 43% |
| RestaurantOps (29 agents) | 106 | 50 | 47% |

GET routes with string query params have produced 0 P1s across all builds. The narrow scope covers all state-changing operations while avoiding false positives on read-only endpoints.

#### Check 4: Registration Points (FC5)

**Scope:** This check covers blueprint and navigation registration only -- the two registration surfaces that are deterministically enumerable. The broader FC5 problem (flash message consistency, activity logging patterns, etc.) is addressed by the Coordinated Behaviors section EXISTING with prescriptive content. Verifying that the content of those prescriptions is correct is a human/review concern, not an automated completeness check.

**What this check verifies:**
- Every blueprint defined in the spec is registered in `create_app` or the factory section
- Every blueprint with user-facing routes has a navigation/navbar entry (if the spec has a nav section)

**What this check does NOT verify:**
- Flash message pattern consistency across blueprints
- Activity logging completeness
- Shared CSS/JS inclusion
- Role-to-dashboard map completeness (covered by Surface 6 Authorization Matrix)

**Steps:**

1. Find the Coordinated Behaviors section by canonical prefix.
2. If section missing: FAIL with "Coordinated Behaviors section not found."
3. Extract all blueprint names from the spec (from file inventory, blueprint sections, or route table).
4. Verify each blueprint appears in a registration list within the Coordinated Behaviors section (look for `register_blueprint`, `create_app`, or a Registration Points subsection).
5. If the spec has a navigation/navbar section: verify each user-facing blueprint has a nav entry.
6. For any blueprint not registered: FAIL.
7. Count: `<N> blueprints, <M> unregistered`.

#### Check 5: Transaction Contracts (FC29)

**Two valid annotation forms (checker must detect both):**

- **Form A -- Dedicated section:** A section with canonical heading prefix "Transaction" + "Boundary" or "Contract". Functions listed under "commits" / "does NOT commit" / "BEGIN IMMEDIATE" sublists. Example: GigSheet plan line 1916.
- **Form B -- Column in model tables:** Model function tables include a "Commits" or "Transaction" column with values like "yes", "no/caller", "BEGIN IMMEDIATE". Example: a table row `| update_order | UPDATE | no -- caller commits |`.

**Steps:**

1. **Detect Form A:** Search for a section with canonical heading prefix "Transaction" + ("Boundary" or "Contract").
2. **Detect Form B:** Search model function tables (under `### *_models.py` headings) for a column header containing "Commit" or "Transaction".
3. If neither Form A nor Form B found: FAIL with "Transaction Contracts not found (no dedicated section and no Commits column in model tables)."
4. Extract all model functions from the spec that contain write operations. **Enumeration rule:** lines matching `def <name>(` in model code blocks where the code block also contains `INSERT`, `UPDATE`, `DELETE`, or `conn.execute`.
5. For each write function: verify it appears in the transaction annotations (Form A list or Form B column) with one of:
   - "commits" / "COMMIT" / "yes" (commits internally)
   - "does NOT commit" / "caller commits" / "no" (caller's transaction)
   - "BEGIN IMMEDIATE" / "immediate" (exclusive lock with concurrency scenario)
6. For any write function without a transaction annotation: FAIL.
7. Count: `<N> write functions, <M> unannotated`.

#### Check 6: Authorization Mode (FC35)

**Control flow (same unified pattern as Check 3):**

1. **Enumerate qualifying routes first.** Scan route handler sections for auth-protected routes: lines containing `@login_required`, `@require_role`, `@admin_required`, or similar auth decorators in code blocks.
2. **If zero auth-protected routes found:** mark surface as N/A. Stop.
3. **If auth routes exist:** find the Authorization Matrix section by canonical prefix.
4. **If section missing:** FAIL with "Authorization Matrix section not found. <N> auth-protected routes require authorization annotations."
5. **If section exists:** for each auth-protected route, verify it appears in the matrix with a mode:
   - public, role-only, role+ownership, or admin-only
6. For routes annotated "role+ownership": verify the spec names the specific ownership field and comparison (e.g., "check venue.owner_id == g.user['id']"). If the field is unnamed: WARN.
7. For any auth-protected route missing from the matrix: FAIL.
8. Count: `<N> auth routes, <M> unannotated`.

**Output contract:** Write report to `[reports-directory]/spec-completeness-check.md`. Format matches the brainstorm's report template:

```markdown
# Spec Completeness Check -- <project name>

**Status:** PASS | FAIL
**Date:** <date>
**Plan:** <plan filename>

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

## Summary

- **Total checks:** N
- **PASS:** X
- **FAIL:** Y
- **WARN:** Z
- **N/A (section absent):** W

STATUS: PASS
```

Use `STATUS: PASS` if zero FAILs (WARNs allowed).
Use `STATUS: FAIL -- N omissions found across M surfaces` if any FAILs exist.

**Rules (same discipline as consistency checker):**
1. Extract all checkable assertions first, then verify each.
2. Mark each surface as PASS, FAIL, WARN, or N/A.
3. FAIL = missing coverage (route/function/export not in coverage table).
4. WARN = coverage present but ambiguous (e.g., ownership check named but field not specified).
5. N/A = surface not applicable (e.g., no auth routes, no write functions).
6. Do not modify the spec. Report only.

**Estimated size:** ~120-150 lines. The consistency checker is 107 lines. This one has 6 check categories (vs 6 for consistency) but each check is simpler (presence check vs name matching).

### Task 2: Add Step 9w.6 to autopilot SKILL.md

**File:** `.claude/skills/autopilot/SKILL.md`

**Insert after Step 9w.5 (line ~285), before Step 10w (line ~287):**

```markdown
### Step 9w.6: Spec Completeness Gate (MANDATORY -- SWARM ONLY)

Use the **spec-completeness-checker** agent. Pass:
1. The path to the plan document
2. `docs/reports/<run-id>/` (the reports directory created in Step 6.1)

The agent writes its report to `docs/reports/<run-id>/spec-completeness-check.md`.
Read that file and check STATUS.
- If PASS: continue to Step 10w (Parallel Swarm Work).
- If FAIL: read the Details section. Fix the spec omissions identified in the
  report (add missing entries to the coverage tables). Re-run Step 9w.6. Max
  1 retry.
- If still FAIL after retry: abort with
  "SPEC INCOMPLETE: <N> omissions across <M> surfaces. See report."

This gate catches spec-author omissions (missing export names, missing
ownership checks, unannotated transactions) that produce predictable P1s at
swarm scale. It is separate from Step 9w.5 (consistency) which catches
contradictions.
```

**Lines added:** ~16 lines.

**Also update the comment near Step 9w.5** to group both gates:

```markdown
### Pre-Swarm Structural Gates (Steps 9w.5 and 9w.6)

These gates run after run-id generation and before swarm agent spawn.
Step 9w.5 checks for contradictions. Step 9w.6 checks for omissions.
Both must PASS for the swarm to launch.
```

**Lines changed:** ~4 lines (replace existing Step 9w.5 comment).

### Task 3: Document mandatory spec sections in CLAUDE.md

**File:** `CLAUDE.md` (project-level)

**Add a new section** under "Required Artifacts" or as a standalone section:

```markdown
## Mandatory Spec Coverage Sections (Swarm Plans)

Every swarm plan's shared interface spec must include these 6 sections.
The spec-completeness-checker (Step 9w.6) validates they exist and are
complete. Missing sections FAIL the pre-swarm gate.

1. **Export Names Table** -- every function, route name, template, and form field
   that crosses agent boundaries. Columns: Name, Type, Defined By, Used By.
2. **Cross-Boundary Wiring Table** -- every cross-module function call with
   producer file, consumer file, and import path.
3. **Input Validation Prescriptions** -- every POST/PUT route and typed URL param
   with prescribed validation and error response. Columns: Route, Input, Validation, Error Response.
4. **Coordinated Behaviors** -- blueprint registration, navbar links, role maps,
   flash message patterns, and any other behavior that must be consistent across agents.
5. **Transaction Contracts** -- every model function that writes to the DB annotated
   with: "commits internally", "does NOT commit", or "requires BEGIN IMMEDIATE".
6. **Authorization Matrix** -- every auth-protected route with mode: public,
   role-only, role+ownership (with field), or admin-only.

Sections 1, 2, and 4 already exist in most specs. Sections 3, 5, and 6 are new.
Section 5 can be a column in model function tables instead of a separate section.
```

**Lines added:** ~20 lines.

**Who fills these in autopilot? (resolves brainstorm Open Question 2):**
The plan author includes these sections during plan authoring (Steps 4-5 of the autopilot). Plan deepening agents (Step 6) refine them. The completeness checker (Step 9w.6) validates after deepening. This matches the existing flow -- Export Names Table and Coordinated Behaviors are already authored during planning.

## Technical Considerations

- **No overlap with consistency checker (re-scoped after Codex review).** Consistency checks declared-name coherence: do the names in declared surfaces match each other? (Category 4: export name A == import name A? Category 6: does every declared export have a declared consumer?) Completeness checks coverage: is every function/route/blueprint represented in the coverage tables at all? Specifically, Surface 2 (Wiring Coverage) only checks whether cross-boundary functions from the Export Names table appear in the Wiring table as producers. It does NOT check whether wiring entries have consumers -- that's the consistency checker's Category 6.
- **No new dependencies.** The agent uses only Read, Grep, Glob, Write (same as consistency checker).
- **Heading matching is prefix-based.** The agent searches for `## Export Names` or `### Export Names` (case-insensitive, ignoring trailing text). This handles all existing heading variations without requiring a spec format migration.
- **FC4 narrow scope is load-bearing.** The Input Validation surface only checks POST/PUT routes and typed URL params (`<int:id>`). GET routes with string query params are excluded. This prevents false positives on read-only endpoints.
- **Solo builds unaffected.** Step 9w.6 is swarm-only. Solo builds skip it entirely.
- **SKILL.md growth.** Autopilot goes from 636 to ~656 lines (+20). Acceptable -- the step is small and follows established patterns.
- **Phase 2 extensibility.** The report format has one row per surface. Adding FC9/FC38/FC40/worker surfaces in Phase 2 means adding rows to the same table and check categories to the agent. No schema change needed.

## Implementation Order

| Order | Task | File | Lines Changed |
|-------|------|------|---------------|
| 1 | Write spec-completeness-checker agent | .claude/agents/spec-completeness-checker.md (new) | ~130 new |
| 2 | Add Step 9w.6 to autopilot | .claude/skills/autopilot/SKILL.md | ~20 added |
| 3 | Document mandatory sections | CLAUDE.md | ~20 added |

**Ordering:** Task 1 is independent. Task 2 depends on Task 1 (references the agent). Task 3 is independent but should be done last (documents the convention after the mechanism exists).

**Total footprint:** 1 new file (~130 lines), 2 existing files modified (~40 lines added).

## Acceptance Tests

### Happy Path

- WHEN a swarm plan has all 6 mandatory coverage sections with complete entries THE SYSTEM SHALL produce a spec-completeness-check.md report with STATUS: PASS
- WHEN the autopilot reaches Step 9w.6 with a PASS report THE SYSTEM SHALL proceed to Step 10w (Parallel Swarm Work) without interruption
- WHEN a plan has an Export Names Table where every model function in the spec body appears in the table THE SYSTEM SHALL mark the Export Names surface as PASS

### Error Cases

- WHEN a swarm plan is missing the Export Names Table section THE SYSTEM SHALL produce STATUS: FAIL with "Export Names section not found"
- WHEN a swarm plan has an Export Names Table but `create_supplier()` is defined in a model section without appearing in the table THE SYSTEM SHALL produce FAIL for the Export Names surface with the specific missing symbol
- WHEN a swarm plan has a POST route `/orders/create` with `request.form.get('quantity')` but no Input Validation Prescriptions entry for that route THE SYSTEM SHALL produce FAIL for the Input Validation surface
- WHEN a swarm plan has a route with `@login_required` but no entry in the Authorization Matrix THE SYSTEM SHALL produce FAIL for the Authorization Mode surface
- WHEN a swarm plan has a model function `update_order_status()` with an UPDATE statement but no transaction annotation THE SYSTEM SHALL produce FAIL for the Transaction Contracts surface
- WHEN Step 9w.6 produces STATUS: FAIL and the spec author fixes the omissions and re-runs THE SYSTEM SHALL accept the fixed spec on the retry (max 1 retry)
- WHEN Step 9w.6 produces STATUS: FAIL twice (after 1 retry) THE SYSTEM SHALL abort with "SPEC INCOMPLETE" and not proceed to Step 10w
- WHEN a solo build reaches the autopilot THE SYSTEM SHALL skip Step 9w.6 entirely (swarm-only gate)
- WHEN a swarm plan has no auth-protected routes (no `@login_required`) THE SYSTEM SHALL mark the Authorization Mode surface as N/A, not FAIL
- WHEN a swarm plan has no POST/PUT/DELETE routes and no `<int:id>` params THE SYSTEM SHALL mark the Input Validation surface as N/A, not FAIL
- WHEN a swarm plan has qualifying POST routes but the Input Validation Prescriptions heading is missing THE SYSTEM SHALL produce FAIL (not N/A) with the count of qualifying routes
- WHEN a GET route has only string query params with no type conversion THE SYSTEM SHALL NOT flag it in the Input Validation surface (narrow scope)
- WHEN transaction annotations exist as a column in model function tables (Form B) instead of a dedicated section THE SYSTEM SHALL detect them and evaluate coverage normally

### Verification Commands

```bash
# Verify agent file exists and has correct frontmatter:
grep "name: spec-completeness-checker" .claude/agents/spec-completeness-checker.md

# Verify Step 9w.6 exists in autopilot:
grep "Step 9w.6" .claude/skills/autopilot/SKILL.md

# Verify mandatory sections documented in CLAUDE.md:
grep "Mandatory Spec Coverage" CLAUDE.md

# Verify report output format (after a test run):
grep "STATUS:" docs/reports/<run-id>/spec-completeness-check.md
```

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-05-21-spec-completeness-checker-brainstorm.md](docs/brainstorms/2026-05-21-spec-completeness-checker-brainstorm.md) -- key decisions: separate agent (not extend consistency checker), core 6 surfaces first, hard gate, hybrid parsing strategy

### Internal References

- Existing consistency checker agent: `.claude/agents/spec-consistency-checker.md` (107 lines, structural template)
- Autopilot skill Step 9w.5: `.claude/skills/autopilot/SKILL.md:271-285` (insertion point for Step 9w.6)
- GigSheet Export Names Table: `docs/plans/2026-05-20-gigsheet-plan.md:1692` (canonical table format example)
- GigSheet Transaction Annotations: `docs/plans/2026-05-20-gigsheet-plan.md:1916` (transaction format example)
- VenueConnect Authorization Matrix: `docs/plans/2026-05-19-venueconnect-plan.md:2563` (auth matrix format example)
- Agent pitfalls registry: `~/.claude/docs/agent-pitfalls.md` (FC1, FC3, FC4, FC5, FC29, FC35 definitions)

### Prior Lessons Applied

- autopilot-skips-non-step-instructions (2026-05-06): Step 9w.6 is a numbered MANDATORY step
- compound-bash-instruction-refactor (2026-04-09): Report uses structural tables, not prose
- sandbox-autonomy-hardening (2026-05-13): Follows consistency checker agent pattern exactly
- spec-convergence-loop (2026-04-30): This handles the automatable structural subset; human verification handles cross-section contradictions

## Feed-Forward

- **Hardest decision:** The narrow definition of "parsed input" for FC4. Only POST/PUT routes and typed URL params (`<int:id>`) are checked. GET routes with string query params are excluded. This prevents false positives but could miss validation gaps on read endpoints that pass strings to SQL or int() casts deep in model code. The first run validates whether this scope is correct.
- **Rejected alternatives:** Extending spec-consistency-checker (couples different concerns). Template-only without checker (doesn't prove coverage). All 10 surfaces in v1 (broader than evidence requires). Full markdown parser (fragile, unnecessary with canonical headings).
- **Least confident:** Whether prefix-based heading matching handles all future plan formats. Explicit verification targets:

  **Accepted heading variants (validated against 18 plans):**
  - `## Export Names Table` / `## Export Names Table (FC1 Prevention)` / `### Export Names Table`
  - `## Cross-Boundary Wiring Table` / `### Cross-Boundary Wiring Table` / `## Cross-Boundary Wiring Section`
  - `## Coordinated Behaviors` / `## Coordinated Behaviors Table` / `### Coordinated Behaviors (MANDATORY for all agents)`
  - `## Transaction Boundary Annotations` / `## Transaction Boundary Rules` / `## Transaction Contracts`
  - `## Authorization Matrix` / `### Authorization Matrix`

  **Safe fallback:** If a heading prefix is not found, the surface FAILs with "section not found." This is the safe direction -- false FAILs force the spec author to adopt canonical headings, while false PASSes would silently skip coverage checks.

  **When the checker should FAIL for unsupported format:** If the plan has no recognizable headings for ANY of the 4 mandatory surfaces (Export Names, Wiring, Coordinated Behaviors, Transaction Contracts), the checker produces 4 FAILs and the autopilot aborts. This is correct behavior -- a plan without any coverage sections is genuinely incomplete, regardless of format.

  **First-run validation:** Run the checker against the GigSheet plan (docs/plans/2026-05-20-gigsheet-plan.md) before deploying to a live build. It has all 4 existing sections and should produce PASS on Surfaces 1, 2, 4, 5 and FAIL on Surfaces 3, 6 (new sections not yet authored).
