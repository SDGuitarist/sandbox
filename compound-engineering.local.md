# Review Context — Sandbox (Flask Swarm Acid Test)

## Risk Chain

**Brainstorm risk:** "Whether Python imports between blueprints will cause
mismatches that CSS class/ID matching in JS didn't. In JS, agents just need to
agree on string names. In Python, agents need to agree on import paths, function
signatures, AND the app factory's blueprint registration order."

**Plan mitigation:** Prescriptive code blocks for all `__init__.py` files,
exact blueprint variable names, deferred imports inside `create_app()` to
prevent circular imports. Template Render Context section (150+ lines) defining
exact `render_template()` keyword arguments.

**Work risk (from Feed-Forward):** Context manager usage gap — spec said
`@contextmanager` but didn't show `with` syntax. All 3 agents made the same
bare-assignment mistake.

**Review resolution:** 0 interface mismatches. All 7 checkpoints passed.
Context manager fix applied post-assembly (zero-risk — changed acquisition
pattern, not queries). Codex review found validation + input preservation
issues, fixed in commit 3ad4c20.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| task-tracker/app/db.py | get_db() context manager | Connection lifecycle |
| task-tracker/app/__init__.py | Blueprint registration order | Circular imports |
| task-tracker/app/blueprints/*/routes.py | with get_db() usage (post-fix) | Context manager pattern |
| task-tracker/app/templates/layout.html | Flash messages, block definitions | Silent Jinja2 mismatches |

## Plan Reference

`docs/plans/2026-04-07-feat-flask-swarm-acid-test-plan.md`
