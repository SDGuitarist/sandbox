# Orchestrator Context Telemetry — run 081 (Step 1.52 / M29)

~30-agent scale-validation run. A MISSING boundary row below = instrument FAILURE
(harden trigger), never a pass. Proxy counts Read bodies + Agent returns ingested by
the orchestrator; misses system prompts, tool schemas, compaction. Comparative only.

NOTE (calibration, recorded for the validate-at-scale deliverable): the protocol's
"~200K-char proxy budget" appears conflated with the ~200K-TOKEN context window
(chars ≈ 4× tokens → ~800K-char equivalent). Percentages below use the protocol's
literal 200K-char budget for cross-run comparability, so >100% is expected on a
30-agent run and is NOT by itself saturation. Both readings noted per row.

| phase boundary | context_proxy_chars | % of ~200K-char proxy budget | note |
|----------------|---------------------|------------------------------|------|
| pre-gates (Step 6 equivalent — deepen pre-converged, skipped) | 311000 | 156% (≈39% of 800K-char/200K-token window) | HANDOFF 13K + agent returns 12K + template/tracking 6K + agent-pitfalls partial reads 157K + full plan 123K |
| Step 9w.6 (structural gates done, 9w.7 CLEARED) | 323000 | 162% (≈40% of 800K-char window) | swarm-planner + 9w.5 FAIL/fix/rerun PASS + 9w.6 PASS agent returns ~12K |
| Step 10w (all 30 workers returned) | 424000 | 212% (≈53% of 800K-char window) | assignment section 12K + 3 probe returns + 30 launch confirmations + 30 worker completion summaries ~75K + firebreak lifecycle bash ~3K |
