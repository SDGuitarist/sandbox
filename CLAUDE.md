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

## Required Artifacts

Every completed autopilot run must produce:

1. **BUILD_TRACKING.md** -- Copied from `~/.claude/docs/autopilot-tracking-template.md` at run start. Must contain filled AGENT_STATUS, FAILURES, and RUN_METRICS sections at run end.
2. **Solution doc** -- Written during the compound phase to `docs/solutions/` with YAML frontmatter.
3. **Learnings propagation** -- `/update-learnings-noninteractive` (autopilot) or `/update-learnings` (manual) must run and produce the "Learnings Propagated" summary table. Agent-pitfalls Update Log must have an entry for today's build.
4. **HANDOFF.md** -- Updated with current project state, key artifacts, and next-session prompt.

Missing any of these artifacts fails the run.

## Production Safety

- Never run migration or initialization code against real user data. Copy to `/tmp` first.
- DB safety rules from `~/.claude/CLAUDE.md` apply here (four prior data loss incidents).
- No deadline pressure overrides safety checks.

## Escalation Rules

- If a swarm agent's ownership gate fails, abort that agent's merge and report.
- If smoke tests fail after one retry, continue to review with the failure noted.
- If the spec contract check fails after one retry, abort the pipeline.
- If any mandatory tail artifact is missing, fail the run -- do not silently succeed.

## Review Expectations

- Every build goes through `/workflows:review` before compound.
- Review agents should scrutinize areas flagged in the plan's Feed-Forward "least confident" item.
- Learnings Researcher is the highest-ROI review agent. Solution doc violations are always P1.

## Control Surface Scope

Not all autonomy controls live in this repo. Know what is local and what is global:

**Project-local (this repo owns these):**
- `.claude/settings.local.json` -- project permissions
- `.claude/skills/` -- autopilot, resolve-todos, and any future skills
- `.claude/agents/` -- swarm and verification agents
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
