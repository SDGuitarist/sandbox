Work in /Users/alejandroguillen/Projects/sandbox
Branch: feat/p1p2-unattended-swarm-wave-barrier
HEAD:   e5e07bb  (resolved-work commit; this handoff doc sits one commit on top — review the branch tip)

THE ASK: this is a §0 spike-review RE-REVIEW. Your prior §0 review returned NO-GO with 4 findings.
Decide GO / NO-GO on whether the 4 findings are genuinely resolved (not merely reworded) and
whether the work phase may now proceed to §1. Do NOT write code — this is a spike/plan review.

Plan:   docs/plans/2026-07-22-p1p2-unattended-swarm-wave-barrier-plan.md  (now revision 5; §0)
The rev5 resolution map is the plan's "Codex §0 spike-review resolution map (revision 5)" table.

WHAT §0 IS. The plan encodes an unattended multi-wave swarm "wave-barrier" loop. Before ANY
SKILL/tool deliverable is written, §0 requires three BLOCKING verify-first spikes. A spike failure
that invalidates dependent waves is a STOP-for-plan-revision, NOT a silent scope cut. All three §0
spikes now PASS (0a strengthened, 0b, 0c reshaped + RUN).

FILES TO OPEN (do not trust this summary):
- tools/spike_two_wave_setup.py            — 0a harness (now a minimal Flask app; boots create_app)
- tools/spike_two_wave_importsmoke.py      — 0a integrated gate (import-smoke + create_app() boot)
- tools/spike_per_wave_runner_setup.py     — 0c fixture builder (real ancestry shape; build/--teardown)
- tools/spike_per_wave_runner_check.py     — 0c adjudicator (10 checks)
- docs/reports/p1p2-spikes/0a-result.md    — recorded 0a outcome (STATUS: PASS)
- docs/reports/p1p2-spikes/0b-result.md    — recorded 0b outcome (+ §3.1 policy alignment note)
- docs/reports/p1p2-spikes/0c-result.md    — recorded 0c outcome (STATUS: PASS)
- docs/reports/p1p2-spikes/0-summary.md    — §0 rollup (STATUS: COMPLETE)
Plan sections touched: frontmatter (revision 5), the rev5 resolution map, §0.0a, §0.0c, §3.1, §3.2,
§3.4, §5 (phase table + steps 6/8b), §6 (roster schema), §7 (reject-set).

HOW EACH FINDING WAS RESOLVED — ADJUDICATE each is genuinely closed:

1. (0a proved only the narrow import-resolution premise; did not exercise the §3.4
   create_app()/app-context/teardown seam; recorded conclusion too broad.)
   RESOLUTION: STRENGTHENED, not narrowed. 0a's fixture is now a minimal Flask app —
   pkgspike/database.py (get_db/query/init_db/close_db, all requiring an app context),
   pkgspike/factory.py (create_app importing Wave-1 symbols, registering a blueprint + a
   teardown_appcontext handler + calling init_db), pkgspike/routes.py (blueprint importing query).
   The Wave-2 worker authors a create_app() that calls init_db() BARE (a latent bug it cannot
   discover with Wave-1 absent — the Design-X condition). At assembly the integrated gate BOOTS
   create_app(): the broken tree FAILS with the genuine `RuntimeError: Working outside of
   application context` (the H6/H3 lifecycle class — a bare import-smoke would have PASSED), then
   the one inline assembly-fix (`with app.app_context(): init_db()`) makes the gate PASS (6 passed).
   §3.4 now states the gate boots create_app() + exercises app-context/teardown; §0.0a's
   conclusion is narrowed to exactly (A) write+commit-only authoring is sound AND (B) the gate
   catches import + lifecycle failures at assembly. CHECK: is 0a's PASS/FAIL logic genuinely
   falsifiable (would the broken tree PASSING be reported as FAIL)? Is the "caught the lifecycle
   seam" signal keyed on pytest's real error-marker line, not a docstring echo? Is the §0.0a/§3.4
   claim now exactly what the spike proves — no broader?

2. (§3.1 did not say whether orphaned detached child shells are in scope; 0b shows they can happen.)
   RESOLUTION: §3.1 now states an EXPLICIT policy — orphaned detached child shells are OUT of scope
   for the prove-zero-live gate (which proves the Agent TASK is terminal), declared as a residual
   keyed to the pre-existing firebreak F6 residual (this plan neither expands nor fixes F6), with
   two stated reasons: (i) assembly cherry-picks from each worker's COMMITTED branch head, never a
   live worktree, so a post-terminal writer cannot alter the assembled INPUT unless it makes a git
   COMMIT; (ii) a detached child's tool calls are invisible to PreToolUse (F6). CONTAINMENT for the
   one assembly-corrupting case (a post-terminal COMMIT advancing a worker branch): record
   `terminal_head_sha` at the terminal instant (§5 phase `workers_terminal` + §6 roster), re-read
   the live branch head before assembly (§5 step 8b) AND require equality in the §7
   `verify_wave --wave K` reject-set (roster `terminal_head_sha` == worker_deltas `worker_head_sha`
   == live branch head; any mismatch ⇒ FAIL). CHECK: is the policy explicit (in-scope vs
   out-of-scope stated)? Is the containment sound and does it actually catch the only
   assembly-corrupting case? Is the equality wired consistently across §5/§6/§7?

3. ("typecheck" is only an import-smoke substitution; the plan should not imply a real type-checker
   exists.) RESOLUTION: SUBSTITUTION ONLY — "typecheck" purged as a gate label. No type-checker is
   installed or pinned. §0.0a/§3.4/reports call the gate exactly an "integrated import-smoke
   (import-time cross-module name resolution + create_app() boot — NOT static type checking; no
   type-checker is configured)". The 0a report records `typecheck: N/A` and never as a passed gate.
   (Remaining "typecheck" tokens are only in prohibition/rejection lists — §4 worker rule 11
   prohibits workers RUNNING package-wide typechecks; the §4 module-mode-gate validator REJECTS a
   plan that prescribes a package-wide typecheck gate. Neither implies a checker exists.) CHECK: is
   any surviving "typecheck" usage only prohibition/rejection, never a claimed real gate?

4. (0c is a synthetic spike-0c-base cut from current HEAD; does not exercise the real
   origin/<default> / original_branch ancestry.) RESOLUTION: 0c RESHAPED + RUN. New fixture:
   `spike-default` (DEFAULT; pushed to a local bare `spikeorigin` so `spikeorigin/spike-default` is
   a real remote-tracking ref — baseRef=fresh; the real GitHub origin is NEVER touched),
   `spike-feat` AHEAD of default by 1 commit (original_branch), and two disjoint COMPLETED worker
   sets rooted on `spike-default` tip. Verified before the run: merge-base(spike-feat, worker) ==
   spike-default tip (033e191) != spike-feat HEAD (6a4a084) — genuine base-divergence. The real
   swarm-runner agent was spawned TWICE (fresh context, original_branch=spike-feat); both returned
   STATUS: PASS. The adjudicator's 10 checks all PASS: report isolation, complete cleanup (all
   swarm-SPIKE-* branches + worktrees gone), no run-level leak (each summary references only its own
   wave), AND every recorded cherry-pick base == spike-default tip in BOTH summaries across the two
   sequential reuses (w2 ran after spike-feat had already advanced, yet its base is still the
   default tip). Evidence: docs/reports/p1p2-spikes/0c-result.md. CHECK: does the reshaped fixture
   faithfully exercise the real baseRef=fresh / original_branch-ahead relationship? Is there any
   leak a real run would hit that this fixture would still miss?

KNOWN RESIDUALS (I disclose these; judge whether any is a NO-GO):
- 0a proves the gate MECHANISM (boot create_app) catches the app-context/teardown class on a
  representative case; it does not exhaustively prove every lifecycle failure mode. §9 item 3
  already flags the import-smoke substitution as the load-bearing assumption.
- 0a's broken factory is synthesized by the setup script (not authored by a live LLM worker); it
  proves gate mechanics + that write+commit-only is possible, not real-agent authoring behavior.
- 0c ran under an ungoverned firebreak (no sentinel), so it did NOT observe the classifier live;
  swarm-runner's trusted-identity GREEN behavior is asserted from the §8 classifier suite
  (282→284), not observed in 0c. Live governed multi-wave firebreak observation is P4's job.
- The terminal_head_sha capture is a new §1 implementation obligation (not yet built — §1 has not
  started); the plan specifies it consistently.

Return: GO or NO-GO. For NO-GO, list each unresolved finding with the exact plan/spike section and
what is still missing to make it PASS.
