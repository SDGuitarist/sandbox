---
title: "Agent Guardrails: Deadline-First Throughput and Production DB Safety"
date: 2026-05-09
category: operations
tags: [agents, claude-code, codex, throughput, deadline, db-safety, migrations, review-bottleneck]
module: CLAUDE.md, run.py, db.py, docs
symptom: "Agents spent days making careful local improvements while production DB risk remained high and lead throughput stayed too low for the workshop deadline"
root_cause: "Agents optimized for component correctness and incremental fixes without first evaluating deadline-feasible throughput, manual review burden, or production DB blast radius"
---

# Agent Guardrails: Deadline-First Throughput and Production DB Safety

## Problem

Two different failure patterns stalled the lead-scraper for over a week:

1. **Production DB incidents.** The same SQLite database was wiped multiple times through concurrent access, migration debugging, and tests touching production state.
2. **Throughput-blind workflow design.** Agents built or followed workflows that were locally careful but operationally useless. Hours of work moved only a handful of leads toward sending while the workshop deadline kept approaching.

These were not isolated bugs. They were reasoning failures at the operating level:

- treating production like a normal local file
- treating one-by-one review as acceptable without doing the math
- optimizing for verification quality while ignoring campaign feasibility
- recognizing bottlenecks only after spending time inside them

## Key Decisions

### 1. Deadline and throughput are first-class constraints

The workshop date is **May 30, 2026**. Any proposed flow must be evaluated against that deadline before implementation starts.

**Rule:** A workflow is wrong if it cannot materially improve send volume before the deadline, even if the workflow is technically elegant or locally safer.

Required intake before helping:

1. Deadline
2. Throughput target
3. Current lead / sendable count
4. Current bottleneck
5. Manual review burden

This is now encoded in `CLAUDE.md`.

### 2. Manual-review math must happen before workflow work

The most expensive miss in this repo was allowing a design where most leads hit a manual review path, then only later realizing that this made the system unusable at scale.

**Rule:** Before recommending any gate, review queue, or approval process, estimate:

- leads processed per hour
- percent of leads that hit manual review
- total manual touches required
- whether the queue can be cleared before the deadline

If the process requires one-by-one review for a large share of leads, call it **not feasible** up front.

### 3. Production data is a protected asset, not a default file

The production DB cannot be treated like a scratch file for tests, debug commands, or migration validation.

**Rule:** Any ambiguous command that might touch production is unsafe until proven otherwise.

Operational consequences:

- tests must never touch production
- migration debugging must happen on `/tmp` copies
- destructive schema changes must be explicit
- write-heavy commands must take locks and backups
- health checks must detect missing, empty, or collapsed DB state

These protections now exist in `db.py` and `run.py`.

### 4. Natural language must be a planner, not an improvising executor

Free-form NL execution is too risky for this repo. It can hide assumptions, skip throughput math, or wander into dangerous paths.

**Rule:** Natural language is allowed only when it translates into known safe actions with preview, confirmation, audit, and execution boundaries.

Current implementation:

- allowlisted `nl` command
- config overrides instead of code edits
- preview mode
- audit log

### 5. Escalate early when a careful process is killing momentum

One of the biggest misses was staying inside a low-throughput process rather than naming it as the main problem.

**Rule:** Escalate immediately when:

- manual review becomes the dominant path
- more than 20% of leads are expected to hit a slow manual branch
- hours of work move only trivial numbers of leads forward
- a quality gate improves local correctness while destroying volume

The right agent behavior is not “continue carefully.” It is “say plainly that this path will miss the deadline.”

## What Went Wrong

| Failure mode | What happened | What should have happened |
|-------------|---------------|---------------------------|
| Production DB treated as a normal dev target | Tests and migration verification touched real data | Copy to `/tmp`, validate there, protect prod by construction |
| Migration logic too close to normal startup | Every CLI invocation could trigger dangerous schema code | Detect drift on startup, require explicit migration command |
| Manual review queue treated as acceptable | Leads accumulated in `needs_review` with no throughput math | Stop early and call the workflow infeasible |
| Late bottleneck recognition | Agent noticed the problem only after hours of work | Compute manual burden and deadline fit before building the flow |
| NL convenience without operating boundaries | Natural language could have encouraged unsafe improvisation | Restrict NL to allowlisted plans with preview and audit |

## Prevention Strategies (Ranked by ROI)

1. **Do the throughput math first.** Before workflow work, estimate volume, manual touches, and deadline fit. This catches dead-end processes early.
2. **Treat production as opt-in, never default.** Temp DBs and `/tmp` copies for all tests, debug sessions, and migration verification.
3. **Fail closed on dangerous ambiguity.** If a path might touch production or create a large manual queue, stop and escalate.
4. **Keep NL behind structured executors.** Preview, confirmation, validation, and audit reduce hidden assumptions.
5. **Log and snapshot operational state.** Backups, DB health snapshots, and audit logs turn “mysterious wipe” into diagnosable failure.

## Required Agent Checklist

Before proposing a high-impact workflow or code change, answer:

1. What is the bottleneck?
2. Is the current process deadline-feasible?
3. How many manual touches does this add?
4. What percent of leads hit the slow path?
5. If this goes wrong, does it cost time, money, or workshop viability?
6. Is there a lower-precision but much higher-throughput option that is more appropriate right now?

If these questions are not answered, the agent is not ready to help.

## Repo Changes That Encode These Lessons

- `CLAUDE.md` now forces deadline/throughput intake and escalation rules.
- `CODEX-HANDOFF-THROUGHPUT-GUARDRAILS.md` repeats the same constraints for future sessions.
- `db.py` now blocks unsafe production access patterns and runs DB health checks.
- `run.py` now routes common operations through locked, backed-up workflows and a restricted `nl` interface.

## Related Solution Docs

- `2026-05-05-init-db-wipes-data.md` -- root lessons from the repeated SQLite incidents
- `2026-05-06-reliability-hardening.md` -- examples of simplifying toward the real bug instead of building abstractions too early

## Feed-Forward

- **Hardest decision:** Whether to frame this as a model-quality problem or an operating-rules problem. Chose operating rules. Model quality matters, but the recurring damage came from letting agents act without hard deadline and production constraints.
- **Rejected alternatives:** (1) “Trust better prompting alone.” Too weak; prompts get ignored under pressure. (2) “Ban agent autonomy entirely.” Too expensive; the repo still benefits from agents, but only with explicit boundaries. (3) “Solve just the DB safety issue.” Incomplete, because the throughput-blind workflow design was independently killing momentum.
- **Least confident:** The 20% slow-path escalation threshold is intentionally blunt. It is a good forcing function today, but it may need tuning once the workshop pressure is gone and the system has better automation coverage.
