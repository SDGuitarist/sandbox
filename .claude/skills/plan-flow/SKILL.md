---
name: plan-flow
description: Full plan workflow -- create plan, deepen with research, self-review, then generate Codex review handoff. Chains workflows:plan -> deepen-plan -> refine -> codex handoff.
argument-hint: "[feature description or brainstorm path]"
user-invocable: true
---

# Plan Flow -- Full Plan Pipeline

This skill chains the entire plan lifecycle into one invocation:

1. **Create** the plan (`/workflows:plan`)
2. **Deepen** with parallel research (`/compound-engineering:deepen-plan`)
3. **Self-review & refine** against quality gates
4. **Generate Codex handoff** -- the script command + return fix prompt

## Arguments

<feature> $ARGUMENTS </feature>

## Step 1: Create the Plan

Run the `/compound-engineering:workflows:plan` skill with the feature description or brainstorm path from the arguments.

Wait for it to complete. Note the output plan file path (should be in `docs/plans/`).

## Step 2: Deepen the Plan

Run the `/compound-engineering:deepen-plan` skill, passing the plan file path from Step 1.

This launches parallel research agents to add depth, best practices, edge cases, and implementation details to every section.

Wait for it to complete. The plan file is updated in place.

## Step 3: Self-Review and Refine

After deepening, review the plan yourself against these quality gates. Fix any issues directly in the plan file.

### Quality Gate Checklist
- [ ] **What exactly is changing?** -- Clear and specific, not vague
- [ ] **What must not change?** -- Explicitly listed
- [ ] **How will we know it worked?** -- EARS acceptance tests present with verification commands
- [ ] **Most likely way this plan is wrong?** -- Honest self-assessment, not a throwaway line

### EARS Acceptance Tests
- [ ] Happy path tests exist
- [ ] Error case tests exist
- [ ] Each test uses `WHEN [condition] THE SYSTEM SHALL [behavior]` format
- [ ] Verification commands are included (curl, npm test, etc.)

### Feed-Forward Section
- [ ] `## Feed-Forward` section exists at the end
- [ ] **Hardest decision** is named with reasoning
- [ ] **Rejected alternatives** are listed with why they lost
- [ ] **Least confident** identifies the real remaining uncertainty
- [ ] `feed_forward:` YAML frontmatter has `risk:` and `verify_first:` fields

### Plan Quality
- [ ] No section says "we'll figure that out while coding"
- [ ] No scope creep beyond the brainstorm
- [ ] Implementation details are concrete enough to code from
- [ ] File paths and function names are specified where possible

**Fix any failing checks directly in the plan.** Don't just note them -- resolve them.

## Step 4: Generate Codex Handoff

After self-review is complete, generate two outputs:

### 4a. Codex Review Command

Output the exact command the user should run:

```
--- CODEX REVIEW COMMAND ---

./scripts/plan-review.sh docs/plans/[PLAN_FILE].md --output docs/plans/[PLAN_FILE]-codex-review.md
```

### 4b. Return Fix Prompt

Output a copy-paste-ready prompt that the user will give back to Claude Code after Codex finishes. This prompt tells Claude Code how to apply Codex's findings:

```
--- RETURN FIX PROMPT (paste this back to Claude Code after Codex review) ---

Read the Codex review at docs/plans/[PLAN_FILE]-codex-review.md.
Read the plan at docs/plans/[PLAN_FILE].md.

For each item in the review:

**Blockers:** Fix these in the plan immediately. These must be resolved before work starts.

**Concerns:** Evaluate each one. If valid, update the plan. If not applicable, add a brief note in the Feed-Forward explaining why.

**Suggestions:** Apply the ones that improve the plan without adding scope. Skip any that are scope creep.

**Open Questions:** If you can answer them from context, add the answer to the plan. If they need human input, add them to Feed-Forward "least confident" or as a callout box in the relevant section.

After applying fixes:
1. Re-check the Quality Gate (4 questions)
2. Re-check EARS acceptance tests
3. Update the Feed-Forward section if any decisions changed
4. Report what you changed and any items you intentionally skipped (with reasoning)
```

## Output Format

```
PLAN FLOW COMPLETE

Plan file: docs/plans/[PLAN_FILE].md
Status: Deepened + self-reviewed

--- CODEX REVIEW COMMAND ---
./scripts/plan-review.sh docs/plans/[PLAN_FILE].md --output docs/plans/[PLAN_FILE]-codex-review.md

--- RETURN FIX PROMPT (paste back after Codex review) ---
[the return fix prompt above, fully filled in]
```

## Rules

- Every bracket `[PLAN_FILE]` must be filled in with the actual filename. No placeholders in the final output.
- The self-review in Step 3 must actually fix problems, not just list them.
- If the plan is missing EARS tests or Feed-Forward, write them -- don't just flag the gap.
- The Codex review prompt at `scripts/prompts/plan-review.md` is already customized for our quality gates. Don't duplicate that logic in the handoff.
