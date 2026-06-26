---
title: "G1 Firebreak — from DeepMind PDF to a live, self-validating control"
date: 2026-06-25
type: solution
status: canonical
tags:
  - lessons-learned
  - security
  - firebreak
  - autopilot
  - activation
  - governance
  - agent-security
summary: >
  The G1 risk-tiered firebreak began as one of five hardening gaps extracted from
  Google DeepMind's "Three Layers of Agent Security" paper, scored against the
  unattended autopilot swarm. This doc records how G1 went from a verified-but-dormant
  classifier to a live control: the two distinct activation gaps (registering the
  global PreToolUse hook; wiring the orchestrator to write/probe/teardown the
  sentinel), the deterministic positive-control probe that makes the first real swarm
  run self-validating, and the central lesson — harness-green is not live. Companion
  to the convergence-loop diagnosis in 2026-06-24-enumerated-denylist-vs-structural-backstop.md.
---

# G1 Firebreak — Activation Arc

## Where it came from

Origin: a Google DeepMind paper, *"Three Layers of Agent Security"* (+ the AI Control
Roadmap companion), analyzed in `docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md`.
That analysis scored the autopilot swarm against the framework and produced **five
prioritized hardening gaps (G1–G5)**. G1 — a risk-tiered firebreak that defers the
outward/irreversible tail of worker actions to a human-approval queue instead of a
blanket `bypassPermissions` — was rated the single highest-leverage gap and built first.

## What "build the classifier" did and did NOT achieve

Phase 1 produced a deterministic PreToolUse classifier (`firebreak-classify.py`), a
cheap entry gate (`firebreak-gate.sh`), four test corpora, and a Step-0 spike proving
the hook fires for a real `isolation:"worktree"` + `bypassPermissions` worker. All of
that was **harness-verified** — JSON envelopes piped to the classifier, temp repos,
simulated workers. It was also, the entire time, **completely inert in reality**:

- The hook was never registered in `~/.claude/settings.json`, so it didn't run in any
  session.
- Even once registered, the classifier is a **no-op unless a run sentinel exists**, and
  **nothing wrote the sentinel** — the autopilot skill had zero firebreak wiring.

So "the classifier passes 265 tests" and "the firebreak protects a swarm run" were two
very different claims, and only the first was true. **This is the lesson that bookends
the whole arc: harness-green ≠ live.** A control that is perfect in its test harness and
unwired in the orchestrator provides exactly zero protection — and worse, *false
confidence*, the precise fail-open the threat model warns against.

## The two activation gaps (and why they're distinct)

**Gap 1 — dormant → armed: register the global hook.**
A PreToolUse hook in **global** `~/.claude/settings.json` (matcher `Bash|mcp__.*|Write|Edit`),
invoking the project-local gate by absolute path, file-guarded so it silently allows if
the gate ever goes missing:

```
[ -f <abs>/firebreak-gate.sh ] && exec bash <abs>/firebreak-gate.sh; exit 0
```

Global (not project-local) placement is required so the hook governs worktree-isolated
workers, whose cwd is a worktree, not the repo root. The classifier walks **up from cwd**
to find the sentinel, so a worker in `<repo>/.claude/worktrees/...` still finds
`<repo>/.claude/firebreak-active.json`. The classifier denies via a
`permissionDecision:"deny"` JSON on **stdout** (exit code always 0), so the hook command
only needs stdout to flow through — `exec` does that and can't swallow a deny.
Cost in unrelated sessions: the gate's grep runs on every tool call (cheap), and a python
cold-start on marker-bearing commands that immediately no-ops (no sentinel). Manual
sessions are otherwise untouched.

**Gap 2 — armed → governing: wire the orchestrator.**
Armed is not governing: without a sentinel, the armed hook no-ops during a swarm run.
A deterministic helper (`firebreak-activate.py`: `activate` / `set-phase` / `deactivate`
/ `status`) plus three edits to the autopilot skill:

1. **Step 9w.9.6 (new)** — after the provenance gate / before worker spawn: write the
   sentinel, then run a **positive-control probe** (below). Abort fail-open if it fails.
2. **Step 17w** — flip `phase → tail` before the tail-runner spawn so the trusted tail
   keeps its learnings-write carve-out (F5).
3. **Step 18w + the 11w–16w blocking-abort path** — `deactivate` at run end, success or
   failure.

## The positive-control probe — making the first real run self-validating

The riskiest assumption is that the hook *actually* fires for the real worker path on
*this* run (not just in the one-time Step-0 spike). So activation doesn't trust that —
it proves it, every run, before spawning the real workers:

- Spawn ONE real worker-shaped agent (`isolation:"worktree"`, `bypassPermissions`,
  cheap model) that attempts two control-plane writes (`todos/approvals/__fb_probe_*__`
  via Write tool and via Bash redirect) plus a harmless outward `curl …firebreak-probe.invalid`.
- **Verify deterministically, not by the agent's self-report:** after the probe, the
  orchestrator checks whether the canary files exist. If either exists, the firebreak did
  NOT block the worker → **abort the run fail-open**. If neither exists, both writes were
  denied → the firebreak governs the worker path → proceed.
- Probe-target choice matters: a Write to `.claude/hooks/<newfile>` is ALLOWED (only the
  firebreak scripts/sentinel/settings are protected files), but `todos/approvals/<x>` is
  reliably denied via both Write and Bash — that's why the canary lives there. `mkdir -p
  todos/approvals` first, so a fail-open Bash redirect actually creates its canary
  instead of failing on a missing dir and hiding the failure.

Net effect: **you never need to manufacture a test build to validate G1.** Its first real
swarm run validates it — and fails closed (aborts safely) if it isn't live.

## Verification done

- Four classifier suites green: classifier 265, gate 26, superset 295/0-gaps,
  soundness 319 RED + 127 GREEN.
- Wired hook command, production walk-up path: worker CP write → deny; worker
  `docker buildx --push` → deny; no sentinel → silent allow; benign read → allow.
- End-to-end with the real scripts: `activate` governs a worker `buildx --push`,
  `set-phase tail` stays governed, `deactivate` releases, no stray sentinels.

## Declared residuals (NOT chased — see the stopping discipline)

- **No live swarm run yet.** Everything is harness/e2e-verified; the integrated flow has
  never executed inside a real `dangerouslySkipPermissions` autopilot run. The probe is
  the built-in live proof; the first real swarm run is the validation.
- **Stale sentinel on orchestrator crash** between `activate` and teardown — governs
  manual sessions in the repo until the next run's `activate` (which clears stale) or a
  manual `deactivate`. Documented in the skill.
- **Solo path unwired** — only the swarm path spawns workers (the threat-model target);
  solo runs as one trusted agent.
- **Classifier residuals** carry over from the convergence work: the interpreter-escape,
  the non-statically-resolvable `$VAR`, and the OUTWARD unlisted-binary tail. See the
  threat model in the plan.

## Feed-Forward

- **Hardest decision:** whether "flip it on" meant registering the hook (literal, but
  inert for swarms) or wiring the orchestrator (the real thing). Registering an inert
  global hook and calling it done would have been the textbook fail-open. Both were done,
  in order, with the inertness stated plainly.
- **Rejected alternative:** manufacturing a throwaway swarm build to validate G1 live.
  Rejected as the same over-engineering the convergence loop fell into — the probe is
  designed to self-validate on first real use, so synthesizing a test for it is wasted
  spend.
- **Least confident:** the first real swarm run — environment permitting
  (`dangerouslySkipPermissions`). The probe is designed to abort safely if anything is
  off, so the failure mode is a halted run, not an ungoverned one.

## Pointers
- Plan: `docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md`
- Governance map: `docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md` (item G1)
- Convergence-loop diagnosis: `docs/solutions/2026-06-24-enumerated-denylist-vs-structural-backstop.md`
- Code: `.claude/hooks/firebreak-{gate.sh,classify.py,activate.py}`; orchestrator
  Steps 9w.9.6 / 17w / 18w in `.claude/skills/autopilot/SKILL.md`.
- Global hook: `~/.claude/settings.json` PreToolUse (backup `~/.claude/settings.json.bak-firebreak-20260625`).
