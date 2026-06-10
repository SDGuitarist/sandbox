# Codex Decision Handoff — FC51 Spec-Provenance REPAIR Hardening

**Type:** Architecture decision (advisory, not a binding code review).
**Date:** 2026-06-09
**Repo:** `~/Projects/sandbox` (Sandbox autopilot harness)
**Branch:** `feat/fc51-worktree-spec-base` (off `master` @ `49deb17`)
**Decider:** Alejandro (beginner dev) + Claude Code, with Codex's recommendation.

---

## Read these first (in order)

1. `HANDOFF.md` — current repo state (Run 070 + hardening + fixtures just shipped to master).
2. `CLAUDE.md` — operating contract (autonomy classes, swarm spec rules, bash rules).
3. `.claude/skills/autopilot/SKILL.md` — **Step 9w.9.5 lines 602–647** (the step we are hardening) and **Step 10w lines 649–758** (the spawn path it gates).
4. `tools/check_spec_provenance.py` — the shipped detector that 9w.9.5 already calls.
5. `docs/solutions/2026-06-08-film-production-pm-run-070-swarm-build.md` — **lines 238–264** (the FC51 spec-file-divergence analysis) and **lines 322–340** (prevention strategies).
6. `docs/solutions/2026-06-07-autopilot-orchestration-hardening.md` — Track A (FC51 cherry-pick assembly) context.

---

## The decision we need

**How should we harden the spec-provenance REPAIR in autopilot Step 9w.9.5?**
Detection already works (shipped). The repair is still fragile prose. We need
Codex to pick the right repair architecture and pressure-test it before we touch
this load-bearing skill.

---

## Background: what FC51 / FC52 are

In a swarm build, the orchestrator runs on a **feature branch**. Worker agents are
spawned with `isolation: "worktree"`, and those worktrees **root on the repo's
DEFAULT branch (master) HEAD**, NOT the feature branch. (Confirmed empirically:
Run 070's worktree base was `f90aed8` = master HEAD.)

The plan/spec lives at `docs/plans/<spec>.md`. During the pre-swarm convergence
loop, the spec is edited/converged **on the feature branch**. All pre-swarm gates
(9w.5 consistency, 9w.6 completeness, 9w.8 spec-eval) validate the
**feature-branch** spec. But workers read the spec **as it exists at the worktree
base (master HEAD)** — which is STALE if convergence happened after that base
commit.

**Run 070's near-miss:** all 16 workers read a 2010-line stale spec while the gates
had validated the 2295-line converged spec. The run survived only because the
orchestrator happened to also inject spec sections into briefs — "saved by luck."

This is "gate/use provenance drift" — the gates certify an artifact the workers
never read.

---

## Current state of Step 9w.9.5 (verbatim, lines 602–647)

The step currently does three things:

1. **Detect** — runs `tools/check_spec_provenance.py --default-branch <d>
   --original-branch <feat> --spec-path docs/plans/<spec>.md`. Line 1 of output:
   `STATUS: PROVENANCE_OK` (exit 0) / `PROVENANCE_DRIFT` (exit 3) / ERROR (exit 2).
   **This is shipped and works** (also exercised by fixture F-D1). ✅

2. **Repair** — prose, two channels, current labeling:
   - **"Preferred / reliable" — inline brief injection.** Inject the full converged
     spec (or per-role sections) into every worker brief; tell workers the brief is
     authoritative over any worktree spec file.
   - **"Additional" — put the converged spec at the worktree base.** Cherry-pick the
     converged spec file onto the default-branch HEAD so the file channel matches.

3. **Record** — write `docs/reports/<run-id>/spec-provenance.md` with
   `STATUS: PROVENANCE_OK` or `PROVENANCE_REPAIRED -- <channel>`.

4. A rule: NEVER spawn while the worktree-base spec differs from the gated spec
   without recording the repair.

---

## The problem with the current repair

The solution doc (lines 243–247) calls **brief injection fragile** for three reasons:
1. **Manual** — the orchestrator must know which spec sections changed and inject them.
2. **Unverifiable** — there is NO validation that brief content matches the current
   spec; workers could get a stale/incomplete brief with no error.
3. **Not version-controlled** alongside the spec changes.

Yet 9w.9.5 currently labels brief injection as the *preferred/reliable* channel.

**The deeper gap:** there is **no post-repair re-verification**. Detection runs,
repair happens, then the pipeline spawns — nothing confirms the repair actually
closed the drift. (Lesson #2 from Run 070, verbatim: "no validation that brief
content matches the current spec.")

---

## The core trade-off

| | Cherry-pick spec to worktree base | Inline brief injection |
|---|---|---|
| **Determinism** | Deterministic: file physically present where workers read it | Manual curation; orchestrator must know what changed |
| **Self-verifying** | YES — re-run the detector → `PROVENANCE_OK` is a hard, exact proof | NO — "did I inject the right sections?" is heuristic |
| **Side effect** | Writes a spec-only commit to the **default branch (master) mid-run, before the build is validated** | Touches nothing outside briefs |
| **Failure mode** | Mutating master pre-validation; if run aborts, master carries an orphan spec commit | Silent stale/incomplete brief → workers diverge invisibly until review |

The tension: the deterministic channel (cherry-pick) is the one that mutates the
default branch before we know the build is good. The non-invasive channel
(injection) is the one we can't verify.

---

## Candidate options (Codex may propose a better one)

**Option A — Cherry-pick primary + mandatory re-verify.**
Make cherry-picking the converged spec onto the worktree base the PRIMARY channel.
After the cherry-pick, MANDATORY re-run of `check_spec_provenance.py`; require
`PROVENANCE_OK` before spawn, else ABORT. Brief injection demoted to a documented
fallback (when writing to the default branch is undesirable). Record
`STATUS: PROVENANCE_REPAIRED -- spec-committed-to-base` + re-verify SHA.

**Option B — Injection primary + coverage check.**
Keep inline brief injection primary (never touches master), but ADD a mandatory
check that the injected section set covers the spec diff (`git diff` of spec
sections between base and feat). Record injected section titles. Less invasive but
the coverage check is heuristic, not an exact equality proof.

**Option C — Hybrid / conditional.**
e.g., prefer cherry-pick when the spec-only change is isolable in a clean commit;
fall back to injection + coverage check otherwise. Codex to specify the decision rule.

---

## Questions for Codex (please answer each)

1. **Which repair channel should be PRIMARY**, and why? Specifically weigh
   "deterministic + self-verifying (cherry-pick)" against "mutates master mid-run,
   pre-validation."
2. **Is mutating the default branch (master) before the build is validated an
   acceptable orchestrator action** in this harness? If a run aborts after the
   cherry-pick, what's the cleanup contract? Does this violate any invariant in
   CLAUDE.md's Forbidden Actions / Production Safety?
3. **Can the cherry-pick channel be made airtight** — is "re-run the detector →
   PROVENANCE_OK" a sufficient proof that all 16 worktrees will read the converged
   spec? Are there worktree-base assumptions that could break it (e.g., worktrees
   NOT rooting on master HEAD, or rooting on a stale local master)?
4. **For the injection channel, is an exact coverage proof even possible**, or is it
   inherently heuristic? If heuristic, should injection be allowed as anything other
   than an explicitly-flagged fallback?
5. **Is the post-repair re-verification gate the real missing safety net** (vs. the
   choice of channel)? Should re-verification be MANDATORY regardless of channel?
6. **Scope check:** should this be a focused edit to Step 9w.9.5, or does it warrant
   a brainstorm→plan→review loop? Is there a simpler fix we're missing (e.g., make
   worktrees root on the feature branch instead — is that possible/safe)?
7. **Anything we got wrong** in the trade-off table or the FC51/FC52 framing above?

---

## Output we want from Codex

- A clear recommendation: PRIMARY channel + whether re-verification is mandatory.
- Answers to the 7 questions, ordered by importance.
- Any blocking concerns about mutating master mid-run.
- A short proposed rewrite outline for Step 9w.9.5's Repair + Record sections (prose
  bullets, not full text) that we can turn into the actual edit.
- Explicitly flag if you think this needs the full brainstorm→plan loop rather than
  a direct skill edit.
