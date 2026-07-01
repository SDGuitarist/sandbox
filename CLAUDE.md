# Sandbox Operating Contract

This is the root contract for all agents and sessions in this repo.

## Autonomy Classes

Three execution modes are allowed in this project:

- **manual** -- Human-driven session. Claude assists interactively. All decisions require human approval.
- **autopilot-solo** -- Unattended single-agent build. The autopilot skill runs the full compound loop without human input. Requires `dangerouslySkipPermissions: true` in `.claude/settings.local.json`.
- **autopilot-swarm** -- Unattended multi-agent build. The autopilot skill spawns parallel worker agents via worktrees. Same prerequisites as solo, plus plan frontmatter `swarm: true`.

## Forbidden Actions

These apply to all autonomy classes:

- No production database access. Sandbox apps use local SQLite or dev-only Supabase projects.
- No `git push --force` or `git reset --hard` without human confirmation.
- No destructive history rewrites (`git rebase` on published commits, `git filter-repo`, `git filter-branch`, amending pushed commits) without human confirmation.
- No external API calls without explicit declaration in the plan or spec.
- No edits to files outside `~/Projects/sandbox/` except during learnings propagation (see below).
- No deleting solution docs, prior run reports, or BUILD_TRACKING files.

**Allowed out-of-repo writes (learnings propagation only):**
These files are written by `/update-learnings-noninteractive` (autopilot) or `/update-learnings` (manual) during the compound phase tail:
- `~/.claude/docs/agent-pitfalls.md` -- cross-project failure registry (append-only)
- `~/Documents/dev-notes/LESSONS_LEARNED.md` -- cumulative cross-project lessons
- `~/Documents/dev-notes/YYYY-MM-DD.md` -- daily journal entry (append-only)
- `~/.claude/projects/[project-key]/memory/MEMORY.md` -- auto-memory project state
- `~/.claude/projects/[project-key]/memory/workflow.md` -- workflow lessons
- `~/.claude/projects/[project-key]/memory/patterns.md` -- code patterns

## Build Namespace Convention (MANDATORY — prevents ghost-file collisions)

Every autopilot build MUST write its application code under its **own top-level
directory** named for the build (e.g. `shelftrack/`, `gigsheet/`) — **never** the
shared top-level `app/` namespace.

**Why:** worker worktrees root on `master`, so any tracked top-level dir a build
writes is inherited by every future build's workers. A build that writes into a shared
`app/` collides with the next build's `app/` (run 070's film-PM `app/models/` package
shadowed run 080 ShelfTrack's `app/models.py` → import landmine, and blocked the run at
the 9w.9 ghost-file gate). Per-build namespacing makes prior builds inert clutter, not
blockers. (`/app/` is now gitignored; film-PM's files remain on disk, recovery tag
`archive/pre-hygiene-2026-07-01`.)

The 9w.9 ghost-file cleanup step enforces this: if the plan's file assignments target a
top-level dir already tracked on `master` from a prior build, re-namespace under the
build's own dir before spawning workers.

## Required Artifacts

Every completed autopilot run must produce:

1. **BUILD_TRACKING.md** -- Copied from `~/.claude/docs/autopilot-tracking-template.md` at run start. Must contain filled AGENT_STATUS, FAILURES, and RUN_METRICS sections at run end.
2. **Solution doc** -- Written during the compound phase to `docs/solutions/` with YAML frontmatter.
3. **Learnings propagation** -- `/update-learnings-noninteractive` (autopilot) or `/update-learnings` (manual) must run and produce the "Learnings Propagated" summary table. Agent-pitfalls Update Log must have an entry for today's build.
4. **HANDOFF.md** -- Updated with current project state, key artifacts, and next-session prompt.
5. **Self-audit report** -- Written by the self-audit-reviewer agent to `docs/reports/<run-id>/self-audit.md`. Must include: final run status, WARN disposition table (every WARN disposed), "What Was Missed" analysis, skeptical reviewer Q&A, promotion decisions, and Run Quality Grade (6 dimensions scored 1-5 with artifact-backed evidence). Every DEFERRED disposition must have a matching HANDOFF.md entry.

Missing any of these artifacts fails the run.

## Mandatory Spec Coverage Sections (Swarm Plans)

Every swarm plan's shared interface spec must include these 6 sections.
The spec-completeness-checker (Step 9w.6) validates they exist and are
complete. Missing sections FAIL the pre-swarm gate.

1. **Export Names Table** -- every model function, endpoint name (url_for target),
   blueprint name, route path, and **orchestration entrypoint** that crosses agent
   boundaries. Orchestration entrypoints (FC50) are every route→non-model function
   call and tool→constants import crossing an agent/cluster boundary, listed with
   `Type = orchestration entrypoint`. Columns: Name, Type, Defined By, Used By,
   Full Signature. (The checker validates these 5 classes; for `orchestration
   entrypoint` rows it additionally FAILs on an empty Full Signature -- the FC50
   presence guard. Template filenames and form field names should also be listed
   but are not yet machine-checked.)
2. **Cross-Boundary Wiring Table** -- every cross-module function call with
   producer file, consumer file, and import path.
3. **Input Validation Prescriptions** -- every POST/PUT/PATCH/DELETE route and typed URL param
   with prescribed validation and error response. Columns: Route, Input,
   Validation, Error Response.
4. **Coordinated Behaviors** -- blueprint registration, navbar links, role maps,
   flash message patterns, and any other behavior that must be consistent
   across agents.
5. **Transaction Contracts** -- every model function that writes to the DB
   annotated with: "commits internally", "does NOT commit", or "requires
   BEGIN IMMEDIATE". Can be a dedicated section or a column in model tables.
6. **Authorization Matrix** -- every auth-protected route with mode: public,
   role-only, role+ownership (with field), or admin-only.

Sections 1, 2, and 4 already exist in most specs. Sections 3, 5, and 6 are new.

## Production Safety

- Never run migration or initialization code against real user data. Copy to `/tmp` first.
- DB safety rules from `~/.claude/CLAUDE.md` apply here (four prior data loss incidents).
- No deadline pressure overrides safety checks.

## Escalation Rules

- If a swarm agent's ownership gate fails, abort that agent's merge and report.
- If smoke tests fail after one retry, continue to review with the failure noted.
- If the spec contract check fails after one retry, abort the pipeline.
- If any mandatory tail artifact is missing, fail the run -- do not silently succeed.
- If the self-audit report has undisposed WARNs or claims PIPELINE_PASS with deferred risks, fail the run.
- If the self-audit report claims an A quality grade while DEFERRED WARNs carry HIGH severity, the justification must contain `HIGH` and every such WARN's key. Gate 7f checks each DEFERRED+HIGH WARN independently and fails on the first missing key.

## Review Expectations

- Every build goes through `/workflows:review` before compound.
- Review agents should scrutinize areas flagged in the plan's Feed-Forward "least confident" item.
- Learnings Researcher is the highest-ROI review agent. Solution doc violations are always P1.

## Control Surface Scope

Not all autonomy controls live in this repo. Know what is local and what is global:

**Project-local (this repo owns these):**
- `.claude/settings.local.json` -- project permissions
- `.claude/skills/` -- autopilot, resolve-todos, and any future skills
- `.claude/agents/` -- swarm, verification, and self-audit agents
- `.claude/agent-memory/` -- per-agent persistent state
- This file (`CLAUDE.md`) -- operating contract

**Global (owned by `~/.claude/`, not editable from this repo):**
- `~/.claude/commands/update-learnings.md` -- learnings propagation command (never modified; sandbox uses a local non-interactive variant)
- `~/.claude/hooks/` -- feed-forward check, commit-size guard, phase-doc naming, etc.
- `~/.claude/settings.json` -- base permissions and hook definitions
- `~/.claude/docs/agent-pitfalls.md` -- cross-project failure registry (append-only from this repo)
- `~/.claude/docs/autopilot-tracking-template.md` -- BUILD_TRACKING template

**Written during learnings propagation (cross-project by design):**
- `~/Documents/dev-notes/LESSONS_LEARNED.md`, `~/Documents/dev-notes/YYYY-MM-DD.md`
- `~/.claude/projects/[project-key]/memory/` (MEMORY.md, workflow.md, patterns.md)

## Bash Command Rules

Security heuristics fire above `dangerouslySkipPermissions`. One command per Bash call. Always.

Forbidden patterns (from compound-bash-instruction-refactor solution doc):
1. `cd /path && command` -- use `git -C /path` or full paths
2. `source .venv/bin/activate` -- use full path: `.venv/bin/pip`
3. `for x in ...; do ... done` -- use multiple individual Bash calls
4. `python3 -c "code"` -- use Write tool to create .py file, then run it
5. `&&` or `;` to chain commands -- one command per call
