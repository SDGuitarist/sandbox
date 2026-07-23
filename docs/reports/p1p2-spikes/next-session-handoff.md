Work in /Users/alejandroguillen/Projects/sandbox
Branch: feat/p1p2-unattended-swarm-wave-barrier
Live HEAD: 654c5ee426066d236d5c875d0e02aa6453103813
HANDOFF.md: /Users/alejandroguillen/Projects/sandbox/HANDOFF.md

THE ASK: Codex returned NO-GO on the §0 verify-first spike review. Resolve the 4 findings by
editing the plan + spikes, re-running the affected spikes, updating the artifacts, doing a second
self-review, and producing a fresh Codex §0 re-review handoff. **Do NOT start §1.** Do NOT launch
any autopilot run.

=========================================================================================
WHAT THIS PROJECT IS (self-contained context — you will not have the prior conversation)
=========================================================================================
P1/P2 encodes an unattended multi-wave swarm "wave-barrier" loop into the autopilot SKILL so a
≥20-agent swarm can eventually run fully hands-off. Plan (revision 4):
docs/plans/2026-07-22-p1p2-unattended-swarm-wave-barrier-plan.md.

Design X (load-bearing): unattended runs push NO code to origin/<default>; workers WRITE+COMMIT
only; ALL cross-module integration + self-verification is deferred to per-wave assembly on the
local feature branch. The firebreak stays ACTIVE for the whole run — NO toggle/deactivation. The
per-wave blocking integrated gate lives inside the (TRUSTED) swarm-runner: contract-check (grep)
+ a pytest integrated import-smoke that (per §3.4) also boots create_app(). Implementing §1 is a
MANUAL work phase, not an autopilot run; the actual hands-off swarm is a separate later item (P4),
gated on the trust gate + explicit human go.

§0 is three BLOCKING verify-first spikes that must pass BEFORE any §1 SKILL/tool code:
- 0a — falsify the spec-only premise end-to-end (author-with-prior-wave-absent, then assemble +
  integrated gate). Ran: PASS, but see Finding 1 (proved only the NARROW import-resolution premise).
- 0b — TaskStop observability (prove-zero-live viable). Ran: PASS. Findings 2 came out of it.
- 0c — per-wave swarm-runner reuse is side-effect-clean. BUILT but NOT run; see Finding 4.

Spike artifacts already on disk:
- tools/spike_two_wave_setup.py, tools/spike_two_wave_importsmoke.py  (0a)
- tools/spike_per_wave_runner_setup.py                                (0c fixture builder)
- docs/reports/p1p2-spikes/0a-result.md, 0b-result.md, 0-summary.md
- docs/reports/p1p2-spikes/codex-0-review-handoff.md                  (the handoff Codex reviewed)

Hard invariants to preserve throughout:
- Firebreak stays ACTIVE (no toggle). No unattended CODE push to origin/<default>.
- Single-wave autopilot behavior byte-for-byte unchanged.
- Firebreak classifier: no `-m`/name carve-out; only the two approved tool-path additions;
  classifier suite must stay 282→284 (currently 282 baseline). Do not touch classifier logic.
- One gate architecture (§3.4); do not reintroduce a compileall/module-mode toggle.

=========================================================================================
CODEX VERDICT: NO-GO — findings (verbatim)
=========================================================================================
1. §0.0a proves only the narrow import-resolution premise. It does not test the plan's stated
   create_app() / app-context / teardown lifecycle seam in §3.4, so the recorded "Design X premise
   holds" conclusion is too broad.
2. §3.1 still does not clearly say whether orphaned detached child shells are in scope. The spike
   shows this can happen, so the plan needs an explicit policy.
3. "typecheck" is currently only an import-smoke substitution. The plan should not imply a real
   type-checker exists unless one is pinned.
4. §0c is still a synthetic base shape (spike-0c-base cut from current HEAD), so it does not yet
   faithfully exercise the real origin/<default> / original_branch ancestry shape.

CODEX FIX DIRECTIVES (verbatim):
1. Amend §0.0a and §3.4 so the plan is honest about what 0a proves. If the gate really must boot
   create_app() and exercise app-context/teardown, add or revise the spike so it tests that. If
   not, narrow the claim so 0a only proves import-resolution and write+commit-only authoring.
2. Amend §3.1 to say whether orphaned detached child shells are in scope. If they are in scope,
   add a concrete detection or containment step. If they are out of scope, state that explicitly.
3. Decide whether "typecheck" is a real gate or an import-smoke substitution. If it is real, pin a
   checker. If it is substitution only, rename the plan/report language so nobody reads it as
   actual type checking.
4. Rework or supplement 0c so it exercises a base/ancestry shape closer to the real
   origin/<default> and original_branch flow, not only a synthetic spike-0c-base cut from current
   HEAD.
5. After the edits, update the spike/review artifacts as needed, then run a second self-review of
   your own changes and report any remaining risks before considering §1.

=========================================================================================
RECOMMENDED RESOLUTIONS (from the prior session — verify with your own judgment, not gospel)
=========================================================================================
Finding 1 → STRENGTHEN the gate + spike (Codex option a), do NOT narrow. Rationale: §3.4 explicitly
says the import-smoke boots create_app(); and Run 083's REAL integration failures (harvest H3/H6/H9
in docs/reports/083/harvest-findings.md) were lifecycle seams — init_db() called without app-context,
SECRET_KEY validated before config, an unregistered teardown_appcontext. A bare import-smoke would
NOT catch these; narrowing §3.4 to import-only would gut the gate's whole value. So:
  - Augment tools/spike_two_wave_setup.py's fixture into a minimal Flask app: pkgspike/__init__.py
    with create_app() that calls init_db() requiring an app-context and registers
    teardown_appcontext(close_db) — mirroring H6/H3.
  - Have the integrated gate (tools/spike_two_wave_importsmoke.py) BOOT create_app() (and push an
    app-context) in addition to importing modules.
  - Demonstrate the gate FAILS on a lifecycle break (e.g., init_db() called bare → "working outside
    application context") and PASSES after the assembly-fix (`with app.app_context(): init_db()`).
    That proves the gate catches the H6/H3/H9 class, not just imports.
  - Update §3.4 wording to state the gate boots create_app() + exercises app-context/teardown, and
    rewrite §0.0a's over-broad "Design X premise holds" to the precise claim (write+commit-only
    authoring is sound AND the integrated gate catches import + lifecycle failures at assembly).
  - Re-run 0a and rewrite docs/reports/p1p2-spikes/0a-result.md.

Finding 2 → §3.1 EXPLICIT POLICY: orphaned detached child shells are OUT of scope for the
"prove-zero-live" gate (which proves the Agent TASK is terminal), declared as a residual, PLUS a
concrete containment for the one dangerous case. Rationale/wording to add:
  - (i) Assembly cherry-picks from the worker's COMMITTED branch head, not its live worktree — a
    post-terminal detached writer cannot alter the assembled INPUT unless it makes a git COMMIT.
  - (ii) A detached child executing code is invisible to the PreToolUse firebreak — this is the
    pre-existing declared F6 residual in .claude/hooks/firebreak-classify.py; this plan neither
    expands nor fixes F6.
  - (iii) CONTAINMENT (cheap, catches the only assembly-corrupting case): §3.1/§5 record
    worker_head_sha at the moment each worker is declared terminal; before assembly AND before
    wave-mode cleanup, re-read the branch head; a mismatch = a post-terminal commit by a detached
    writer → ABORT. Add this equality check to §7's verify_wave reject-set (worker_head_sha is
    already recorded there).
  Confirm 0b-result.md's nuances already align; update if needed.

Finding 3 → SUBSTITUTION ONLY (do not install a type-checker; none is warranted yet). Purge the word
"typecheck" from §0.0a, §3.4, and the reports; call it exactly "integrated import-smoke (import-time
cross-module name resolution — NOT static type checking; no type-checker is configured)". If a real
checker is ever wanted, that is a separate pinned addition, out of scope here.

Finding 4 → RESHAPE 0c to the real baseRef=fresh ancestry shape. Read
.claude/agents/swarm-runner.md (Step 3 cherry-pick base-divergence) and SKILL Step 9w.9.5 /
Step 10.5w (workers root on origin/<default>, NOT original_branch). Rework
tools/spike_per_wave_runner_setup.py so:
  - a local DEFAULT branch (e.g. `spike-default`) exists, optionally behind a local bare "origin"
    so `origin/spike-default` is a real ref (baseRef=fresh);
  - a FEATURE branch (`spike-feat`) is AHEAD of spike-default by ≥1 commit (original_branch);
  - worker branches root on `spike-default` tip (so merge-base(spike-feat, worker) == spike-default
    tip == the real cherry-pick base) — NOT on the feature HEAD;
  - swarm-runner is invoked twice with original_branch=spike-feat and the two disjoint worker sets.
  Then RUN 0c (fixture build → spawn swarm-runner ×2 fresh context each → verify: per-wave report
  isolation, both assembly branches cleaned up, no run-level state leak i.e. w2 summary references
  only w2 branches/bases, AND the cherry-pick base equals spike-default tip) → then --teardown.
  Write docs/reports/p1p2-spikes/0c-result.md. NOTE: spawning swarm-runner returns a bounded final
  STATUS line; do NOT call TaskOutput on a local_agent (it dumps the full transcript and floods
  context).

=========================================================================================
DEFINITION OF DONE (this session)
=========================================================================================
- Plan edited: §0.0a, §3.1, §3.4, and the typecheck language, plus the 0c spike design; bump
  frontmatter `revision: 5` with a one-line resolution-map row per finding.
- Spikes updated + RE-RUN: 0a (strengthened, boots create_app) and 0c (reshaped, real ancestry);
  0a/0c result reports rewritten; 0-summary.md updated.
- HANDOFF.md phase line updated to rev5 / §0 re-review pending.
- Second self-review of your own edits; report remaining risks.
- Produce a fresh Codex §0 re-review handoff (lead with "Work in /Users/alejandroguillen/
  Projects/sandbox" + branch + HEAD + ask). Commit + push. STOP. Do NOT start §1.

Preserve the four untracked user-owned files (.agents/, .codex/, AGENTS.md,
wfscale-identity-spike.mjs) — do not stage or modify them.
