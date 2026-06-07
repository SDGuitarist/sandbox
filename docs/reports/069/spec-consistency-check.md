STATUS: FAIL -- 4 contradictions found

# Pre-Swarm Spec Consistency Check

**Plan:** docs/plans/2026-06-06-feat-cpaa-event-replay-simulator-plan.md
**Checked:** 2026-06-06
**Checker:** spec-consistency-checker agent (manual invocation, pre-swarm gate)

## Results

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| 1 | Schema vs EARS / frozen decision | §4.2 anomalies.kind enum lists `dup_exact` as storable kind | §3.1 frozen #1 + §14 EARS line 409: "no anomaly" for identical-payload dup | FAIL | Schema allows `dup_exact` anomaly rows; behavioral spec prohibits them |
| 2 | Schema field vs EARS counter reference | §4.2 schema: no counter columns on any table | §14 EARS + verification: references `dup_exact` counter and `dup_conflict` counter | FAIL | Where the counts live is undefined — no `dup_exact_count`/`dup_conflict_count` column in `replay_runs` or any table |
| 3 | Route path in dir-tree comment vs Export Names | §2 replay_routes.py comment: `POST /replay` | §5 Export Names endpoint table: `replay.start POST /replay/run` | FAIL | Comment omits the `/run` suffix; agent C5 will read the comment as the route path |
| 4 | Export Names completeness vs Data Ownership + Wiring | §9 names proj_financial.py and proj_env_system.py as single writers; §6 wiring shows `apply_<domain>` with only `apply_station` named | §5 Export Names table: no entry for `apply_financial` or `apply_env_system` (or equivalent) | FAIL | Agents C3-proj-financial and C4-proj-envsys have no canonical function-name contract |
| 5 | Parameter naming: wiring vs Export Names | §6 wiring signature param: `type` (4th positional) | §5 Export Names signature param: `event_type` | WARN | `type` shadows Python built-in and differs from canonical name; not a hard mismatch but risks incorrect import usage |

## Detailed Analysis

### Finding 1 (P0): `dup_exact` anomaly kind contradicts behavioral spec

**§4.2 schema** (line 206):
```
kind TEXT NOT NULL, -- dup_conflict|dup_exact|unknown_key|malformed_payload
```
This comment treats `dup_exact` as a valid value that CAN be stored in the `anomalies` table.

**§3.1 frozen #1** (lines 113-115):
> "A duplicate key is silently ignored + counted; the same key with a **different** payload is
> ignored and logged as an anomaly (never overwrites)."

Only the different-payload case → anomaly. Identical-payload → silently ignored + counted. No anomaly record.

**§14 EARS** (line 409):
> "WHEN an event is appended with an existing key + IDENTICAL payload THE SYSTEM SHALL ignore it
> and increment the `dup_exact` counter (**no anomaly**)."

"No anomaly" is explicit. The schema including `dup_exact` as an anomaly kind directly contradicts this.

**Fix required:** Remove `dup_exact` from the `anomalies.kind` enum comment in §4.2. The kind list should be `dup_conflict|unknown_key|malformed_payload` only.

---

### Finding 2 (P0): `dup_exact` and `dup_conflict` counters have no schema column

§14 EARS and §14 verification commands (`test_dedup.py — frozen #1 + dup_exact/dup_conflict counters`) reference counters for both `dup_exact` and `dup_conflict`. These are read-level values that tests will query.

The `anomalies` table can count `dup_conflict` rows via `SELECT COUNT(*) WHERE kind='dup_conflict'`, but `dup_exact` has no anomaly row (Finding 1). There is also no `dup_exact_count` column in `replay_runs` or any other table. The schema gives `replay_runs.events_applied` (a count), but no dedup counters.

Agents writing `ingest.py` (B2), `event_models.py` (A6), and `tests/test_dedup.py` (F1) will each need to know where these counts are persisted. Currently undefined.

**Fix required:** Either (a) add counter columns to `replay_runs` (e.g., `dup_exact_count INTEGER DEFAULT 0, dup_conflict_count INTEGER DEFAULT 0`) with a note about who increments them, or (b) define that `dup_conflict` count is derived from `SELECT COUNT(*) FROM anomalies WHERE kind='dup_conflict' AND run_id=?` and `dup_exact` is an in-memory/returned-by-ingest counter only (not persisted). Either way, the schema and §9 data ownership must be updated to reflect the decision.

---

### Finding 3 (P1): `replay_routes.py` directory comment omits `/run` from POST path

**§2 directory tree** (line 84):
```
replay_routes.py  # bp: replay (POST /replay, GET /run/<run_id>, GET /projection/at)
```

**§5 Export Names** endpoint table (lines 263-267):
```
replay.start     | POST | /replay/run         | replay
replay.projection_at | GET | /replay/projection/at | replay
replay.run_detail   | GET | /replay/run/<run_id>  | replay
```

The comment says `POST /replay`. With the blueprint prefix `/replay`, a route registered as `/` inside the blueprint resolves to `/replay/` (the blueprint root). The Export Names table says the full path is `/replay/run`, meaning the route inside the blueprint is `/run`.

The comment is the primary human-readable spec that agent C5-replay-routes will use for the file header. As written it specifies the wrong path. The GET routes in the comment (`GET /run/<run_id>`, `GET /projection/at`) are relative-within-blueprint paths and correctly resolve to the Export Names full paths — but the POST route says `/replay` (not `/run` relative).

**Fix required:** Change the comment to `bp: replay (POST /run, GET /run/<run_id>, GET /projection/at)` or use full paths consistently: `(POST /replay/run, GET /replay/run/<run_id>, GET /replay/projection/at)`.

---

### Finding 4 (P1): `apply_financial` and `apply_env_system` function names absent from Export Names and Wiring

**§9 Data Ownership** (lines 353-355):
- `station_state` → writer: `proj_station.py`
- `financial_state` → writer: `proj_financial.py`
- `environmental_state / system_state` → writer: `proj_env_system.py`

**§6 Wiring Table** (line 281):
```
replay_engine.py | proj_station/financial/env_system | apply_<domain>(conn, row) | from app.proj_station import apply_station | dispatch
```
The import path names only `apply_station`. The functions for the financial and env/system projection handlers are called `apply_<domain>` (a placeholder).

**§5 Export Names** (lines 238-250): No entry for `apply_financial`, `apply_env_system`, or any function from `proj_financial.py` or `proj_env_system.py`.

Agents C3-proj-financial and C4-proj-envsys will invent their own function names. When replay_engine.py (agent C1) imports them, the names will not match unless the agents happen to guess the same convention.

**Fix required:** Add explicit Export Names entries:
- `apply_station(conn, row)` | fn → None | proj_station.py | replay_engine.py
- `apply_financial(conn, row)` | fn → None | proj_financial.py | replay_engine.py
- `apply_env_system(conn, row)` | fn → None | proj_env_system.py | replay_engine.py

And update §6 wiring to list all three import names explicitly.

---

### Finding 5 (WARN): `type` parameter abbreviation in §6 wiring

**§6 wiring** append_event signature: `append_event(conn, k, ts, type, payload, source)`
**§5 Export Names**: `append_event(conn, idempotency_key, logical_ts, event_type, payload, source)`

The 4th positional parameter is named `type` in §6 (abbreviated) vs `event_type` in §5 (canonical). `type` is a Python built-in; using it as a parameter name is a code smell and differs from the canonical name declared in §5.

Not a hard cross-section contradiction (positions match, intent is clear), but agents reading §6 as their primary reference may write `def append_event(conn, k, ts, type, payload, source)` in code, shadowing the built-in.

**Fix suggested:** Change §6 wiring to use the canonical param names: `append_event(conn, idempotency_key, logical_ts, event_type, payload, source) -> int`.

---

## Consistency Checks That PASSED

| Check | Result |
|-------|--------|
| Timestamp format `YYYY-MM-DD HH:MM:SS` across §3.2.E, §4.1, §4.2, §7, §8 rule 4, §14 smoke table `t=2026-06-15 19:00:00` | PASS — identical format, space separator, never T-separator |
| Run-state enum `{PENDING,RUNNING,COMPLETE_PASS,NON_DETERMINISTIC,ABORTED}` across §3.2.A, §2 dir comment, §4.2 SQL comment, §8, §9, §14 EARS | PASS — all five tokens match exactly, same spelling everywhere |
| Anomaly kinds `dup_conflict`, `unknown_key`, `malformed_payload` across §4.2, §7, §8 rules 5-6, §14 EARS | PASS — three kinds consistent (subject to Finding 1 removing `dup_exact` from the schema kind list) |
| Routes in smoke table vs Export Names endpoint table | PASS — all 8 smoke rows map to exact Export Names entries |
| `record_anomaly` consumers: §3.2.F says ingest+replay+validator; §5 "Used By" says ingest, replay_engine, validator; §6 wiring shows all three | PASS — fully consistent |
| `canonical_hash` ownership: §3.2.E says serialization.py; §5 "Defined By" says serialization.py; §6 says `from app.serialization import canonical_hash` | PASS |
| `start_run`/`set_run_status` ownership: §8 rule 7 says replay_engine via run_models; §5 Defined By run_models.py; §6 import `from app.run_models import start_run, set_run_status` | PASS |
| Anomaly table single-writer: §3.2.F, §4.2 comment, §5 anomaly_models.py, §9 data ownership — all name `anomaly_models.py` as the sole writer | PASS |
| Shadow reset table list: §3.2.C names `station_state, financial_state, environmental_state, system_state`; §4.2 schema defines exactly those 4 tables as projection tables | PASS |
| `events_at_time(conn, t)` across §5 and §6 | PASS — exact match |
| `live_content_hash(ro_conn)` across §5 and §6 | PASS — exact match |
| `record_determinism(conn, run_a, run_b, match, diffs)` across §5 and §6 | PASS — exact match |
| Authorization matrix routes vs Export Names paths | PASS — all auth-gated routes appear in Export Names |

## Summary

- **Total checks:** 17
- **PASS:** 12
- **FAIL:** 4 (2 are P0, 2 are P1)
- **WARN:** 1
- **N/A (section absent):** 0

## Required Fixes Before Stage-2 Launch

Priority order:

1. **(P0) §4.2 anomalies.kind comment** — remove `dup_exact` from the kind list. List becomes: `dup_conflict|unknown_key|malformed_payload`
2. **(P0) Define `dup_exact`/`dup_conflict` counter persistence** — add counter columns to `replay_runs` schema (preferred) OR add a prose decision in §9 that `dup_conflict` count = `COUNT(*) FROM anomalies WHERE kind='dup_conflict'` and `dup_exact` count is in-memory/returned-by-function-only. Update §14 EARS to say how tests assert the counter value.
3. **(P1) §2 replay_routes.py comment** — fix `POST /replay` → `POST /run` (relative) or `POST /replay/run` (absolute).
4. **(P1) §5 Export Names + §6 Wiring** — add explicit entries for `apply_financial(conn, row)` and `apply_env_system(conn, row)`.
5. **(WARN) §6 wiring append_event param** — rename `type` → `event_type` to match §5 canonical name.
