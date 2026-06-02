---
status: pending
priority: p1
issue_id: "048"
tags: [code-review, security, testing-routes, run-061]
dependencies: []
---

# Missing Generic Exception Handler + content[0] Crash in Claude API Call

## Problem Statement

The Claude API call in `testing/routes.py:119-128` has three specific exception handlers (`APITimeoutError`, `APIConnectionError`, `APIStatusError`) but no generic `except Exception` fallback. If the Anthropic SDK raises an unexpected exception type (e.g., `json.JSONDecodeError` from malformed response, or `KeyError`), the request crashes with a 500 error and no test run is recorded.

Additionally, `response.content[0].text` on line 128 will crash with `IndexError` if the API returns an empty `content` array (possible on certain error conditions or tool-use-only responses).

## Findings

- **Source agents:** performance-oracle, kieran-python-reviewer
- **File:** `prompt-dashboard/app/blueprints/testing/routes.py:119-128`
- **Feed-Forward risk:** This is directly related to the plan's feed-forward risk "Claude API synchronous calls may timeout in Flask request cycle"

## Proposed Solutions

### Solution A: Add generic exception handler + content guard (Recommended)

Add a guard on `response.content[0]` and a final `except Exception` clause:

```python
response_text = response.content[0].text if response.content else None
```

And after the three specific handlers:

```python
except Exception as e:
    duration_ms = int(time.time() * 1000) - start_ms
    response_text = None
    input_tokens = None
    output_tokens = None
    error = 'Unexpected error during API call. Check server logs.'
    logger.exception('Unexpected error calling Claude API for prompt %d', prompt_id)
```

- **Effort:** Small (7 lines)
- **Risk:** None

## Acceptance Criteria

- [ ] No 500 errors from any Claude API failure mode
- [ ] Empty content array returns None for response_text, not IndexError
- [ ] All test runs are recorded in the database, including unexpected errors
- [ ] Server logs contain the full traceback for debugging

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-06-01 | Created from review | Feed-forward risk area confirmed |
