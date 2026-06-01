# Codex Review: Client Intake Dashboard -- Autopilot Brief

**Date:** 2026-05-22
**Phase:** Pre-Build Review (before autopilot launch)
**Repo:** ~/Projects/sandbox
**Reviewer:** Codex

## What I Need From You

Review this autopilot brief for completeness, contradictions, and missing requirements BEFORE I launch an unattended swarm build. This app is revenue-serving (powers the $500 Audit tier), so the spec needs to be tighter than a generic CRUD test app.

## The Brief

**Client Intake Dashboard** -- A Flask web app for managing client intake assessments. A potential client fills out an intake form (business type, current workflows, pain points, tools used, goals). The system stores submissions, lets the admin review them, generates a simple bottleneck assessment report, and tracks status (new, reviewed, audit-scheduled, completed). Powers the $500 Audit tier of the Amplify AI consulting business.

## Business Context

- **Who uses it:** Alex (admin) reviews submissions. Potential clients (public) fill out the intake form.
- **Revenue tier:** $500 Audit. After a workshop, interested attendees get a link to the intake form. Alex reviews their answers, generates a bottleneck assessment, and schedules a paid audit call.
- **Flow:** Workshop attendee -> intake form link -> fills out form -> Alex reviews -> generates assessment -> schedules audit -> $500 engagement
- **Stack:** Flask + SQLite + Jinja2 templates + Bootstrap (standard sandbox pattern)
- **Auth:** Admin-only login for the review dashboard. Public intake form requires no auth.

## Review Questions

1. **Is the brief complete enough for a swarm of 15-25 agents to build from?** What's missing that would cause agents to guess or contradict each other?

2. **Intake form fields** -- I listed "business type, current workflows, pain points, tools used, goals." Are these sufficient for generating a useful bottleneck assessment? What fields are missing?

3. **Bottleneck assessment report** -- I said "generates a simple bottleneck assessment report." This is vague. What should the report actually contain? Is it a template with filled-in fields, a scored rubric, free-text notes, or something else?

4. **Status workflow** -- I listed 4 statuses: new, reviewed, audit-scheduled, completed. Is this the right set? Should there be "archived" or "declined"?

5. **Public form security** -- The intake form is public-facing. What protections does the brief need to specify? (rate limiting, CSRF, honeypot spam prevention, etc.)

6. **Missing features** -- Are there obvious features a $500 Audit tool needs that the brief doesn't mention? (e.g., email notifications, PDF export of assessment, notes/comments on submissions, intake form customization)

7. **Contradictions or ambiguities** -- Anything in the brief that two agents could interpret differently?

## Constraints (Don't Review These -- They're Handled by the Pipeline)

- Swarm orchestration, agent count, and assembly merge (autopilot skill handles this)
- Spec format and mandatory sections (spec-completeness-checker validates these)
- Bash command rules and permission handling (CLAUDE.md enforces these)
- Solution doc generation (compound phase handles this)

## What to Return

A numbered list of findings, each tagged:
- **P0** -- Brief is broken, will cause build failure or incoherent app
- **P1** -- Missing requirement that will need a post-build fix
- **P2** -- Nice-to-have improvement to the brief

Keep it concrete. "The report section is vague" is not helpful. "The report section needs to specify: template structure, which intake fields map to which report sections, and whether it's editable after generation" is helpful.
