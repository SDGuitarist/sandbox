# Orchestrator Context Telemetry — run 083

| phase boundary | context_proxy_chars | % of ~200K-char proxy budget | note |
|----------------|---------------------|------------------------------|------|
| pre-swarm gates done (9w.7) | ~255000 | ~128% | Heavy front-load: HANDOFF + run-plan + full 1328-line spec + template + pitfalls page + 3 gate/probe agent returns. NOTE: proxy budget is a 200K-CHAR comparative metric; Opus 4.8 real window is 1M tokens (run-081 lesson: 430K chars ≈54% of real window). >100% of the char-proxy here is expected given the front-load and is NOT a real-window saturation signal. Delegating aggressively from here to keep growth flat. |
| Wave 0 merged + pushed (pre-Wave-1) | ~520000 | ~260% | Includes firebreak-classify.py read (~170K chars) + 5 Wave-0 worker reports + database.py/__init__.py reads. Char-proxy >100% expected on a 1M-token real window (run-081: 430K chars ≈54% real). No compaction observed; delegating assembly kept growth bounded. |
