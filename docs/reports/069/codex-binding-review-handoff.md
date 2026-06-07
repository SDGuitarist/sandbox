# Codex Binding Review Handoff — CPAA Event-Replay Simulator (Run 069)

**Review type:** MANUAL, human-driven (paste into Codex yourself — NOT `codex exec`).
**Why manual:** headless may use a weaker model and isn't truly independent (Claude orchestrates it).
**Gate:** this is the final binding review before autopilot-swarm launch. Convergence criterion =
Codex clean AND human finds zero P0s.

---

## Paste this into Codex

> You are doing a **final, binding pre-launch review** of a frozen swarm-build spec. 24 worker agents
> will build against it unattended, each seeing only its own slice — so the failure mode that matters is
> **cross-section contradiction**: two sections that are each internally consistent but produce
> incompatible bytes or behavior when two different agents implement them. Single-section review will not
> catch these. Do not restyle or nitpick; hunt for contradictions that would make two agents' outputs
> disagree.
>
> **File:** `docs/plans/2026-06-06-feat-cpaa-event-replay-simulator-plan.md` (the whole plan is the spec).
>
> Focus your hardest scrutiny on these three known P0-risk areas, cross-checking §3.2, §4, §8, §9, and §14
> against each other for each one:
>
> **P0-1 — Canonical hash byte recipe (§8 rule 8 / §3.2 D).** The determinism proof rests on every agent
> producing byte-identical serialization. Verify the recipe in §8.8 is fully determined with no degrees of
> freedom: table iteration order (`station_state, auction_state, environmental_state, system_state`);
> per-table `ORDER BY <pk> COLLATE BINARY ASC`; the framing bytes (`\x1f` count separator, `\x00` row
> separator, `\x1e` table-block join); the per-row `json.dumps(sort_keys=True, separators=(",",":"),
> ensure_ascii=False, allow_nan=False)`; REAL columns via shortest-round-trip `repr` (no `round`); SQL
> NULL → JSON null. Check the **exclusion list** (`replay_runs`, `events`, `anomalies`,
> `projection_snapshots`, every `*_at` column) is consistent with the actual columns declared in §4.2 —
> is there any projection column that is non-deterministic across runs (a timestamp, an autoincrement id)
> that the recipe fails to exclude? Confirm `last_heartbeat` (emitted verbatim, §4.4 sets it to
> `logical_ts`) cannot vary between two replays of the same corpus. Confirm `EMPTY_PROJECTION_HASH` and the
> golden hash are produced by code (`tools/compute_golden.py`) not hand-authored.
>
> **P0-2 — Run-lock atomicity + stale reaper (§3.2 B/B′/C, §9 Transaction Contracts).** Verify the lock is
> truly TOCTOU-free: single guarded `INSERT … SELECT … WHERE NOT EXISTS(status='RUNNING')` inside
> `BEGIN IMMEDIATE`, decision by `cursor.rowcount` (1=held, 0=409), with SELECT-then-UPDATE explicitly
> forbidden. Walk the 3-transaction sequence (T1 lock-acquire commits so the 409 path can read the RUNNING
> row from another connection; T2 reset→apply→snapshot→hash→mark_complete_pass; T3 exception →
> mark_aborted). Does the reaper (`reap_stale_runs`, ABORTs RUNNING rows with `started_at < now-15min`)
> compose correctly with the lock in BOTH the replay route (reap then start_run in same T1) and the ingest
> route (reap then active_run read; ingest creates no run)? Is there any interleaving where a crashed run
> bricks the lock, or where the reaper aborts a live run? Confirm the `replay_runs` CHECK constraints in
> §4.2 (`status='RUNNING' ⇒ started_at NOT NULL`; `status='COMPLETE_PASS' ⇒ projection_hash NOT NULL`)
> match what the §9 write functions actually set.
>
> **P0-3 — live-hash writer assignment & shadow isolation (§8 rule 10, §9 Data Ownership, frozen #3).**
> `replay_engine` captures `live_hash_pre` (via live_guard) before reset and `live_hash_post` after apply,
> and stores both via `mark_complete_pass`; the validator only READS them. Verify exactly one writer owns
> `replay_runs` for these columns and there is no path where the validator or any other module writes
> `live_hash_*`. Confirm the isolation invariant holds end-to-end: `open_live_ro` uses
> `file:{path}?mode=ro&immutable=1`, no writable `live.db` handle exists anywhere, and "live unchanged" is
> provable as `live_hash_pre == live_hash_post`. Check §9's one-writer-per-table table against §8 rule 10's
> reset-via-owner rule: does `replay_engine` calling each `reset_<domain>(conn)` actually preserve
> one-writer-per-table, or does any agent end up writing a table it doesn't own?
>
> Also do a fast pass for: (a) any §5 export name / §6 wiring import path / §9 writer that disagrees across
> sections; (b) any §14 EARS acceptance test that asserts behavior no section actually specifies; (c)
> scalar return types used without a usage example (the Run-068-class `create_project() -> int` mismatch).
>
> Return a verdict: **GO** (zero P0 cross-section contradictions) or **NO-GO** with each P0 as
> {section refs, the contradiction, the concrete byte/behavior divergence it causes, the minimal fix}.
> Rank anything you find P0 / P1 / P2. Be specific and adversarial; this is the last gate before 24 agents
> build on it.

---

## After Codex returns

- **GO + human zero-P0:** convergence met → proceed to explicit human GO → launch autopilot-swarm.
- **NO-GO:** bring each finding back here; fix the plan; re-run this handoff (loop until clean).
- Optional before launch: run the plan through NotebookLM for the external-data cross-ref step
  (corpus `cpaa-shadow-lab/generate_scenario.py` vs §4.4 taxonomy — already reconciled once, P0 caught).
