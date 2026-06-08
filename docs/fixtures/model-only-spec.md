# Fixture: Model-Only Spec (FC50 — expect N/A)

Purpose: a minimal shared interface spec with only noun classes (model functions,
endpoints) and ZERO `orchestration entrypoint` rows. The 9w.6 completeness gate's
Check 1b (orchestration entrypoint signature presence guard) MUST return **N/A**
— the guard checks only what IS declared and never invents entrypoint rows.

Expected checker result: **Orchestration Entrypoints (FC50): N/A** (0 entrypoint
rows). Export Names itself should PASS (both identifiers are listed).

## Export Names Table

| Name | Type | Defined By | Used By | Full Signature |
|------|------|------------|---------|----------------|
| `create_item` | model function | `app/models.py` | `items` agent | — |
| `items.list` | endpoint | `app/blueprints/items/routes.py` | `layout` agent (navbar) | — |

## Cross-Boundary Wiring Table

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| `app/models.py` | `app/blueprints/items/routes.py` | `from app.models import create_item` |
