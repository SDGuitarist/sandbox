"""Ownership gate: verify each agent only touched assigned files."""
import subprocess
import json

AGENTS = {
    "worktree-agent-a6338d84": {
        "name": "scaffold",
        "files": ["gigsheet/app/__init__.py", "gigsheet/app/filters.py", "gigsheet/app/static/style.css",
                  "gigsheet/app/static/app.js", "gigsheet/app/templates/base.html",
                  "gigsheet/app/templates/404.html", "gigsheet/app/templates/500.html",
                  "gigsheet/app/dashboard/__init__.py", "gigsheet/app/dashboard/routes.py",
                  "gigsheet/app/templates/dashboard/index.html", "gigsheet/requirements.txt",
                  "gigsheet/run.py", "gigsheet/.gitignore"]
    },
    "worktree-agent-a63c2c55": {
        "name": "auth",
        "files": ["gigsheet/app/auth/__init__.py", "gigsheet/app/auth/routes.py",
                  "gigsheet/app/templates/auth/login.html", "gigsheet/app/templates/auth/register.html",
                  "gigsheet/app/templates/auth/workspaces.html"]
    },
    "worktree-agent-a2427b8a": {
        "name": "models",
        "files": ["gigsheet/app/db.py", "gigsheet/app/models.py", "gigsheet/app/schema.sql",
                  "gigsheet/app/__init__.py"]
    },
    "worktree-agent-a2b49aae": {
        "name": "decorators",
        "files": ["gigsheet/app/decorators.py"]
    },
    "worktree-agent-a89c1bb7": {
        "name": "lead-list",
        "files": ["gigsheet/app/lead_list/__init__.py", "gigsheet/app/lead_list/routes.py",
                  "gigsheet/app/templates/lead_list/index.html"]
    },
    "worktree-agent-a9690e0b": {
        "name": "lead-crud",
        "files": ["gigsheet/app/lead_detail/__init__.py", "gigsheet/app/lead_detail/routes.py",
                  "gigsheet/app/templates/lead_detail/detail.html", "gigsheet/app/templates/lead_detail/form.html"]
    },
    "worktree-agent-aafc0788": {
        "name": "lead-import",
        "files": ["gigsheet/app/lead_import/__init__.py", "gigsheet/app/lead_import/routes.py",
                  "gigsheet/app/templates/lead_import/index.html", "gigsheet/app/templates/lead_import/preview.html"]
    },
    "worktree-agent-a782599d": {
        "name": "lead-tags",
        "files": ["gigsheet/app/lead_tags/__init__.py", "gigsheet/app/lead_tags/routes.py",
                  "gigsheet/app/templates/lead_tags/index.html"]
    },
    "worktree-agent-a9509c97": {
        "name": "template-list",
        "files": ["gigsheet/app/template_list/__init__.py", "gigsheet/app/template_list/routes.py",
                  "gigsheet/app/templates/template_list/index.html"]
    },
    "worktree-agent-a21f5d56": {
        "name": "template-editor",
        "files": ["gigsheet/app/template_editor/__init__.py", "gigsheet/app/template_editor/routes.py",
                  "gigsheet/app/templates/template_editor/detail.html", "gigsheet/app/templates/template_editor/form.html"]
    },
    "worktree-agent-a7c7d1ec": {
        "name": "template-preview",
        "files": ["gigsheet/app/template_preview/__init__.py", "gigsheet/app/template_preview/routes.py"]
    },
    "worktree-agent-aa472d18": {
        "name": "campaign-list",
        "files": ["gigsheet/app/campaign_list/__init__.py", "gigsheet/app/campaign_list/routes.py",
                  "gigsheet/app/templates/campaign_list/index.html"]
    },
    "worktree-agent-a2d0e6b9": {
        "name": "campaign-editor",
        "files": ["gigsheet/app/campaign_editor/__init__.py", "gigsheet/app/campaign_editor/routes.py",
                  "gigsheet/app/templates/campaign_editor/detail.html", "gigsheet/app/templates/campaign_editor/form.html"]
    },
    "worktree-agent-ab20c8f8": {
        "name": "campaign-sender",
        "files": ["gigsheet/app/campaign_sender/__init__.py", "gigsheet/app/campaign_sender/routes.py",
                  "gigsheet/app/templates/campaign_sender/status.html"]
    },
    "worktree-agent-a7c0ba7e": {
        "name": "campaign-scheduler",
        "files": ["gigsheet/app/campaign_scheduler/__init__.py", "gigsheet/app/campaign_scheduler/routes.py",
                  "gigsheet/app/templates/campaign_scheduler/view.html"]
    },
    "worktree-agent-a7391acb": {
        "name": "delivery-webhooks",
        "files": ["gigsheet/app/delivery_webhooks/__init__.py", "gigsheet/app/delivery_webhooks/routes.py"]
    },
    "worktree-agent-ab28120e": {
        "name": "delivery-stats",
        "files": ["gigsheet/app/delivery_stats/__init__.py", "gigsheet/app/delivery_stats/routes.py",
                  "gigsheet/app/templates/delivery_stats/detail.html"]
    },
    "worktree-agent-a05b2194": {
        "name": "delivery-dashboard",
        "files": ["gigsheet/app/delivery_dashboard/__init__.py", "gigsheet/app/delivery_dashboard/routes.py",
                  "gigsheet/app/templates/delivery_dashboard/index.html"]
    },
    "worktree-agent-a86eb7e5": {
        "name": "pipeline-board",
        "files": ["gigsheet/app/pipeline_board/__init__.py", "gigsheet/app/pipeline_board/routes.py",
                  "gigsheet/app/templates/pipeline_board/index.html"]
    },
    "worktree-agent-ab71d287": {
        "name": "pipeline-actions",
        "files": ["gigsheet/app/pipeline_actions/__init__.py", "gigsheet/app/pipeline_actions/routes.py"]
    },
    "worktree-agent-ad584648": {
        "name": "pipeline-detail",
        "files": ["gigsheet/app/pipeline_detail/__init__.py", "gigsheet/app/pipeline_detail/routes.py",
                  "gigsheet/app/templates/pipeline_detail/detail.html"]
    },
    "worktree-agent-ac337dd3": {
        "name": "analytics-overview",
        "files": ["gigsheet/app/analytics_overview/__init__.py", "gigsheet/app/analytics_overview/routes.py",
                  "gigsheet/app/templates/analytics_overview/index.html"]
    },
    "worktree-agent-a228326d": {
        "name": "analytics-campaigns",
        "files": ["gigsheet/app/analytics_campaigns/__init__.py", "gigsheet/app/analytics_campaigns/routes.py",
                  "gigsheet/app/templates/analytics_campaigns/detail.html"]
    },
    "worktree-agent-a526a854": {
        "name": "workspace-settings",
        "files": ["gigsheet/app/workspace_settings/__init__.py", "gigsheet/app/workspace_settings/routes.py",
                  "gigsheet/app/templates/workspace_settings/index.html"]
    },
    "worktree-agent-ab684082": {
        "name": "workspace-members",
        "files": ["gigsheet/app/workspace_members/__init__.py", "gigsheet/app/workspace_members/routes.py",
                  "gigsheet/app/templates/workspace_members/index.html"]
    },
    "worktree-agent-adfcb775": {
        "name": "email-queue",
        "files": ["gigsheet/app/email_queue.py", "gigsheet/send_worker.py"]
    },
    "worktree-agent-ab559a1a": {
        "name": "sendgrid-client",
        "files": ["gigsheet/app/sendgrid_client.py"]
    },
    "worktree-agent-ae72a676": {
        "name": "file-uploads",
        "files": ["gigsheet/app/file_uploads/__init__.py", "gigsheet/app/file_uploads/routes.py",
                  "gigsheet/app/templates/file_uploads/index.html"]
    },
    "worktree-agent-a8182d0c": {
        "name": "sse-events",
        "files": ["gigsheet/app/sse/__init__.py", "gigsheet/app/sse/routes.py"]
    },
    "worktree-agent-a296eb73": {
        "name": "seed",
        "files": ["gigsheet/seed.py"]
    },
    "worktree-agent-a29a25e1": {
        "name": "tests",
        "files": ["gigsheet/test_smoke.py"]
    },
}

violations = []
passed = 0

for branch, info in AGENTS.items():
    result = subprocess.run(
        ["git", "-C", "/Users/alejandroguillen/Projects/sandbox",
         "diff", "--name-only", f"master...{branch}"],
        capture_output=True, text=True
    )
    actual_files = set(result.stdout.strip().split("\n")) if result.stdout.strip() else set()
    allowed_files = set(info["files"])

    extra = actual_files - allowed_files
    if extra:
        violations.append(f"VIOLATION: {info['name']} ({branch}) modified: {extra}")
    else:
        passed += 1

print(f"OWNERSHIP GATE: {passed}/{len(AGENTS)} agents passed")
if violations:
    print("STATUS: FAIL")
    for v in violations:
        print(v)
else:
    print("STATUS: PASS")
    print("All 31 agents only modified their assigned files.")
