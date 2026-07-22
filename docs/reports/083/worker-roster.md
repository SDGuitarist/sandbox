# Worker Roster — run 083

## Wave 0 — shared surface (spawned 2026-07-22, background worktree opus)
| Role | Agent ID | Branch | Owned files |
|------|----------|--------|-------------|
| scaffold | aa1d652c8a811fa57 | worktree-agent-aa1d652c8a811fa57 | swarmlimit/__init__.py |
| database | ad3ab04aeaa23692d | worktree-agent-ad3ab04aeaa23692d | swarmlimit/database.py, swarmlimit/schema.sql |
| auth-core | adfec57fe6a0a6728 | worktree-agent-adfec57fe6a0a6728 | swarmlimit/auth.py, swarmlimit/models/auth_models.py, swarmlimit/routes/auth.py |
| shared-services | a905cae6a376734d2 | worktree-agent-a905cae6a376734d2 | swarmlimit/refs.py, swarmlimit/models/audit_models.py |
| smoke-author | a54ed07dde1369a1c | worktree-agent-a54ed07dde1369a1c | swarmlimit/smoke.py, docs/reports/083/planned-manifest.json, docs/reports/083/pitfalls-baseline.txt |

## Wave 1 — MODEL layer (spawned 2026-07-22, background worktree opus; base origin/master c0c87ba)
| Role | Agent ID | Branch | Owned file |
|------|----------|--------|------------|
| supplier | ae679e548fff9a0d5 | worktree-agent-ae679e548fff9a0d5 | swarmlimit/models/supplier_models.py |
| category | ad0b52225cfd98b70 | worktree-agent-ad0b52225cfd98b70 | swarmlimit/models/category_models.py |
| product | a160ff0ec6f5cf999 | worktree-agent-a160ff0ec6f5cf999 | swarmlimit/models/product_models.py |
| order | aefd048d35f5e5027 | worktree-agent-aefd048d35f5e5027 | swarmlimit/models/order_models.py |
| shipment | a7d9d30c44fc0f4a3 | worktree-agent-a7d9d30c44fc0f4a3 | swarmlimit/models/shipment_models.py |
| return | ab10c73543a26882e | worktree-agent-ab10c73543a26882e | swarmlimit/models/return_models.py |
| payment | ac62202d4d67d13e8 | worktree-agent-ac62202d4d67d13e8 | swarmlimit/models/payment_models.py |

## Wave 2 — routes (NOT yet spawned): suppliers, categories, products, orders, shipments, returns, payments → swarmlimit/routes/<r>.py

## Wave 0 status: MERGED + pushed to origin/master (c0c87ba). 5 worker worktrees lingering (cleanup deferred to teardown). Assembly-fixes: H3, H6.

Firebreak ACTIVE (run=083, phase=build). Workers root on origin/master (76b63ac). Wave mechanic: merge wave→feat, FF push feat→origin/master, re-verify provenance, then next wave.
