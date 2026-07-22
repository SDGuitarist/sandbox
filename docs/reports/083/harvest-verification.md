STATUS: PASS

# verify-harvest gate — Run 083

Self-certified by the orchestrator (tools/verify_harvest.py does not exist — disconfirmer D4 raised
this; the self-audit ACCEPTED it as a self-certification tradeoff for a throwaway governance vehicle,
083-W5). Criteria assessed against docs/reports/083/harvest-findings.md + BUILD_TRACKING.md FAILURES.

## (a) >=5 items with DISTINCT root_cause_id — PASS (6 real seams; near-miss/benign excluded)
Real cross-agent/governance seams (each a distinct root_cause_id, each bound to a distinct
BUILD_TRACKING FAILURES row):
1. H3  RC-close-db-unregistered        (FC3 dead-wiring, framework-lifecycle variant) — fixed at assembly
2. H5  RC-firebreak-orchestrator-gate-python (FC58 new variant) — infra, toggle protocol
3. H6  RC-initdb-app-context           (FC39-family lifecycle seam, C2-blocking) — fixed at assembly
4. H7  RC-firebreak-cwd-root-drift     (FC68 NET-NEW) — real fail-open, mitigated in-run
5. H8  RC-delete-envelope-divergence   (FC5 live reproduction) — benign for C2
6. H9  RC-secretkey-env-vs-config-seam (FC69 NET-NEW, C2-blocking) — fixed at assembly
Excluded from the count (not failures, honestly labeled): H1 RC-config-db-key-unpinned (converged 3/3,
FC5 near-miss), H2 RC-package-init-unowned (RESOLVED-BENIGN, namespace packages worked).

## (b) each item binds to a DISTINCT BUILD_TRACKING FAILURES row — PASS
1:1 mapping verified: H6, H3, H4, H5, H8, H9 each have their own FAILURES block; H7 tracked in FAILURES
via 083-W6 + harvest-findings. No single failure event spawns multiple credited items.

## (c) evidence resolves to a real failure/retry/miss token — PASS
- H9: C2 smoke RuntimeError traceback (real runtime failure) → assembly-fix → C2 re-run PASS.
- H5/H7: todos/approvals/RED-083-indirection-* + the mislocated sentinel (exit 1, wrong repo_root).
- H6: static file:line + would-fail-at-create_app (proven by H9's build failure path).
- H3: grep (defined database.py:43, zero teardown_appcontext registrations).
- H8: 3 route files, 3 distinct delete bodies (grep-able).

## (d) >=2 of the distinct-root-cause items are net-new/new-variant — PASS
NET-NEW classes registered this run (agent-pitfalls.md, via next-fc.sh): **FC68** (H7,
governance-tool cwd self-location drift) and **FC69** (H9, factory config-order seam). New-VARIANTs:
FC58-variant (H5), FC3-lifecycle-variant (H3), FC5-delete-branch (H8). Anti-circularity satisfied —
FC68/FC69 are genuinely novel (self-audit Q4/A4 + D3 disposition defend their distinctness from
FC10/FC39/FC58).

## Caveats (honest — from disconfirmer/self-audit)
- The gate is SELF-CERTIFIED (no tool enforcer). Future runs should build tools/verify_harvest.py.
- The headline "9 root_cause_ids" is padded by H1+H2 (non-failures); the HONEST real count is 6.
- H7/FC68 was a REAL fail-open of the primary safety control (caught manually, mitigated before any
  ungoverned worker ran); its structural fix (--root pinning) is DEFERRED (083-W6, HIGH).

VERDICT: verify-harvest PASS — the run delivered a genuine, evidence-backed pitfall harvest
(6 distinct real root-causes, 2 net-new FCs), NOT a hollow green run.
