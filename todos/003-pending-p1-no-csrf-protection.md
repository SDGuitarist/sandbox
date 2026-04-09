---
status: resolved
priority: p1
issue_id: "003"
tags: [code-review, security, flask]
dependencies: ["004"]
unblocks: []
sub_priority: 3
---

# No CSRF Protection on Flask Forms

## Problem Statement

The task-tracker-categories Flask app has no CSRF protection. Every POST
route (create/update/delete for projects and tasks) is vulnerable to
cross-site request forgery. No `flask-wtf` CSRFProtect, no CSRF tokens
in any template.

**Impact:** Any page on the internet could craft a form that silently
creates, modifies, or deletes projects and tasks when visited by a user.

## Findings

- **Security Sentinel (P1):** "An attacker could craft a page that silently
  creates, modifies, or deletes projects and tasks on their behalf.
  Exploitability: Trivial."
- Note: This is a sandbox demo app, but the pattern should be correct since
  swarm agents will replicate it in future builds.

## Proposed Solutions

### Option A: Add flask-wtf CSRFProtect
1. `pip install flask-wtf` + add to requirements.txt
2. `CSRFProtect(app)` in create_app()
3. Add `{{ csrf_token() }}` to every form template
- Pros: Standard Flask pattern, prevents CSRF
- Cons: Requires SECRET_KEY fix first (003 depends on 004)
- Effort: Small
- Risk: None

## Technical Details

**Affected files:**
- `task-tracker-categories/requirements.txt`
- `task-tracker-categories/app/__init__.py`
- `task-tracker-categories/app/templates/projects/form.html`
- `task-tracker-categories/app/templates/tasks/form.html`
- `task-tracker-categories/app/templates/projects/detail.html` (delete form)

## Acceptance Criteria

- [ ] All POST forms include CSRF token
- [ ] CSRFProtect is initialized in app factory
- [ ] Requests without valid CSRF token return 400

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-09 | Security review finding | Add CSRF to spec template for future Flask swarms |
