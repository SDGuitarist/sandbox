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

**Main section enumeration:** The agent also needs to identify routes and model functions from the spec's main body. These are found by searching for:
- Route tables: headings containing "Route" or "Endpoint" followed by markdown tables with columns like `Method`, `Path`, `Handler`
- Model function definitions: headings containing "Model" or "Schema" or function signature code blocks within `### <blueprint>_models.py` or `### models/` sections
- Blueprint sections: any `### <name>/` or `## <name> Blueprint` heading

**The 6 check implementations:**

#### Check 1: Export Names Coverage (FC1)

1. Find the Export Names section by canonical prefix.
2. If section missing: FAIL with "Export Names section not found."
3. Extract all names from the Export Names table (column 1).
4. Scan all model function sections for function definitions (lines matching `def <name>(` in code blocks).
5. Scan all route handler sections for `url_for('<blueprint>.<function>')` patterns in code blocks.
6. For each function/url_for target found in the spec body but NOT in the Export Names table: FAIL.
7. Count: `<N> symbols checked, <M> missing`.

#### Check 2: Wiring Completeness (FC3)

1. Find the Cross-Boundary Wiring section by canonical prefix.
2. If section missing: FAIL with "Cross-Boundary Wiring section not found."
3. Extract all producer-consumer entries from the wiring table.
4. For each producer: verify the producing module appears in the spec's file inventory or blueprint sections.
5. For each consumer: verify the consuming file appears in the spec.
6. For each entry in the Export Names table with a "Used By" column: verify it has at least one consumer listed.
7. For any export with zero consumers: FAIL.
8. Count: `<N> entries, <M> orphaned`.

#### Check 3: Input Validation Prescriptions (FC4)

1. Find the Input Validation Prescriptions section by canonical prefix.
2. If section missing: FAIL with "Input Validation Prescriptions section not found."
3. Identify all routes from the route table that accept user input. **Narrow definition of "parsed input":**
   - Routes with `methods=['POST']` or `methods=['PUT', 'PATCH']` (form submissions)
   - Routes with `<int:id>` or `<int:*>` URL parameters (type-converted params)
   - Routes with DELETE method that reference a resource by ID (FK delete paths)
4. For each identified route: verify it appears in the Input Validation Prescriptions table with at least one validation rule.
5. Exclude: GET routes with only string query params (no type conversion). These are low-risk.
6. For any route with parsed input but no validation prescription: FAIL.
7. Count: `<N> routes checked, <M> unvalidated`.

#### Check 4: Registration Points (FC5)

1. Find the Coordinated Behaviors section by canonical prefix.
2. If section missing: FAIL with "Coordinated Behaviors section not found."
3. Extract all blueprint names from the spec (from file inventory, blueprint sections, or route table).
4. Verify each blueprint appears in the Coordinated Behaviors table or Registration Points list for:
   - Blueprint registration (mentioned in `create_app` or factory section)
   - Navbar/navigation links (if the spec has a nav section)
5. For any blueprint not registered: FAIL.
6. Count: `<N> blueprints, <M> unregistered`.

#### Check 5: Transaction Contracts (FC29)

1. Find the Transaction section by canonical prefix (matching "Transaction" + "Boundary" or "Contract").
2. If section missing: FAIL with "Transaction Contracts section not found."
3. Extract all model functions from the spec that contain write operations (keywords: `INSERT`, `UPDATE`, `DELETE`, `conn.execute` with write SQL).
4. For each write function: verify it appears in the Transaction section with one of:
   - "commits" / "COMMIT" annotation
   - "does NOT commit" / "caller commits" annotation
   - "BEGIN IMMEDIATE" annotation
5. For any write function without a transaction annotation: FAIL.
6. Count: `<N> functions, <M> unannotated`.

#### Check 6: Authorization Mode (FC35)

1. Find the Authorization Matrix section by canonical prefix.
2. If section missing AND the spec has auth-protected routes (login_required decorator or similar): FAIL with "Authorization Matrix section not found."
3. If section missing AND no auth routes: N/A.
4. Extract all non-public routes from the route table (routes behind `@login_required` or role decorators).
5. For each auth-protected route: verify it appears in the Authorization Matrix with a mode:
   - public, role-only, role+ownership, or admin-only
6. For routes annotated "role+ownership": verify the spec names the specific ownership field and comparison (e.g., "check venue.owner_id == g.user['id']").
7. For any auth-protected route without an authorization annotation: FAIL.
8. Count: `<N> routes, <M> unannotated`.

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
- WHEN a GET route has only string query params with no type conversion THE SYSTEM SHALL NOT flag it in the Input Validation surface (narrow scope)

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
- **Least confident:** Whether prefix-based heading matching handles all future plan formats. Current plans use `##` and `###` with varying suffixes. The checker matches on prefix, ignoring suffix -- this works for all 20+ existing plans. If a future plan uses a completely different heading structure, the checker will FAIL (safe direction -- forces adoption of conventions rather than silently passing).
