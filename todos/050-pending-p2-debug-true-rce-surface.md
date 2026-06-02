---
status: pending
priority: p2
issue_id: "050"
tags: [code-review, security, run-061]
dependencies: []
---

# debug=True RCE Surface in run.py

## Problem Statement

`run.py:5` has `debug=True` which enables the Werkzeug interactive debugger. While the app binds to `127.0.0.1` (localhost only), if accidentally changed to `0.0.0.0` or accessed via port forwarding, the debugger's interactive Python console becomes an RCE vector. The PIN can be brute-forced on macOS.

## Findings

- **Source agent:** security-sentinel
- **File:** `prompt-dashboard/run.py:5`
- **Note:** This is prescribed in the spec and `.env.example` has `FLASK_DEBUG=1`. Downgraded from P1 to P2 because the app binds to localhost only.

## Proposed Solutions

### Solution A: Environment-controlled debug mode (Recommended)

```python
app.run(host='127.0.0.1', port=5050,
        debug=os.environ.get('FLASK_DEBUG', '0') == '1',
        threaded=True)
```

- **Effort:** Small (1 line)
- **Risk:** None

## Acceptance Criteria

- [ ] Debug mode only enabled when FLASK_DEBUG=1 is set
- [ ] Default is debug=False

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-06-01 | Created from review | Localhost-only mitigates but doesn't eliminate risk |
