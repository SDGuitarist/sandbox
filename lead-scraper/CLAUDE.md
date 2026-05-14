# Lead Scraper Operating Rules

This file is for any coding agent working on this repo, especially Claude Code.

Read this before proposing solutions, changing code, or running commands.

## Mission-Critical Context

- The workshop is on **May 30, 2026**.
- The user needs a large enough lead pipeline to promote it successfully.
- The database currently has far fewer qualified leads than needed.
- Momentum has already been lost for over a week due to low-throughput workflows and production DB incidents.

This is not a normal coding task. This repo is tied to a deadline with real business risk.

## Top-Level Goal

Optimize for **workshop-feasible throughput**, not local elegance.

Any solution that is careful but too slow to materially improve outreach volume before **May 30, 2026** is the wrong solution.

## Mandatory Intake Gate

Before assisting, planning, or implementing, you must explicitly understand and restate:

1. **Deadline**
   - The relevant deadline is **May 30, 2026**.

2. **Throughput target**
   - How many leads, approved messages, or sends are needed to make the workshop viable?

3. **Current state**
   - Current lead count
   - Current approved/sendable count if relevant
   - Current bottleneck

4. **Manual labor constraint**
   - How many human review touches does the proposed workflow require?

5. **Failure mode**
   - What happens if most leads hit the slow path?

If you cannot answer these, stop and reason about them before proceeding.

## Throughput Rules

You must do the math before recommending or implementing any workflow change.

For any proposed review/gate/send process, estimate:

- leads processed per hour
- manual approvals required
- expected percentage that hit manual review
- total time to clear the queue
- whether that is feasible before **May 30, 2026**

If a workflow requires one-by-one review for hundreds or thousands of leads, call it out as **not feasible** before doing any work.

If a workflow processes only a handful of leads after significant effort, treat that as a system failure, not incremental progress.

## Escalation Rules

You must escalate immediately instead of continuing normally when any of these are true:

- A proposed workflow introduces a manual bottleneck that will not scale before the deadline.
- More than 20% of leads are expected to hit a manual-only slow path.
- A review flow would require the user to approve leads one by one at scale.
- A quality gate improves local precision while destroying campaign throughput.
- The system has spent significant time and moved only a trivial number of leads toward sending.

When escalating, say plainly that the workflow is not viable at deadline scale and recommend the higher-throughput alternative.

## Do Not Optimize For The Wrong Thing

Do not prioritize:

- perfect verification over usable volume
- elegant review queues over campaign feasibility
- component correctness over end-to-end throughput
- extra gating layers that create operator bottlenecks

Do prioritize:

- removing bottlenecks
- reducing manual review load
- batch-safe operations
- high-confidence automation where manual review is not feasible
- identifying the single constraint that most limits outreach volume

## Production DB Rules

The production SQLite database is fragile and high-stakes.

Non-negotiable rules:

- Never run tests against the production DB.
- Never run experiments against the production DB.
- Never use production for migration debugging.
- Never run concurrent processes against `leads.db`.
- Always use `/tmp` copies or temp DBs for validation.
- Treat any destructive migration or schema rewrite as a separate, explicit operation.

If there is any ambiguity about whether a command might touch production, assume it is unsafe and stop.

## Required Reasoning Pattern For Workflow Changes

Before recommending a change to scraping, enrichment, gating, approval, or sending, explicitly evaluate:

1. **Throughput**
   - Can this process handle the required volume before the deadline?

2. **Human labor**
   - How many manual touches does this create?

3. **Slow path**
   - What percentage of leads hit the slow path?

4. **Business consequence**
   - If this is wrong, does it cost time, money, or workshop viability?

5. **Best alternative**
   - Is there a lower-precision but much higher-throughput option that is more appropriate for the deadline?

## Required Response Behavior

For any high-impact operational request, begin by identifying:

- the bottleneck
- whether the current process is deadline-feasible
- the cheapest way to regain momentum

Do not jump straight into implementation details without first checking whether the proposed path is strategically viable.

## Anti-Pattern To Avoid

This is the failure pattern that must not repeat:

1. Build or follow a thoughtful process.
2. Spend hours moving only a few leads forward.
3. Realize too late that the process cannot scale.
4. Recommend the obvious throughput fix only after momentum is already lost.

If you see this pattern forming, stop and change direction immediately.
