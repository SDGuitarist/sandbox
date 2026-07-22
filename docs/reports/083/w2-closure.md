# 083-W2 CLOSURE — Path-B --case atomicity evidence captured post-teardown

**Status:** CLOSED (2026-07-22, same session, post-firebreak-teardown).

083-W2 (self-audit HIGH DEFERRED) flagged that the atomicity-rollback claim ("all 10 Path-B EARS
cases green incl. rollbacks") had NO on-disk artifact — the C2 run used `--manifest` mode, which is
mutually exclusive with `--case` (smoke.py), so the `_TX_FAULT` rollback cases never executed there.
The disconfirmer (D1) caught this correctly.

**Closure:** after Step-18w firebreak teardown, all 10 Path-B `--case` proofs were run LIVE
(firebreak off — the FC62 "keep the dynamic surface lit" discipline) and captured to
`docs/reports/083/case-suite-output.txt`. Result: **10/10 --case PASS + plain full suite PASS
(10 path-b cases + 11 core cases)**. Every case exited 0, including:
- `process-return-rollback` — the 4-table atomic ROLLBACK via `return_models._TX_FAULT` (asserts
  COUNT(returns)/COUNT(payments) unchanged AND shipment status VALUE still 'delivered' AND product
  stock VALUES unchanged). **This is the feed-forward risk's load-bearing proof** — the densest
  cross-agent write (process_return reaching into 3 other agents' tables) rolls back atomically.
- `process-return-guard-refund`, `process-return-guard-shipment` — pre-write guards (409, zero writes).
- `state-machine-illegal` (3 sub-checks), `soft-delete-order`, `uniqueness-collision`.

**Effect on the run:** the feed-forward risk resolution is now ARTIFACT-BACKED, not narrative. The
self-audit.md is a point-in-time record and is NOT rewritten (per the run-081 precedent); this note
+ case-suite-output.txt document the closure. 083-W6 (firebreak --root structural fix) remains
DEFERRED HIGH by design (a code change to governance tooling, out of scope mid-run).
