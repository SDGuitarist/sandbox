---
run_id: "050"
project: GigSheet
date: 2026-05-20
generated_by: swarm-planner
---

# GigSheet Run 050 -- Swarm Agent Assignment

## Validation Summary

- **Total agents:** 31
- **Total files:** 87
- **Duplicate file check:** No file appears in multiple assignments -- PASS
- **Absolute path check:** No path starts with `/` or contains `..` -- PASS
- **Blueprint Registry cross-check:** All 25 registered blueprints have a corresponding agent with `__init__.py` + `routes.py` -- PASS
- **Path anomaly noted:** Agent 31 (tests) uses path `gigsheet/test_smoke.py` while all other agents use paths relative to the `gigsheet/` project root directly (e.g., `app/`, `send_worker.py`). This matches the plan as written. If the working directory for agents IS `gigsheet/`, the correct path would be `test_smoke.py`. Flagged for orchestrator awareness -- does not block PASS.

---

## Shared Interface Spec

All agents must read and comply with the full shared interface spec in the plan at:
`docs/plans/2026-05-20-gigsheet-plan.md`

Key contracts every agent must honor:
- **Blueprint names and url_prefix values** from the Blueprint Registry (lines 164-275 of plan)
- **Model function signatures** -- call only functions listed in the Export Names Table; never write SQL directly to tables owned by another agent
- **Decorator guard chain** -- ALL routes (except auth) must use `@login_required` then `@require_workspace`; ownership check `abort(403)` when `workspace_id` mismatches
- **Commit discipline** -- functions marked "Does NOT commit" must not call `conn.commit()`; caller commits
- **Form field names** -- exact names from the Form Field Names table; no synonyms
- **Flash message categories** -- only `'success'`, `'error'`, `'info'`, `'warning'`
- **CSRF** -- every HTML form includes `{{ csrf_token() }}`; webhook blueprint is exempt via `csrf.exempt()`
- **Workspace isolation** -- every query on tenant-scoped tables includes `WHERE workspace_id = ?`

---

## Agent Assignments

### Agent 1: scaffold

**Files:**
- `app/__init__.py`
- `app/filters.py`
- `app/static/style.css`
- `app/static/app.js`
- `app/templates/base.html`
- `app/templates/404.html`
- `app/templates/500.html`
- `app/dashboard/__init__.py`
- `app/dashboard/routes.py`
- `app/templates/dashboard/index.html`
- `requirements.txt`
- `run.py`
- `.gitignore`

**Responsibility:** Creates the Flask app factory, registers all 25 blueprints, owns the dashboard blueprint and all top-level static/template infrastructure.

**Blueprint owned:** `dashboard` (url_prefix `/dashboard`)

---

### Agent 2: auth

**Files:**
- `app/auth/__init__.py`
- `app/auth/routes.py`
- `app/templates/auth/login.html`
- `app/templates/auth/register.html`
- `app/templates/auth/workspaces.html`

**Responsibility:** Implements user registration, login with scrypt password hashing, workspace creation and selection, and session management.

**Blueprint owned:** `auth` (url_prefix `/auth`)

---

### Agent 3: models

**Files:**
- `app/db.py`
- `app/models.py`
- `app/schema.sql`

**Responsibility:** Owns all database schema, connection management, and every model function (create/read/update/delete) for all tables; no other agent writes SQL to any shared table.

---

### Agent 4: decorators

**Files:**
- `app/decorators.py`

**Responsibility:** Implements `login_required`, `require_workspace`, and `require_role` decorators used by all route agents.

---

### Agent 5: lead-list

**Files:**
- `app/lead_list/__init__.py`
- `app/lead_list/routes.py`
- `app/templates/lead_list/index.html`

**Responsibility:** Paginated lead listing with stage/tag filtering and FTS5 search.

**Blueprint owned:** `lead_list` (url_prefix `/leads`)

---

### Agent 6: lead-crud

**Files:**
- `app/lead_detail/__init__.py`
- `app/lead_detail/routes.py`
- `app/templates/lead_detail/detail.html`
- `app/templates/lead_detail/form.html`

**Responsibility:** Create, read, update, and delete individual leads via the lead detail blueprint.

**Blueprint owned:** `lead_detail` (url_prefix `/lead`)

---

### Agent 7: lead-import

**Files:**
- `app/lead_import/__init__.py`
- `app/lead_import/routes.py`
- `app/templates/lead_import/index.html`
- `app/templates/lead_import/preview.html`

**Responsibility:** CSV upload, preview with formula-injection sanitization, and batch commit of lead imports.

**Blueprint owned:** `lead_import` (url_prefix `/import`)

---

### Agent 8: lead-tags

**Files:**
- `app/lead_tags/__init__.py`
- `app/lead_tags/routes.py`
- `app/templates/lead_tags/index.html`

**Responsibility:** Tag CRUD and tag assignment/removal on leads.

**Blueprint owned:** `lead_tags` (url_prefix `/tags`)

---

### Agent 9: template-list

**Files:**
- `app/template_list/__init__.py`
- `app/template_list/routes.py`
- `app/templates/template_list/index.html`

**Responsibility:** Lists all email templates in the workspace.

**Blueprint owned:** `template_list` (url_prefix `/templates`)

---

### Agent 10: template-editor

**Files:**
- `app/template_editor/__init__.py`
- `app/template_editor/routes.py`
- `app/templates/template_editor/detail.html`
- `app/templates/template_editor/form.html`

**Responsibility:** Create, edit, and delete email templates with merge field support.

**Blueprint owned:** `template_editor` (url_prefix `/template`)

---

### Agent 11: template-preview

**Files:**
- `app/template_preview/__init__.py`
- `app/template_preview/routes.py`

**Responsibility:** JSON API endpoints for live template preview rendering and test email sends.

**Blueprint owned:** `template_preview` (url_prefix `/preview`)

---

### Agent 12: campaign-list

**Files:**
- `app/campaign_list/__init__.py`
- `app/campaign_list/routes.py`
- `app/templates/campaign_list/index.html`

**Responsibility:** Lists all campaigns in the workspace with status indicators.

**Blueprint owned:** `campaign_list` (url_prefix `/campaigns`)

---

### Agent 13: campaign-editor

**Files:**
- `app/campaign_editor/__init__.py`
- `app/campaign_editor/routes.py`
- `app/templates/campaign_editor/detail.html`
- `app/templates/campaign_editor/form.html`

**Responsibility:** Create and edit campaigns, manage recipient lead lists.

**Blueprint owned:** `campaign_editor` (url_prefix `/campaign`)

---

### Agent 14: campaign-sender

**Files:**
- `app/campaign_sender/__init__.py`
- `app/campaign_sender/routes.py`
- `app/templates/campaign_sender/status.html`

**Responsibility:** Triggers campaign send by enqueuing jobs and shows real-time send status with SSE integration.

**Blueprint owned:** `campaign_sender` (url_prefix `/send`)

---

### Agent 15: campaign-scheduler

**Files:**
- `app/campaign_scheduler/__init__.py`
- `app/campaign_scheduler/routes.py`
- `app/templates/campaign_scheduler/view.html`

**Responsibility:** Schedule campaigns for future delivery and cancel scheduled campaigns.

**Blueprint owned:** `campaign_scheduler` (url_prefix `/schedule`)

---

### Agent 16: delivery-webhooks

**Files:**
- `app/delivery_webhooks/__init__.py`
- `app/delivery_webhooks/routes.py`

**Responsibility:** Receives SendGrid delivery event webhooks (CSRF-exempt, rate-limited at 100/min) and records email events.

**Blueprint owned:** `delivery_webhooks` (url_prefix `/webhooks`)

---

### Agent 17: delivery-stats

**Files:**
- `app/delivery_stats/__init__.py`
- `app/delivery_stats/routes.py`
- `app/templates/delivery_stats/detail.html`

**Responsibility:** Per-campaign delivery statistics detail view.

**Blueprint owned:** `delivery_stats` (url_prefix `/delivery`)

---

### Agent 18: delivery-dashboard

**Files:**
- `app/delivery_dashboard/__init__.py`
- `app/delivery_dashboard/routes.py`
- `app/templates/delivery_dashboard/index.html`

**Responsibility:** Aggregate delivery reporting dashboard with CSV export.

**Blueprint owned:** `delivery_dashboard` (url_prefix `/reports`)

---

### Agent 19: pipeline-board

**Files:**
- `app/pipeline_board/__init__.py`
- `app/pipeline_board/routes.py`
- `app/templates/pipeline_board/index.html`

**Responsibility:** Kanban board displaying leads grouped by pipeline stage.

**Blueprint owned:** `pipeline_board` (url_prefix `/pipeline`)

---

### Agent 20: pipeline-actions

**Files:**
- `app/pipeline_actions/__init__.py`
- `app/pipeline_actions/routes.py`

**Responsibility:** JSON API endpoints for moving leads between stages (single and bulk) and adding pipeline notes.

**Blueprint owned:** `pipeline_actions` (url_prefix `/pipeline/actions`)

---

### Agent 21: pipeline-detail

**Files:**
- `app/pipeline_detail/__init__.py`
- `app/pipeline_detail/routes.py`
- `app/templates/pipeline_detail/detail.html`

**Responsibility:** Lead detail view within pipeline context including notes and tags.

**Blueprint owned:** `pipeline_detail` (url_prefix `/pipeline/lead`)

---

### Agent 22: analytics-overview

**Files:**
- `app/analytics_overview/__init__.py`
- `app/analytics_overview/routes.py`
- `app/templates/analytics_overview/index.html`

**Responsibility:** Overall analytics dashboard with lead counts, campaign totals, and conversion funnel.

**Blueprint owned:** `analytics_overview` (url_prefix `/analytics`)

---

### Agent 23: analytics-campaigns

**Files:**
- `app/analytics_campaigns/__init__.py`
- `app/analytics_campaigns/routes.py`
- `app/templates/analytics_campaigns/detail.html`

**Responsibility:** Per-campaign analytics detail view showing open/click/bounce rates.

**Blueprint owned:** `analytics_campaigns` (url_prefix `/analytics/campaign`)

---

### Agent 24: workspace-settings

**Files:**
- `app/workspace_settings/__init__.py`
- `app/workspace_settings/routes.py`
- `app/templates/workspace_settings/index.html`

**Responsibility:** Workspace name, from_email, and from_name settings (owner/admin only).

**Blueprint owned:** `workspace_settings` (url_prefix `/workspace`)

---

### Agent 25: workspace-members

**Files:**
- `app/workspace_members/__init__.py`
- `app/workspace_members/routes.py`
- `app/templates/workspace_members/index.html`

**Responsibility:** Invite, remove, and change roles of workspace members.

**Blueprint owned:** `workspace_members` (url_prefix `/members`)

---

### Agent 26: email-queue

**Files:**
- `app/email_queue.py`
- `send_worker.py`

**Responsibility:** Email queue worker that polls job_queue, atomically claims jobs, calls sendgrid_client, and updates campaign_progress via models functions inside an app context.

---

### Agent 27: sendgrid-client

**Files:**
- `app/sendgrid_client.py`

**Responsibility:** Pure `send_email()` function supporting mock and live SendGrid modes; no DB writes.

---

### Agent 28: file-uploads

**Files:**
- `app/file_uploads/__init__.py`
- `app/file_uploads/routes.py`
- `app/templates/file_uploads/index.html`

**Responsibility:** Secure file upload with allowlist extension check, Content-Disposition attachment serving, and workspace-scoped storage.

**Blueprint owned:** `file_uploads` (url_prefix `/files`)

---

### Agent 29: sse-events

**Files:**
- `app/sse/__init__.py`
- `app/sse/routes.py`

**Responsibility:** Server-Sent Events endpoint that streams campaign send progress with heartbeat and 5-minute timeout.

**Blueprint owned:** `sse` (url_prefix `/sse`)

---

### Agent 30: seed

**Files:**
- `seed.py`

**Responsibility:** Database seeder that populates demo data for development and testing.

---

### Agent 31: tests

**Files:**
- `gigsheet/test_smoke.py`

**Responsibility:** Smoke test suite verifying all critical routes and the email send pipeline end-to-end.

**Path note:** This path (`gigsheet/test_smoke.py`) is prefixed with `gigsheet/`, which differs from all other agents whose paths are relative to the project root inside `gigsheet/`. If agents run with `gigsheet/` as cwd, this file should be at `test_smoke.py`. Orchestrator should confirm the correct working directory before launch.

---

## File Count by Agent

| Agent | Role | File Count |
|-------|------|-----------|
| 1 | scaffold | 13 |
| 2 | auth | 5 |
| 3 | models | 3 |
| 4 | decorators | 1 |
| 5 | lead-list | 3 |
| 6 | lead-crud | 4 |
| 7 | lead-import | 4 |
| 8 | lead-tags | 3 |
| 9 | template-list | 3 |
| 10 | template-editor | 4 |
| 11 | template-preview | 2 |
| 12 | campaign-list | 3 |
| 13 | campaign-editor | 4 |
| 14 | campaign-sender | 3 |
| 15 | campaign-scheduler | 3 |
| 16 | delivery-webhooks | 2 |
| 17 | delivery-stats | 3 |
| 18 | delivery-dashboard | 3 |
| 19 | pipeline-board | 3 |
| 20 | pipeline-actions | 2 |
| 21 | pipeline-detail | 3 |
| 22 | analytics-overview | 3 |
| 23 | analytics-campaigns | 3 |
| 24 | workspace-settings | 3 |
| 25 | workspace-members | 3 |
| 26 | email-queue | 2 |
| 27 | sendgrid-client | 1 |
| 28 | file-uploads | 3 |
| 29 | sse-events | 2 |
| 30 | seed | 1 |
| 31 | tests | 1 |
| **Total** | | **87** |

---

## Blueprint Registry Cross-Check

| Blueprint Name | url_prefix | Owning Agent | Routes File Present |
|---------------|------------|-------------|-------------------|
| auth | /auth | 2 (auth) | app/auth/routes.py |
| dashboard | /dashboard | 1 (scaffold) | app/dashboard/routes.py |
| lead_list | /leads | 5 (lead-list) | app/lead_list/routes.py |
| lead_detail | /lead | 6 (lead-crud) | app/lead_detail/routes.py |
| lead_import | /import | 7 (lead-import) | app/lead_import/routes.py |
| lead_tags | /tags | 8 (lead-tags) | app/lead_tags/routes.py |
| template_list | /templates | 9 (template-list) | app/template_list/routes.py |
| template_editor | /template | 10 (template-editor) | app/template_editor/routes.py |
| template_preview | /preview | 11 (template-preview) | app/template_preview/routes.py |
| campaign_list | /campaigns | 12 (campaign-list) | app/campaign_list/routes.py |
| campaign_editor | /campaign | 13 (campaign-editor) | app/campaign_editor/routes.py |
| campaign_sender | /send | 14 (campaign-sender) | app/campaign_sender/routes.py |
| campaign_scheduler | /schedule | 15 (campaign-scheduler) | app/campaign_scheduler/routes.py |
| delivery_webhooks | /webhooks | 16 (delivery-webhooks) | app/delivery_webhooks/routes.py |
| delivery_stats | /delivery | 17 (delivery-stats) | app/delivery_stats/routes.py |
| delivery_dashboard | /reports | 18 (delivery-dashboard) | app/delivery_dashboard/routes.py |
| pipeline_board | /pipeline | 19 (pipeline-board) | app/pipeline_board/routes.py |
| pipeline_actions | /pipeline/actions | 20 (pipeline-actions) | app/pipeline_actions/routes.py |
| pipeline_detail | /pipeline/lead | 21 (pipeline-detail) | app/pipeline_detail/routes.py |
| analytics_overview | /analytics | 22 (analytics-overview) | app/analytics_overview/routes.py |
| analytics_campaigns | /analytics/campaign | 23 (analytics-campaigns) | app/analytics_campaigns/routes.py |
| workspace_settings | /workspace | 24 (workspace-settings) | app/workspace_settings/routes.py |
| workspace_members | /members | 25 (workspace-members) | app/workspace_members/routes.py |
| file_uploads | /files | 28 (file-uploads) | app/file_uploads/routes.py |
| sse | /sse | 29 (sse-events) | app/sse/routes.py |

All 25 blueprints from the Blueprint Registry are covered. PASS.

---

STATUS: PASS
