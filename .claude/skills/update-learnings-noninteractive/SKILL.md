---
name: update-learnings-noninteractive
description: Non-interactive learnings propagation for autopilot use. Runs Steps 0-6 of update-learnings without the code-explainer prompt. Sandbox-local.
argument-hint: "[solution doc path, or leave blank to auto-detect]"
allowed-tools: Read Edit Write Glob Grep Bash Agent
---

# Update Learnings (Non-Interactive)

Sandbox-local variant of the global `/update-learnings` command. Runs the
same 7 propagation steps but omits the interactive code-explainer question
at the end. Used by the autopilot skill for unattended runs.

**Why this exists:** The global `/update-learnings` Step 7 asks "Want to
run code-explainer?" which is interactive. In autopilot context, this
competes with the "do not stop between steps" instruction and produces
non-deterministic behavior. See: docs/reports/spike-update-learnings-noninteractive.md

**Duplication note:** Steps 0-6 below are duplicated from
`~/.claude/commands/update-learnings.md`. This is deliberate technical debt
for sandbox isolation. If the global command adds new propagation targets,
this file must be updated to match.

## Arguments

<update_target> #$ARGUMENTS </update_target>

Parse arguments:
- If a path is given, use it as the solution doc
- If blank, find the most recently modified file in `docs/solutions/`

## Step 0: Load Context

- Read the solution doc (the one just written in Compound step 1)
- Read the review summary (from `docs/reviews/<branch>/REVIEW-SUMMARY.md`)
- Read the plan (from `docs/plans/` -- find via solution doc's `related_prs` or most recent)
- Identify the current project name from the nearest `CLAUDE.md` or directory name
- Get today's date for journal entries

Extract from these sources:
- **Key patterns** established (for patterns memory + LESSONS_LEARNED)
- **Workflow lessons** -- things that went well, things to watch (for workflow memory)
- **Risk chain** -- what was flagged, what happened, what was learned (for compound-engineering.local.md)
- **Project state** -- cycle number, branch, test count, what's next (for HANDOFF + MEMORY)
- **Review stats** -- finding counts, top issues, agent consensus (for journal)

## Step 1: Update LESSONS_LEARNED.md

**Location:** `~/Documents/dev-notes/LESSONS_LEARNED.md`

Cumulative, cross-project lessons file. Create it if it doesn't exist.

### Format

```markdown
# Lessons Learned

Cumulative lessons from compound engineering cycles across all projects.
Last updated: [date]

## Code Patterns

### [Pattern Name] -- [Project] Cycle N
- **Context:** [when this applies]
- **Lesson:** [one sentence]
- **Source:** [solution doc path]

## Workflow & Process

### [Lesson Name] -- [Project] Cycle N
- **Context:** [when this applies]
- **Lesson:** [one sentence]
- **Source:** [solution doc path]

## Review Insights

### [Insight] -- [Project] Cycle N
- **Context:** [when this applies]
- **Lesson:** [one sentence]
- **Source:** [review summary path]
```

### Rules
- Append under the appropriate section heading
- Each lesson is 3 lines max (context, lesson, source)
- Do NOT duplicate -- check existing entries first
- Cross-project lessons use the project name as a tag

## Step 2: Update compound-engineering.local.md

**Location:** `[project root]/compound-engineering.local.md`

Replace the entire contents with the latest risk chain state.

### Format

```markdown
# Review Context -- [Project Name]

## Risk Chain

**Brainstorm risk:** [from brainstorm Feed-Forward "least confident"]

**Plan mitigation:** [how the plan addressed it]

**Work risk (from Feed-Forward):** [from plan/work Feed-Forward]

**Review resolution:** [what the review found -- counts + top findings]

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| [file] | [what changed this cycle] | [why it's risky] |

## Plan Reference

`[path to current plan]`
```

### Rules
- FULL REPLACE -- not an append
- List files that changed in the most recent cycle only
- Risk chain traces from brainstorm -> plan -> work -> review

## Step 3: Update Auto-Memory Files

**Location:** `~/.claude/projects/[project-key]/memory/`

Update three files:

### MEMORY.md
- Update `## Project State` with current cycle, branch, PR status, what's next
- Add `## Cycle N Implementation Notes` section
- Keep concise -- MEMORY.md truncates after 200 lines

### workflow.md
- Append to `## Things That Went Well` and `## Things to Watch`
- Do NOT duplicate existing entries

### patterns.md
- Add new code patterns established in this cycle
- Update existing pattern sections if refined
- Do NOT duplicate existing entries

### Rules
- Read each file BEFORE editing
- Check for duplicates before appending
- Keep entries concise (one line per lesson/pattern)

## Step 4: Update HANDOFF.md

**Location:** `[project root]/HANDOFF.md`

FULL REPLACE with the latest project state.

### Format

```markdown
# HANDOFF -- [Project Name]

**Date:** [today]
**Branch:** [current branch]
**Phase:** [current phase status]

## Current State

[2-3 sentences: what was just completed, what's the project status]

## Key Artifacts

| Phase | Location |
|-------|----------|
| Brainstorm | [path] |
| Plan | [path] |
| Review | [path] |
| Solution | [path] |

## Review Fixes Pending

[If review found issues not yet fixed, list the top 3-5 with priority]

## Deferred Items

[Items explicitly deferred to future cycles from the plan or review]

## Three Questions

1. **Hardest decision?** [from solution doc Feed-Forward]
2. **What was rejected?** [from solution doc Feed-Forward]
3. **Least confident about?** [from solution doc Feed-Forward]

## Prompt for Next Session

```
Read HANDOFF.md for context. This is [Project], a [one-line description].
[Current state]. [What to do next].
```
```

### Rules
- FULL REPLACE -- not an append
- Three Questions come from the solution doc's Feed-Forward section
- The "Prompt for Next Session" should be copy-pasteable

## Step 5: Append Journal Entry

**Location:** `~/Documents/dev-notes/YYYY-MM-DD.md` (today's date)

Append a cycle summary entry. Factual summary, not a story analogy.

### Format

```markdown
## [Project] -- Cycle N Complete: [Feature Name]

- **Built:** [one sentence: what was built]
- **Review findings:** [count] unique ([P1 count] P1, [P2 count] P2, [P3 count] P3) from [agent count] agents. Top finding: [top issue].
- **Top lesson:** [one sentence: most important lesson]
- **Risk chain:** [one sentence: what was flagged -> what happened -> outcome]
- **What's next:** [one sentence: immediate next step]
```

### Rules
- Read the file first -- append, never overwrite
- Keep to exactly 5 bullet points
- No story analogies

## Step 6: Update Agent Pitfalls

**Location:** `~/.claude/docs/agent-pitfalls.md`

Cumulative failure pattern registry. Must be updated after every reviewed build.

### Process

1. Read `~/.claude/docs/agent-pitfalls.md`
2. Read the solution doc's review findings
3. For each review finding:
   - **If it matches an existing failure class:** Add the build to that class's "Builds hit" list.
   - **If it is a NEW pattern:** Add a new failure class:
     ```
     ## Failure Class N: [Name]

     **Frequency:** [when this happens]
     **Builds hit:** [this build]

     **What happens:** [description]

     **Agent rule:**
     > [the rule agents must follow]
     ```
4. Check **Per-Agent-Type Pitfalls** section. Add role-specific rules if applicable.
5. Append a row to the **Update Log** table.

### Rules
- Do NOT duplicate existing failure classes
- New failure classes must have a concrete "Agent rule" block
- Keep Update Log entries to one line
- If zero novel findings, still update "Builds hit" and add Update Log entry

## Step 7: Final Summary (NO INTERACTIVE PROMPT)

After ALL six updates are complete, print a summary:

```markdown
## Learnings Propagated

| Target | Status |
|--------|--------|
| LESSONS_LEARNED.md | Updated -- N new entries |
| compound-engineering.local.md | Replaced -- risk chain from Cycle N |
| MEMORY.md | Updated -- project state + cycle notes |
| workflow.md | Updated -- N new lessons |
| patterns.md | Updated -- N new patterns |
| HANDOFF.md | Replaced -- ready for next session |
| Journal (YYYY-MM-DD.md) | Appended -- cycle summary |
| agent-pitfalls.md | Updated -- N new failure classes, M per-agent rules |
```

**Stop here. Do not ask any questions. Do not offer code-explainer.
This is the non-interactive variant -- propagation is complete.**

## Important Rules

1. **No prompts at any step** -- everything is fully automated, including the ending
2. **Read before write** -- always read a file before editing it
3. **Check for duplicates** -- before appending to workflow.md, patterns.md, or agent-pitfalls.md
4. **FULL REPLACE vs APPEND** -- compound-engineering.local.md and HANDOFF.md are full replacements. Everything else is append/edit.
5. **Solution doc is the source of truth** -- all lessons flow FROM the solution doc and review summary
6. **If a target file doesn't exist, create it**
7. **agent-pitfalls.md is mandatory** -- skipping it is FC11
