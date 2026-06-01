Read HANDOFF.md. This is the Sandbox project.

Build a standalone Flask + SQLite + Jinja2 app called Client Intake Dashboard
as a 15-25 agent autopilot-swarm build.

This app supports the $500 Audit tier of the Amplify AI consulting business.

Business flow:
- a public workshop attendee receives an intake form link
- they submit business and workflow information
- Alex reviews the submission in an admin dashboard
- Alex creates or edits a bottleneck assessment
- Alex decides whether to schedule a paid audit call

Users:
- public user: can submit the intake form only
- admin user: can log in, review submissions, add notes, create/edit
  assessments, and update status

Stack and constraints:
- Flask
- SQLite
- Jinja2 templates
- Bootstrap
- standard sandbox app patterns
- admin-only login for dashboard routes
- public intake form requires no login

Public intake form fields:
- contact name
- email
- business name
- business type / industry
- team size
- current workflows
- main pain points
- tools currently used
- goals / desired outcomes
- urgency / timeline
- optional notes from submitter

Assessment model:
- each submission has at most one admin assessment
- assessment is admin-editable
- assessment is stored in the database and visible in the dashboard
- do not assume AI generation unless the plan can justify it simply

Assessment structure:
1. summary
2. current-state bottlenecks
3. likely root causes
4. recommended next steps
5. audit-fit recommendation
6. internal admin notes

Status workflow:
- `new`
- `reviewed`
- `assessment-ready`
- `audit-scheduled`
- `completed`
- `declined`
- `archived`

Status rules:
- `declined`, `completed`, and `archived` are terminal
- admin changes status manually
- public users never see status

Required admin features:
- submissions list view
- submission detail view
- internal notes
- create/edit assessment
- status update controls
- filter by status
- mark whether the lead is a fit for the $500 audit

Public-form security requirements:
- CSRF protection
- server-side validation on all fields
- input length caps
- email validation
- rate limiting
- honeypot spam field
- admin-only protection on all dashboard, assessment, and status routes

Out of scope unless the planner can justify them as trivial:
- payment processing
- calendar integration
- automatic email sending
- PDF export
- multi-admin collaboration
- client self-service editing after submit

Intent:
- this is an intake + assessment + status-tracking MVP
- it is not a full CRM
- it is not a scheduling system
- it is not a payment system

Success bar:
- the build implements the intake workflow, assessment workflow, and status
  workflow consistently
- the public form is protected with the required security controls
- review does not find major ambiguity-driven divergence in assessment
  structure or status handling
