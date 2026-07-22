---
review_agents:
  - security-sentinel
  - learnings-researcher
  - flow-trace-reviewer
---

# Review Context — swarmlimit Max-Value Autopilot Limit-Test (Run 083)

## Risk Chain

**Brainstorm risk (Feed-Forward, verify_first):** "The value is the PITFALL HARVEST + governance stress, not the agent count. Two failure modes: (1) a run that completes GREEN but teaches nothing (hollow) — a date-stamp presence check is gameable; (2) padding the count with clone resources / consumer clusters so 'biggest' is manufactured, not earned."

**Plan mitigation:** Evidence-backed verify-harvest gate (≥5 distinct root_cause_id, ≥2 net-new FCs, each bound to a distinct FAILURES row, anti-circularity). Path-B coupling: state-machine, cross-resource uniqueness, class-B transactions, soft-delete. 3-wave merge-barrier structure for FC52 provenance. Spec §5 Transaction Contracts table with Class A/B/C classification.

**Work risk (Feed-Forward):** process_return is a 4-table atomic write reaching into 3 other agents' tables via in-tx helpers — the densest cross-agent write. Also: whether smoke.py (single owner, Wave-0 authored) is correct, since a bug there makes C2 and every Path-B EARS unverifiable.

**Review resolution:** 0 P1, 3 P2 deferred (all throwaway-vehicle justification). Feed-Forward risk seam (process_return 4-table tx + ext_ref uniqueness) DID NOT FIRE — spec §5 Class A/B/C pin was sufficient. The seams that fired were lifecycle/infrastructure (H3 FC3 dead-wiring, H6 FC39 app-context, H7 FC68 cwd-drift, H9 FC69 config-order) not the business-logic seam.

## Files to Scrutinize (next run / swarm pattern)

| File | What changed | Risk area |
|------|-------------|-----------|
| swarmlimit/__init__.py | H3 fix: registered teardown_appcontext(close_db); H6 fix: wrapped init_db in app context | Lifecycle registration seams — these are exactly where FC3/FC39 live |
| swarmlimit/smoke.py | H9 fix: os.environ.setdefault("SECRET_KEY", ...) in build_app() | Config-order seam between smoke and factory — FC69 |
| swarmlimit/models/return_models.py | process_return 4-table atomic write | Feed-forward seam — VERIFIED PASS in review |
| swarmlimit/models/order_models.py | create_order class-B transaction | Feed-forward seam — VERIFIED PASS |
| swarmlimit/refs.py | assert_ext_ref_unique cross-resource under caller's conn | TOCTOU guard — VERIFIED PASS (BEGIN IMMEDIATE serializes) |
| .claude/firebreak-active.json | H7: sentinel written to wrong root during cwd-drift | FC68 governance-tool cwd self-location — verify repo_root after every activate |

## Deferred Items

- H5 FC58: firebreak allowlist doesn't cover `python -m compileall` or `python -m <pkg>.smoke` — toggle protocol works but is manual; consider extending TRUSTED_PIPELINE_SCRIPT_PATHS
- H7 FC68: firebreak-activate.py should take explicit `--root` argument instead of self-locating via cwd
- P2-01: restock_product_in_tx doesn't validate product existence (silent 0-rowcount on unknown pid — harmless given FK constraints but a code smell)
- P2-02: advance_shipment TOCTOU on class-A read-then-update (acceptable for SQLite throwaway)
- P2-03: H8 DELETE-success envelope divergence documented; pin every response branch in future specs

## Plan Reference

`docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md`
`docs/plans/2026-07-21-feat-082-max-value-unattended-autopilot-limit-test-plan.md`
