---
status: pending
priority: p1
issue_id: "018"
tags: [code-review, performance, reliability]
dependencies: []
---

# Wasted sleep on final 429 attempt in _research_single_hook

## Problem Statement
When the 3rd (final) retry attempt gets a 429, the code sleeps up to 120s via `parse_retry_after()` before returning `(None, None, -1)`. That sleep serves no purpose -- there is no subsequent retry. This wastes up to 120 seconds per rate-limited lead on the final attempt.

## Findings
- **Agent**: Performance Oracle
- **Location**: `enrich.py` lines 1096-1104
- **Evidence**: The `time.sleep(wait)` runs unconditionally before checking `if attempt < 2: continue`. On the final attempt, `continue` is skipped and the function returns -1 immediately after sleeping.
- **Impact**: Up to 120s wasted per lead. With 3 leads tripping the circuit breaker, worst case adds ~360s of dead time.

## Proposed Solutions

### Option A: Move sleep inside the guard (Recommended)
```python
if resp.status_code == 429:
    wait = parse_retry_after(resp.headers.get("retry-after"), fallback=10.0)
    print(f"rate limited, waiting {wait:.0f}s...", end=" ")
    if attempt < 2:
        time.sleep(wait)
        continue
    return (None, None, -1)
```
- Pros: 2-line change, saves up to 120s per failed lead
- Cons: None
- Effort: Small (2 min)
- Risk: None

## Acceptance Criteria
- [ ] Final 429 attempt returns immediately without sleeping
- [ ] Non-final 429 attempts still sleep and retry
- [ ] `test_hook_research_429_exhausted_skips_persist` still passes

## Work Log
- 2026-05-06: Found by Performance Oracle during 8-agent review
