---
review_agents:
  - codex (manual, binding — plan review GO; code review NO-GO → fix → re-review GO)
---

# Review Context — G3 Self-Audit Disconfirmer (compound 2026-06-26)

## Risk Chain

**Brainstorm/Plan risk (Feed-Forward, verify_first):** Does an Opus disconfirmer reading the SAME run artifacts produce *orthogonal, valid* findings, or just restate the Sonnet confirmer? Within-family (Opus vs Sonnet) is the WEAK diversity lever (self-preference is same-family); cross-family (Codex) is the strong one and the pre-registered escalation.

**Plan mitigation:** Cut the binding `disconfirmer_verdict` field (kept the no-LLM-in-dispose-path invariant); before-placement blind to the audit (anchoring-correct); findings routed through the existing Gates 2/5/7f as mandatory WARNs; new deterministic fail-closed Gate 8 enforces the link. Efficacy gated by a pre-registered probe (novel-valid > 0 AND overcall < 0.34), cross-family-judged, brief-tuning capped at 3 then escalate to Codex-as-standing-verifier.

**Work risk (R1, top):** TAIL_SYNC drift — wiring the disconfirmer into only one of solo/swarm, or in the wrong order (it MUST precede the self-audit in both paths).

**Review resolution:** Plan review (Codex) GO. Efficacy probe (Codex) PASS — novel-valid 4/4, overcall 0/25; 069 known-miss independently re-derived. Code review (Codex) NO-GO with 3 findings — 8c bijection was `contains` (D1⊂D10 + merged rows = fail-open) [P1]; 8a parse wording too loose for a fail-closed gate [P1]; one stale "9 hard gates" string in autopilot/SKILL.md [P2]. All fixed in `65954b4` (whole-cell equality + merged/phantom rejection + non-digit boundary; anchored finding-row regex with exhaustive accept/fail trichotomy; gate count → 8). Self-review also un-wrapped a line-wrapped sentinel in the agent. Codex re-review = GO, no new findings.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| .claude/skills/verify-self-audit/SKILL.md | NEW fail-closed Gate 8 (8a parse, 8c exact bijection); count 9→8 | the gate's whole-cell + boundary rules must stay strict (no fail-open regression) |
| .claude/agents/self-audit-disconfirmer.md | NEW Opus agent; D# output contract + canonical sentinel | sentinel/D#/severity literals must stay byte-identical to what Gate 8 + reviewer expect |
| .claude/agents/self-audit-reviewer.md | Step 2 D# ingestion (whole-cell Source); stays sonnet | one WARN per D#, Source cell EXACTLY the token (no path prefix / no merge) |
| .claude/agents/tail-runner.md | swarm Step 7.5 before Step 8; TAIL_SYNC comment | ordering parity with solo path |
| .claude/skills/autopilot/SKILL.md | solo Disconfirmer section before Self-Audit; Step 18w disk-verify; count→8 | TAIL_SYNC; solo fail-closed only as strong as reaching /verify-self-audit |
| tools/verify_delegated_status.py | advisory --artifact-kind disconfirmer (no status) | branch before ACCEPT_SETS lookup; exit codes 1..255 |

## Plan Reference

`docs/plans/2026-06-25-feat-g3-self-audit-disconfirmer-plan.md`
