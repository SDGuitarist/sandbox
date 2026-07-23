Work in /Users/alejandroguillen/Projects/sandbox
Branch: feat/p1p2-unattended-swarm-wave-barrier
HEAD:   d1cf7b1  (spike evidence + this handoff committed; 3730c2d pushed)

THE ASK: review the §0 VERIFY-FIRST SPIKE results (and their code) and return a GO / NO-GO
decision on whether §0 is genuinely satisfied and whether the work phase may proceed to §1.

Plan:   docs/plans/2026-07-22-p1p2-unattended-swarm-wave-barrier-plan.md  (revision 4; §0)

WHAT §0 IS. The plan encodes an unattended multi-wave swarm "wave-barrier" loop. Before ANY
SKILL/tool deliverable is written, §0 requires three BLOCKING verify-first spikes whose outcomes
are recorded. A spike failure that invalidates dependent waves is a STOP-for-plan-revision, NOT a
silent scope cut. I (Claude) have run 0a and 0b (PASS) and built but NOT run 0c. Your job: decide
whether the spikes actually prove what they claim, whether my recorded conclusions are sound, and
GO/NO-GO on proceeding.

FILES TO REVIEW (open them; do not trust this summary):
- tools/spike_two_wave_setup.py            — 0a harness (builds fixture, runs it, writes report)
- tools/spike_two_wave_importsmoke.py      — 0a integrated import-smoke (pytest)
- tools/spike_per_wave_runner_setup.py     — 0c fixture builder (build/--teardown), NOT yet run
- docs/reports/p1p2-spikes/0a-result.md    — recorded 0a outcome (STATUS: PASS)
- docs/reports/p1p2-spikes/0b-result.md    — recorded 0b outcome (STATUS: PASS + nuances)
- docs/reports/p1p2-spikes/0-summary.md    — §0 rollup
Plan §0 is lines ~49-174 of the plan; §3.1 (prove-zero-live) and §3.4 (gate architecture) are the
sections the spikes feed.

WHAT THE SPIKES DID + MY CONCLUSIONS.

0a — falsify the spec-only premise, end-to-end. In a throwaway git repo: a Wave-2 worker rooted
on a base that carries ONLY the spec + an empty package (Wave-1's file `pkgspike/database.py`
ABSENT) authored+committed `pkgspike/routes.py` containing `from pkgspike.database import query`.
Recorded (rc 0 = success):
  - author+commit with Wave-1 absent: rc 0  (PASS — worker can write from export NAMES)
  - `python -m compileall routes.py` (absent): rc 0 (syntax only, no import — expected)
  - `python -c "import pkgspike.routes"` (absent): rc 1 ModuleNotFoundError (EXPECTED — confirms
    workers must be write+commit-only)
Then cherry-pick-assembled BOTH waves and ran the integrated gate on the merged tree:
  - `python -m compileall pkgspike`: rc 0
  - pytest import-smoke (imports every pkgspike module incl. routes→database): 4 passed
My conclusion: Design X premise HOLDS — cross-module self-verification is correctly deferrable to
per-wave assembly. Env pinned: .venv/bin/python 3.14.6, .venv/bin/pytest. No mypy/pyright in .venv
→ "typecheck" is substituted by the import-smoke (a strict superset of compileall) and recorded
`N/A (substituted)`.

0b — TaskStop observability. Spawned a background worker Agent running a FOREGROUND
`ping -c 180 127.0.0.1` (keeps the agent's turn alive), confirmed status `running`, called
`TaskStop`, observed status `running`→`killed` immediately. My conclusion: the §3.1 prove-zero-live
gate is VIABLE via TaskStop + the killed/completion signal. NUANCES I recorded and folded back:
  (1) `TaskList` (team list) does NOT track background Agents (returned "No tasks found" while an
      agent was live) → §3.1/§5 must enumerate via the recorded roster task_ids + completion
      notifications, NOT via TaskList.
  (2) A worker told to `sleep 200` BACKGROUNDED it (foreground sleep is blocked) and the AGENT
      then self-reported `completed` at ~12s while the detached child `sleep` kept running →
      "terminal" is about the Agent task; a completed agent CAN leave a detached child shell.
  (3) `TaskOutput` on a local_agent returns the full JSONL transcript (context flood) — status
      must come from TaskStop's return + the completion/killed notification.

0c — per-wave swarm-runner reuse. NOT YET RUN (deferred to a fresh context: it spawns the real
swarm-runner twice + mutates repo branches, and this session's context was loaded). Fixture builder
is written and pinned: a throwaway `spike-0c-base` branch + two disjoint COMPLETED worker-branch
sets under uniquely-namespaced files, invoked via swarm-runner twice with distinct
reports_dir/assembly_branch. PASS = per-wave report isolation + both assembly branches cleaned up +
no run-level state leak (w2 summary references only w2).

SPECIFICALLY ADJUDICATE (be adversarial; I have flagged my own doubts — confirm or refute them):
1. 0a faithfulness: Is this a genuine falsification? Would the harness's PASS/FAIL logic actually
   report FAIL if the premise were false (i.e., if author+commit REQUIRED the prior file, or the
   integrated tree could not import)? Check tools/spike_two_wave_setup.py's `ok()`/verdict logic
   and that Wave-1 is truly absent in the Wave-2 worktree.
2. 0a coverage gap (MY concern): the fixture is 2 trivial modules with NO Flask app / create_app /
   teardown registration. The plan §3.4 integrated import-smoke also BOOTS create_app(). Run 083's
   real integration failures (H3/H6/H9) were framework-lifecycle seams (init_db app-context,
   SECRET_KEY-before-config, unregistered teardown) that a bare import-smoke would NOT catch. Does
   0a therefore under-prove the gate? Should the §3.4 gate spec (and a follow-up spike) explicitly
   require the import-smoke to boot create_app() and exercise app-context, so it catches the
   lifecycle class — or is import-resolution enough for the §0 premise (with lifecycle deferred to
   the §1 swarm-runner gate design)?
3. typecheck substitution: is recording typecheck as N/A-substituted-by-import-smoke acceptable,
   or must a real type-checker (pyright/mypy) be installed and pinned for the gate?
4. 0b soundness + a possible PLAN GAP (MY concern): §3.1 proves the Agent TASK is terminal, but 0b
   shows a completed worker can leave a DETACHED background child that the orchestrator never
   tracks (not a worker branch author, but potentially still doing outward I/O). Does §3.1's
   "prove zero live workers" need to also account for orphaned detached children (e.g. the
   firebreak already governs their tool calls at spawn, but a raw backgrounded shell inside a
   worktree is outside PreToolUse)? Is this a NO-GO gap, a documented residual, or out of scope?
5. 0c design adequacy: does branching the spike workers off `spike-0c-base` (instead of
   origin/master, the real baseRef) weaken the reuse-cleanliness test? Is running swarm-runner
   against a throwaway `original_branch=spike-0c-base` a faithful stand-in? What exact leak would
   this fixture FAIL to detect that a real run would hit?
6. GO/NO-GO: Given 0a PASS and 0b PASS (with nuances), and 0c ready-but-unrun — may the work phase
   proceed to §1 deliverables AFTER 0c passes, or do items 2/4 above require a plan revision first?

Return: GO or NO-GO, with each of items 1-6 addressed explicitly. If NO-GO, name the exact spike or
plan section to fix and what would make it PASS. Do NOT write code — this is a spike/plan review.
