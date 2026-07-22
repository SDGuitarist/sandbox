# Worker Roster — run 083

## Wave 0 — shared surface (spawned 2026-07-22, background worktree opus)
| Role | Agent ID | Branch | Owned files |
|------|----------|--------|-------------|
| scaffold | aa1d652c8a811fa57 | worktree-agent-aa1d652c8a811fa57 | swarmlimit/__init__.py |
| database | ad3ab04aeaa23692d | worktree-agent-ad3ab04aeaa23692d | swarmlimit/database.py, swarmlimit/schema.sql |
| auth-core | adfec57fe6a0a6728 | worktree-agent-adfec57fe6a0a6728 | swarmlimit/auth.py, swarmlimit/models/auth_models.py, swarmlimit/routes/auth.py |
| shared-services | a905cae6a376734d2 | worktree-agent-a905cae6a376734d2 | swarmlimit/refs.py, swarmlimit/models/audit_models.py |
| smoke-author | a54ed07dde1369a1c | worktree-agent-a54ed07dde1369a1c | swarmlimit/smoke.py, docs/reports/083/planned-manifest.json, docs/reports/083/pitfalls-baseline.txt |

## Wave 1 — models (NOT yet spawned): supplier, category, product, order, shipment, return, payment → swarmlimit/models/<r>_models.py
## Wave 2 — routes (NOT yet spawned): suppliers, categories, products, orders, shipments, returns, payments → swarmlimit/routes/<r>.py

Firebreak ACTIVE (run=083, phase=build). Workers root on origin/master (76b63ac). Wave mechanic: merge wave→feat, FF push feat→origin/master, re-verify provenance, then next wave.
