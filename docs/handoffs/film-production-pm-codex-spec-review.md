Read these files first for project context:
  - CLAUDE.md  (sandbox operating contract — esp. "Mandatory Spec Coverage Sections")
  - docs/plans/film-production-pm-plan.md  (the spec under review, 16-agent swarm)
  - docs/brainstorms/2026-06-02-film-production-pm-brainstorm.md
  - docs/reports/film-production-pm/convergence-catches.md  (the catches I already found + fixed)
  - docs/roadmap-to-fully-unattended.md  (why this review matters: §1, §6)

CONTEXT: This is a spec-convergence review before an unattended autopilot swarm. The
spec passed an internal completeness pass; I (Claude Code) then ran a structural
verification and found 11 issues, fixing 9 (see convergence-catches.md disposition table).
This is the fresh-context second opinion. Your highest-value target is the failure class
the automated gates CANNOT catch: CROSS-SECTION CONTRADICTIONS — where each spec section
is internally consistent but two sections are mutually incompatible. Both P0s I found
(FTS double-maintenance, FTS trigger ownership) were of this kind.

REVIEW IN THIS ORDER:

1. Hunt for NEW cross-section contradictions I missed. Cross-check, field-by-field:
   - The call sheet surface (HIGHEST RISK): generate_call_sheet + get_call_sheet_scenes +
     get_call_sheet_cast vs the 6 Orchestration Entrypoint signatures vs the
     Cross-Boundary Wiring Table vs Template Render Context vs call_sheet_cast schema
     (status enum W/SW/WF/SWF/H — is its value at generation actually specified?).
   - Every return-shape `keys:` list in the Orchestration Entrypoints table vs how the
     consumer uses those keys (templates + callsheet_models).
   - Authorization Matrix vs Route Table vs Input Validation — any route in one table
     missing or contradicting another.

2. Verify my 9 fixes did NOT introduce new contradictions. Specifically:
   - F-H1/H2 (FTS single-writer): is index_entity/remove_entity now the ONLY writer?
     Any remaining trigger reference anywhere? Are routes told to call them in the same
     transaction as the source write (and does that interact badly with model functions
     that "do NOT commit")?
   - F-H3 (Transition Maps): are VALID_PHASE_TRANSITIONS / VALID_SCENE_TRANSITIONS
     complete and consistent with the schema CHECK enums (phases; scene statuses)?
   - F-H4 (money): is the dollars-in / cents-stored convention now unambiguous across
     Input Validation, the money pattern, templates, and every model signature?
   - F-H5 (create_expense -> int | None): does every caller/route handle None? Does the
     department_budgets CHECK (spent_cents <= allocated_cents) still create a 500 path?
   - F-G1 (Orchestration Entrypoints): do the 10 rows satisfy the FC50 presence guard
     (Type == "orchestration entrypoint", non-empty Full Signature), and do the
     signatures match the Model Functions section character-for-character?

3. Resolve the one OPEN item — F-H6: crew + expenses department_head "own dept only"
   ownership is still prose, not code. Propose EXACT ownership-check code per route
   (the brainstorm notes VenueConnect had 5/8 P1s as IDOR). Or confirm the generic IDOR
   pattern + a route note is sufficient.

4. Plan Quality Gate: does the spec still answer — what's changing, what must NOT change,
   how we'll know it worked (EARS acceptance tests present), and the most likely way it's
   wrong? Flag any residual "we'll figure it out while coding."

Output:
  - Findings ordered by severity (P0/P1/P2), each naming the conflicting sections.
  - For each, classify: would the 9w.6 completeness gate or 9w.5 consistency gate catch
    it? (This feeds the hardening roadmap — gate-blind findings are the most valuable.)
  - An updated Claude Code fix prompt listing exactly what to change before launch.
