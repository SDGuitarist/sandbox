# Worker Roster — run 070

16-agent Film Production PM swarm. Worktree branches are named
`worktree-agent-<agentId>` (not by role). Assembly base / cherry-pick base /
ownership-gate base = `original_branch` feat/film-production-pm; worktree root =
master HEAD f90aed8 (now an ancestor of feat → merge-base == worktree-root, O3 invariant).

| Role | Agent ID | Branch | Files |
|------|----------|--------|-------|
| scaffold | a302d3a67f062ebc5 | worktree-agent-a302d3a67f062ebc5 | app/__init__.py, app/templates/base.html, app/static/css/style.css, app/static/js/app.js, run.py, requirements.txt, .gitignore |
| database | aae91ded44476f398 | worktree-agent-aae91ded44476f398 | schema.sql, app/database.py, app/models/__init__.py |
| auth | af1a829ae14ac159e | worktree-agent-af1a829ae14ac159e | app/blueprints/auth/{__init__,routes}.py, app/models/auth_models.py, app/templates/auth/{login,register}.html |
| projects | aadbe19a09071a389 | worktree-agent-aadbe19a09071a389 | app/blueprints/projects/{__init__,routes}.py, app/models/project_models.py, app/templates/projects/{dashboard,new,edit}.html |
| scenes | aa67c73a2a3e19580 | worktree-agent-aa67c73a2a3e19580 | app/blueprints/scenes/{__init__,routes}.py, app/models/scene_models.py, app/templates/scenes/{list,new,detail,edit}.html |
| cast | a4a36f27d0259cece | worktree-agent-a4a36f27d0259cece | app/blueprints/cast/{__init__,routes}.py, app/models/cast_models.py, app/templates/cast/{list,new,detail}.html |
| crew | a1877f25a7893064f | worktree-agent-a1877f25a7893064f | app/blueprints/crew/{__init__,routes}.py, app/models/crew_models.py, app/templates/crew/{list,new,detail}.html |
| departments | a0f32752b37007cd8 | worktree-agent-a0f32752b37007cd8 | app/blueprints/departments/{__init__,routes}.py, app/models/department_models.py, app/templates/departments/{list,detail}.html |
| locations | a2d260703e00b5a3a | worktree-agent-a2d260703e00b5a3a | app/blueprints/locations/{__init__,routes}.py, app/models/location_models.py, app/templates/locations/{list,new,detail}.html |
| schedule | a8137dfc63c6a8848 | worktree-agent-a8137dfc63c6a8848 | app/blueprints/schedule/{__init__,routes}.py, app/models/schedule_models.py, app/templates/schedule/{index,day,new}.html, app/static/js/schedule.js |
| callsheets | a81b79a516c80263f | worktree-agent-a81b79a516c80263f | app/blueprints/callsheets/{__init__,routes}.py, app/models/callsheet_models.py, app/templates/callsheets/{list,detail}.html |
| budget | a133e6d95a5bfdd7a | worktree-agent-a133e6d95a5bfdd7a | app/blueprints/budget/{__init__,routes}.py, app/models/budget_models.py, app/templates/budget/{index,top_sheet,new_line_item}.html |
| expenses | a33563627cea14a2f | worktree-agent-a33563627cea14a2f | app/blueprints/expenses/{__init__,routes}.py, app/models/expense_models.py, app/templates/expenses/{list,new}.html |
| reports | a7e4e1e5df3144173 | worktree-agent-a7e4e1e5df3144173 | app/blueprints/reports/{__init__,routes}.py, app/models/report_models.py, app/templates/reports/{index,budget_summary,dood,progress}.html |
| search | afad6083e5f3706cc | worktree-agent-afad6083e5f3706cc | app/blueprints/search/{__init__,routes}.py, app/models/search_models.py, app/templates/search/results.html |
| tests | aaafec6c02456dd3f | worktree-agent-aaafec6c02456dd3f | test_smoke.py, tests/{__init__,test_critical_flows,conftest}.py |
