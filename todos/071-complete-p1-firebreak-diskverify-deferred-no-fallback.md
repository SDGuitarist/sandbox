---
status: complete
priority: p1
issue_id: "071"
tags: [code-review, firebreak, g1, architecture, orchestrator]
dependencies: []
---

# P1 — Disk-verify gates deferred under active firebreak (no fallback)

## Problem Statement

`python3 tools/verify_delegated_status.py ...` (Steps 11w, 18w) and any other
`python3`-invoked orchestrator gate tool is DEFERRED by the G1 firebreak when
the firebreak is active during the swarm build phase. There is NO non-python
equivalent for this gate logic. Under an active firebreak, the automated
disk-verify checks cannot run; a human must do them manually — blocking
unattended completion.

**Why it matters:** The firebreak deferred 100% of orchestrator python invocations
in run 079. The disk-verify at Steps 11w–16w was done manually. This is not scalable
and breaks the "unattended" promise of autopilot.

## Findings

- **Evidence (run 079):** `python3 tools/verify_delegated_status.py ...` deferred as
  `indirection` (RED-079-indirection-8ec90336b391.md). Manual disk-verify performed
  (existence + line-1 STATUS:PASS + run-id 079 + mtime check).
- **Root cause (firebreak-classify.py):** `classify_simple_command` calls
  `bash_indirection(words, cmd, sentinel)` unconditionally at line 2070 for ALL
  identities. `bash_indirection` defers any `python3` invocation unless it matches
  `KNOWN_TEST_FRAMEWORKS` (pytest only). No identity parameter is passed; there is
  no TRUSTED bypass.
- **Architecture reviewer finding (run 079 review):** P1. No non-python fallback
  exists for disk-verify logic. TRUSTED identity bypass already exists for Write
  tool (lines 2118-2123) and F13 opaque check (line 2057) but NOT for
  bash_indirection.

## Proposed Solutions

### Solution A: Trusted-tool indirection allowlist in classify_simple_command (RECOMMENDED)

Add a pre-check before the `bash_indirection` call at line 2070: when
`identity in TRUSTED` and the script basename is in a hardcoded allowlist
(`verify_delegated_status.py`, `check_spec_provenance.py`, `firebreak-activate.py`),
skip bash_indirection. Scope: TRUSTED identities only; workers remain fully governed.

**Pros:** Narrowest blast radius; consistent with existing TRUSTED carve-outs for
Write; doesn't require allowing all python from orchestrator.
**Cons:** Adds a maintenance surface (allowlist must be updated for new pipeline tools).
**Effort:** Small (3-5 lines in classify_simple_command)
**Risk:** Low if allowlist matches on basename only (no path traversal bypass risk).

### Solution B: Thread identity into bash_indirection

Pass `identity` as a parameter to `bash_indirection` (line 1789) and update the
call at line 2070. Apply the allowlist check inside bash_indirection rather than
before it.

**Pros:** Cleaner encapsulation; bash_indirection owns the full decision.
**Cons:** Larger refactor; bash_indirection is called from one place so no
immediate benefit over Solution A.
**Effort:** Small-Medium
**Risk:** Low; the single caller means no accidental bypass.

## Recommended Action

Implement Solution A first. Scope: classify_simple_command pre-check at line 2070.
Allowlist: `{"verify_delegated_status.py", "check_spec_provenance.py",
"firebreak-activate.py"}`. Only when `identity in TRUSTED`. Add Fix C (live-lifecycle
integration test) in the same PR to verify regression.

## Technical Details

- **Affected files:**
  - `.claude/hooks/firebreak-classify.py` — `classify_simple_command` (line 2070),
    `bash_indirection` (line 1789)
  - `tools/verify_delegated_status.py` — the blocked gate tool
- **Test to add:** Live-lifecycle test with active sentinel: orchestrator python
  GREEN, worker python RED, orchestrator rm GREEN.

## Acceptance Criteria

- [ ] `python3 tools/verify_delegated_status.py ...` from orchestrator returns GREEN
  under an active firebreak
- [ ] Worker `python3 <any-script>` still DEFERRED under active firebreak
- [ ] Allowlist comment references G1 firebreak rationale
- [ ] Live-lifecycle integration test covers this scenario
- [ ] 265/265 existing classifier tests still pass

## Work Log

- 2026-06-29: Created from run 079 review (architecture-strategist P1 finding).
  Architecture reviewer confirmed: P1, confirmed by code trace (line 2070 in
  firebreak-classify.py; no identity param passed). Manual disk-verify performed as
  workaround in run 079.
