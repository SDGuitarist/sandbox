# Codex Handoff — G1 Firebreak Phase 1 IMPLEMENTATION Review (pre-activation)

**Date:** 2026-06-23
**Phase:** Phase 1 core complete (5 hardening passes) → review BEFORE activation
**Repo:** `~/Projects/sandbox` · **Branch:** `feat/g1-risk-tiered-firebreak` (pushed, latest `49a6e9c`)
**Scope:** review the IMPLEMENTATION, not the plan (the plan already got a Codex GO).

## What to review

The deterministic classifier + cheap entry gate that enforce the firebreak. This is
a checkpoint *before* wiring the hook into global `~/.claude/settings.json`, so the
goal is to catch anything that should block activation.

Files:
- `.claude/hooks/firebreak-classify.py` — the classifier (pure stdlib, one file).
- `.claude/hooks/firebreak-gate.sh` — the cheap entry gate (forwards-on-suspicion).
- Tests: `.claude/hooks/test_firebreak_{classify,gate,superset,soundness}.py`.
- Plan + residual model: `docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md`
  (read the "Threat Model" + "Deepening Review — Changelog" F1–F13 FIRST).
- Review trail: `docs/reviews/2026-06-22-g1-phase1-second-review.md`,
  `…2026-06-23-…-third-review.md`, `…-fourth-review.md`, `…-fifth-review.md`.

## The contract (what the code claims)

- **Two enforced invariants:** (1) **superset** — the gate forwards EVERY command the
  classifier would deny (under-forwarding = a RED action fast-paths unseen);
  (2) **soundness** — for a RED corpus the classifier denies each, for a GREEN corpus
  it allows each. Both are test-encoded.
- **Decision order:** F13 opaque-word → control-plane/F9 → outward → indirection → mcp
  → fail-closed. Trusted-identity allowlist (orchestrator/swarm-runner/tail-runner)
  for control-plane writes + learnings carve-out.
- **Declared residuals (NOT bugs — confirm they're acceptable, honest bounds):**
  #1 allowlisted-interpreter escape (hook can't see in-process file I/O);
  #2 inherited-`$VAR` redirect to an unknown dest stays GREEN;
  #3 a runner/dispatcher fetching an UNRECOGNIZED package (`npx some-evil-pkg`) stays
  GREEN — recursion catches all *recognized* inner commands but can't know an arbitrary
  package is RED without running it.

## Scrutinize (adversarial, P0/P1/P2 with exact file:line + the R/F number)

1. **Runner/dispatcher recursion (just changed in `49a6e9c`).** `resolve_argv0` +
   `_skip_runner_flags` + `extract_nested_commands` now recurse `npx --call`/`-c`
   command strings, two-token runner value-flags (`pnpm dlx --package`, `pipx run
   --spec`), and the `npm exec`/`npm x`/`pnpm exec`/`yarn exec`/`bun x` family. Can a
   worker STILL smuggle a *recognized* RED command (curl/git push/vercel/gh api/...)
   through a runner variant the recursion mis-resolves? Probe nested runners,
   wrapper-then-runner, `=`-joined flags, `--` placement, opaque inner argv0.
2. **Superset holes.** Is there ANY command the classifier denies but the gate's
   marker grep fast-paths? (The superset test is a corpus, not a proof — look for a
   category of denial whose literal tokens dodge every `grep -e` marker in the gate.)
3. **Over-defer / false positives.** Does any benign GREEN runner/build command now
   wrongly defer (`npm exec -- jest`, `pnpm dlx tsc`, `pipx run --spec build pytest`)?
4. **Identity / control-plane (F1+F5+F9).** Can a worker reach the hook
   config/scripts/sentinel/`todos/approvals/` via a vector the realpath /
   env-indirection / forward-on-suspicion checks miss? Can `agent_type` be forged?
5. **Are the three declared residuals correctly bounded and honestly stated**, or does
   the code overclaim protection beyond direct worker tool calls anywhere?

## How to run the tests

```
python3 .claude/hooks/test_firebreak_classify.py     # 131/131
python3 .claude/hooks/test_firebreak_gate.py         # 26/26
python3 .claude/hooks/test_firebreak_superset.py     # 153 cases, 0 gaps
python3 .claude/hooks/test_firebreak_soundness.py    # 83 RED + 34 GREEN
```

Return findings as P0/P1/P2 with the exact file:line (and R/F number) to change.
Activation (global hook wiring + orchestrator integration) is OUT OF SCOPE for this
review — flag only what should block it.
