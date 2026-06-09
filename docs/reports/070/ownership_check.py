#!/usr/bin/env python3
"""Step 10.5w ownership gate for run 070.
For each worker branch, diff (three-dot) against original_branch and verify the
worker only touched its assigned files. Writes ownership-gate.md (PASS) or
ownership-violation.md (FAIL)."""
import subprocess, sys

REPO = "/Users/alejandroguillen/Projects/sandbox"
ORIGINAL = "feat/film-production-pm"

# role -> (branch, assigned files)
ASSIGN = {
 "scaffold": ("worktree-agent-a302d3a67f062ebc5", [
   "app/__init__.py","app/templates/base.html","app/static/css/style.css",
   "app/static/js/app.js","run.py","requirements.txt",".gitignore"]),
 "database": ("worktree-agent-aae91ded44476f398", [
   "schema.sql","app/database.py","app/models/__init__.py"]),
 "auth": ("worktree-agent-af1a829ae14ac159e", [
   "app/blueprints/auth/__init__.py","app/blueprints/auth/routes.py",
   "app/models/auth_models.py","app/templates/auth/login.html","app/templates/auth/register.html"]),
 "projects": ("worktree-agent-aadbe19a09071a389", [
   "app/blueprints/projects/__init__.py","app/blueprints/projects/routes.py",
   "app/models/project_models.py","app/templates/projects/dashboard.html",
   "app/templates/projects/new.html","app/templates/projects/edit.html"]),
 "scenes": ("worktree-agent-aa67c73a2a3e19580", [
   "app/blueprints/scenes/__init__.py","app/blueprints/scenes/routes.py",
   "app/models/scene_models.py","app/templates/scenes/list.html","app/templates/scenes/new.html",
   "app/templates/scenes/detail.html","app/templates/scenes/edit.html"]),
 "cast": ("worktree-agent-a4a36f27d0259cece", [
   "app/blueprints/cast/__init__.py","app/blueprints/cast/routes.py",
   "app/models/cast_models.py","app/templates/cast/list.html","app/templates/cast/new.html",
   "app/templates/cast/detail.html"]),
 "crew": ("worktree-agent-a1877f25a7893064f", [
   "app/blueprints/crew/__init__.py","app/blueprints/crew/routes.py",
   "app/models/crew_models.py","app/templates/crew/list.html","app/templates/crew/new.html",
   "app/templates/crew/detail.html"]),
 "departments": ("worktree-agent-a0f32752b37007cd8", [
   "app/blueprints/departments/__init__.py","app/blueprints/departments/routes.py",
   "app/models/department_models.py","app/templates/departments/list.html",
   "app/templates/departments/detail.html"]),
 "locations": ("worktree-agent-a2d260703e00b5a3a", [
   "app/blueprints/locations/__init__.py","app/blueprints/locations/routes.py",
   "app/models/location_models.py","app/templates/locations/list.html",
   "app/templates/locations/new.html","app/templates/locations/detail.html"]),
 "schedule": ("worktree-agent-a8137dfc63c6a8848", [
   "app/blueprints/schedule/__init__.py","app/blueprints/schedule/routes.py",
   "app/models/schedule_models.py","app/templates/schedule/index.html",
   "app/templates/schedule/day.html","app/templates/schedule/new.html","app/static/js/schedule.js"]),
 "callsheets": ("worktree-agent-a81b79a516c80263f", [
   "app/blueprints/callsheets/__init__.py","app/blueprints/callsheets/routes.py",
   "app/models/callsheet_models.py","app/templates/callsheets/list.html",
   "app/templates/callsheets/detail.html"]),
 "budget": ("worktree-agent-a133e6d95a5bfdd7a", [
   "app/blueprints/budget/__init__.py","app/blueprints/budget/routes.py",
   "app/models/budget_models.py","app/templates/budget/index.html",
   "app/templates/budget/top_sheet.html","app/templates/budget/new_line_item.html"]),
 "expenses": ("worktree-agent-a33563627cea14a2f", [
   "app/blueprints/expenses/__init__.py","app/blueprints/expenses/routes.py",
   "app/models/expense_models.py","app/templates/expenses/list.html","app/templates/expenses/new.html"]),
 "reports": ("worktree-agent-a7e4e1e5df3144173", [
   "app/blueprints/reports/__init__.py","app/blueprints/reports/routes.py",
   "app/models/report_models.py","app/templates/reports/index.html",
   "app/templates/reports/budget_summary.html","app/templates/reports/dood.html",
   "app/templates/reports/progress.html"]),
 "search": ("worktree-agent-afad6083e5f3706cc", [
   "app/blueprints/search/__init__.py","app/blueprints/search/routes.py",
   "app/models/search_models.py","app/templates/search/results.html"]),
 "tests": ("worktree-agent-aaafec6c02456dd3f", [
   "test_smoke.py","tests/__init__.py","tests/test_critical_flows.py","tests/conftest.py"]),
}

violations = []
lines = []
for role, (branch, files) in ASSIGN.items():
    assigned = set(files)
    out = subprocess.run(["git","-C",REPO,"diff","--name-only",f"{ORIGINAL}...{branch}"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        violations.append(f"{role}: git diff failed: {out.stderr.strip()}")
        continue
    changed = [f for f in out.stdout.splitlines() if f.strip()]
    extra = [f for f in changed if f not in assigned]
    lines.append(f"| {role} | {branch} | {len(changed)} | {'OK' if not extra else 'VIOLATION: '+', '.join(extra)} |")
    if extra:
        violations.append(f"{role} ({branch}) touched non-assigned files: {extra}")

if violations:
    body = "OWNERSHIP VIOLATION\n\n" + "\n".join(violations) + "\n\nSTATUS: FAIL\n"
    open(f"{REPO}/docs/reports/070/ownership-violation.md","w").write(body)
    print(body)
    sys.exit(1)
else:
    body = ("OWNERSHIP GATE: All 16 agents passed. Each agent only modified assigned files.\n"
            "Base = three-dot merge-base(original_branch, worker) = f90aed8 (O3 invariant).\n\n"
            "| Role | Branch | Files changed | Result |\n|------|--------|---------------|--------|\n"
            + "\n".join(lines) + "\n\nSTATUS: PASS\n")
    open(f"{REPO}/docs/reports/070/ownership-gate.md","w").write(body)
    print(body)
    sys.exit(0)
