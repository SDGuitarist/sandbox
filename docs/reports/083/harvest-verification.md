STATUS: FAIL -- BIJECTION -- REAL root_cause_id(s) with no ## FAILURES row: ['RC-firebreak-cwd-root-drift']

# verify-harvest gate — run 083

Deterministic FC-harvest gate (tools/verify_harvest.py). Checks the run's REAL findings for breadth, bijection to BUILD_TRACKING FAILURES, resolvable evidence, and net-new classes verified against the frozen baseline.

- parsed 9 finding rows; 7 REAL (status begins with REAL)
- (a) BREADTH: 7 distinct REAL root_cause_id (need >= 5)
- (b) BIJECTION: 6 failure rows in ## FAILURES; 1 REAL findings unmatched

VERDICT: FAIL — BIJECTION -- REAL root_cause_id(s) with no ## FAILURES row: ['RC-firebreak-cwd-root-drift']. The harvest does not meet the gate; do NOT credit this run with a genuine pitfall harvest until fixed.
