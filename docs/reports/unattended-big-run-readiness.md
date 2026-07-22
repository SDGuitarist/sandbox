# Trust Gate: Requirements & Steps for a Big UNATTENDED Swarm Run

**Created:** 2026-07-22, from the Run 083 baseline grade (C+ / 3.1-of-5 as an *unattended-run* baseline).
**Purpose:** Do NOT launch a big (>=15-agent) autopilot-swarm run as truly hands-off until every TRUST
CRITERION below holds and the PHASE-4 validation run has passed. Run 083 succeeded only because a human
was in the loop (approved the master pushes, cat-verified the firebreak sentinel, hand-orchestrated the
wave barriers). An unattended run has none of those human catches.

---

## The 5 trust criteria (ALL must hold — this is the go/no-go)

1. **Zero-touch is real.** A full big run completes with **0 human interventions** — no launch-time
   approval, no manual catch. (083 failed this: it needed explicit master-push approval.)
2. **Governance is unattended-safe.** The firebreak **cannot silently fail open**, and needs **no manual
   toggling**. (083 failed this: FC68 live fail-open caught only by manual cat-verify; FC58 required
   manual off/on toggling for orchestrator gate python.)
3. **The mechanism is encoded, not improvised.** The wave-barrier loop (or whatever base strategy) runs
   **from the SKILL**, not from live orchestrator judgment. (083 failed this: waves were hand-run inline.)
4. **Value + safety instruments are self-enforcing.** `verify-harvest` has a real tool enforcer; the
   compounded-darkness gate recognizes a real dynamic verdict. (083: harvest gate self-certified; darkness
   gate threw a false-negative on a passing C2.)
5. **Context survives at scale, verified.** Orchestrator context telemetry shows headroom end-to-end; no
   context death. (083: heavy ~520K-char proxy at 19 agents inline, survived but un-delegated — a bigger
   SKILL-driven run must prove headroom.)

If any criterion is unmet, a big run STILL NEEDS A HUMAN IN THE LOOP (run it like 083, not hands-off).

---

## Steps to get there (ordered; Phases 1-3 are the fixes, Phase 4 is the proof)

### Phase 1 — Governance safety (HARD BLOCKERS; do first)
- **Fix FC68 (083-W6):** `.claude/hooks/firebreak-activate.py` must anchor `repo_root` via an explicit
  `--root <abs>` arg and/or `__file__`-relative resolution (NOT cwd `git rev-parse`); refuse/warn if the
  resolved root lacks `.claude/hooks/firebreak-classify.py`. Add a **post-activation sentinel read-back
  gate** to the SKILL (assert `firebreak-active.json` repo_root == main root) before any spawn. Add a
  **live-lifecycle test**: activate from a worktree cwd, assert the sentinel lands at the MAIN root.
- **Fix FC58 gap (H5):** either add a narrow module-mode carve-out for the orchestrator's own gate python
  (`python -m compileall <pkg>`, `python -m <pkg>.smoke`) to `TRUSTED_PIPELINE_SCRIPT_PATHS`, OR formalize
  the "deactivate-for-orchestrator-gate-window, reactivate+re-probe-before-spawn" toggle protocol in the
  SKILL so it is deterministic, not ad-hoc.
- **Re-arm discipline:** every (re)activation is followed by a positive-control probe OR a deterministic
  sentinel-location assertion before the next worker spawn.

### Phase 2 — Mechanism encoding (removes the live orchestrator from the loop)
- **Encode the wave-barrier loop in the autopilot SKILL:** for each wave -> spawn -> ownership-gate ->
  merge -> push-to-worker-base -> provenance re-verify -> firebreak re-arm+probe -> next wave. So an
  unattended run executes it, not a reasoning human.
- **Pre-resolve the base/push policy:** either a standing pre-approved master-push policy for throwaway
  runs, OR a worker-base strategy that does not require master pushes at all — so there is NO launch-time
  human approval. (This is what forced the one intervention in 083.)
- **Structural cwd safety:** the orchestrator always operates from the main repo root; guard against
  worktree cwd-drift on background-agent completion (the FC68 trigger).

### Phase 3 — Instrument trust (stop self-certifying)
- **Build `tools/verify_harvest.py`:** enforce >=5 distinct `root_cause_id`, >=2 net-new (by FC
  DESCRIPTION not just ID count), 1:1 binding to distinct BUILD_TRACKING FAILURES rows, and evidence-path
  resolution. Wire it as the real gate (mirrors verify-self-audit).
- **Fix `tools/check_compounded_darkness.py`:** recognize `c2-smoke-report.md` (STATUS: PASS) as a real
  dynamic-test verdict, so a passing smoke run is not mis-classified as "dark."

### Phase 4 — The validation run (this is what earns the trusted baseline)
- Run ONE more big swarm (>=20 agents) **fully unattended, SKILL-driven**, with Phases 1-3 in place.
- **PASS = ALL of:** 0 human interventions · 0 firebreak fail-opens (sentinel-location gate green every
  wave) · harvest gate tool-enforced (not self-certified) · darkness gate accurate · context telemetry
  shows headroom · self-audit honest (disconfirmer + 8 gates). 
- THAT run — not 083 — becomes the trusted baseline for hands-off big runs.

---

## Quick go/no-go before launching hands-off
- [ ] FC68 fixed + sentinel read-back gate live (Phase 1)
- [ ] FC58 orchestrator-gate-python resolved (Phase 1)
- [ ] Wave-barrier + base/push policy encoded in SKILL (Phase 2)
- [ ] verify_harvest.py + darkness fix shipped (Phase 3)
- [ ] Phase-4 validation run passed 0-intervention
If any box is empty -> run WITH a human in the loop (083-style), do NOT go hands-off.

**Source:** Run 083 rubric grade (this session); docs/reports/083/self-audit.md;
docs/reports/083/harvest-findings.md (H5/H7); agent-pitfalls FC58/FC68/FC69.
