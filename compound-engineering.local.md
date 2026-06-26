---
review_agents:
  - codex (manual, binding — ~17 convergence passes R1..F16c + buildx)
  - claude (red-team rounds + self-review)
---

# Review Context — G1 Risk-Tiered Firebreak (compound 2026-06-25)

## Risk Chain

**Brainstorm/Plan risk (Feed-Forward "least confident"):** that the PreToolUse hook governs only the MAIN session, not the real worker path (`isolation:"worktree"` + `bypassPermissions`); and that the classifier cannot protect its own control plane from the workers it governs.

**Plan mitigation:** Step-0 gating spike empirically proved the hook fires for a real worktree+bypass worker and that the four-role identity metadata holds. Control-plane protection keyed on a trusted-identity allowlist (F1/F5). Threat model declared up front as honest-agent guard with named residuals — NOT adversarial-proof.

**Work risk (from Feed-Forward):** harness-green ≠ live. The classifier passed 265 tests while inert (hook unregistered, sentinel never written by the orchestrator), so it protected nothing. Closed by: registering the global PreToolUse hook + wiring the orchestrator (sentinel write + positive-control probe + teardown, Steps 9w.9.6/17w/18w).

**Review resolution:** The convergence loop ran ~17 passes (R1–R8, F1–F16c, then the buildx outward fix). Root cause was NOT slow reviewing — it was a deny-known-bad classifier whose structural backstop had an *enumerated exemption* (`DISPATCHERS`) that regenerated the loop. Stopped by a structural fix (`_structured_subvalues` in both the dispatcher handler and the catch-all) + a pre-registered stopping discipline. Final: classifier 265, gate 26, superset 295/0-gaps, soundness 319 RED + 127 GREEN. Residuals declared (interpreter escape, non-resolvable `$VAR`, outward unlisted-binary tail, no live swarm run yet).

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| .claude/hooks/firebreak-classify.py | `_structured_subvalues`, `_arg_path_candidates` catch-all extension, `DISPATCHER_OUTPUT_FLAGS` (+`--cache-to`/`--metadata-file`/`--iidfile`), `_buildx_registry_push` | over-defer (false positives halt real builds) vs fail-open; the DISPATCHERS exemption is the recurring leak source |
| .claude/hooks/firebreak-activate.py | NEW sentinel lifecycle (activate/set-phase/deactivate/status) | stale sentinel on crash governs manual sessions in-repo (declared residual) |
| .claude/skills/autopilot/SKILL.md | Steps 9w.9.6 (activate + positive-control probe + abort), 17w (phase→tail), 18w + 11w-16w (teardown) | un-exercised end-to-end under a real swarm (the residual risk); probe must abort fail-open, not proceed |
| ~/.claude/settings.json | global PreToolUse hook registered (matcher Bash\|mcp__.*\|Write\|Edit) | machine-wide blast radius; file-guarded exec, deny via stdout JSON |

## Plan Reference

`docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md`
