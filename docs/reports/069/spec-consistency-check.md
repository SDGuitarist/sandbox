STATUS: PASS

# Pre-Swarm Spec Consistency Check

**Plan:** docs/plans/2026-06-06-feat-cpaa-event-replay-simulator-plan.md
**Checked:** 2026-06-07
**Checker:** spec-consistency-checker (Stage-2 automated re-confirmation; spec is CONVERGED post Codex GO x2 + human zero-P0)

## Results

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| 1 | Schema vs Route | `replay_runs.run_id TEXT` (§4.2) | route param `<run_id>` (§5 blueprint table, §7) | PASS | Names match; `^[0-9a-f]{8}$` regex consistent with `uuid4().hex[:8]` (§8 rule 15) |
| 2 | Schema vs Route | `determinism_results.id INTEGER` (§4.2) | route param `<int:result_id>` (§5, §7); `record_determinism -> int # returns result_id` (§5) | PASS | Param name `result_id` intentionally differs from column `id`; `record_determinism` docstring explicitly names the returned value `result_id`; not contradictory |
| 3 | Schema vs Route | `determinism_results.run_a`, `run_b` (§4.2) | POST body params `run_a`, `run_b` in §7 validation | PASS | Exact name match |
| 4 | Schema vs Route | `dedup_counters.kind CHECK (kind IN ('dup_exact','dup_conflict'))` (§4.2) | `anomalies.kind CHECK (kind IN ('dup_conflict','unknown_key','malformed_payload'))` (§4.2) | PASS | `dup_exact` absent from anomalies CHECK; `dup_exact` only goes to dedup_counters (no anomaly); consistent with §3.1 frozen #1, §8 rule 9, §14 EARS "no anomaly" for identical-payload dup |
| 5 | Schema vs Route | `dedup_counters` table (§4.2) | §14 EARS/verification: `test_dedup.py — dedup_counters dup_exact/dup_conflict` | PASS | Dedicated `dedup_counters` table with `kind` PK correctly stores both counter kinds; tests can query `SELECT count FROM dedup_counters WHERE kind='dup_exact'` |
| 6 | SQL Types vs App | `replay_runs.run_id TEXT` | `start_run -> tuple[str, bool]` (§5) | PASS | str ↔ TEXT |
| 7 | SQL Types vs App | `replay_runs.events_applied INTEGER NOT NULL DEFAULT 0` | `mark_complete_pass(..., events_applied, ...)` (§5, §9) | PASS | int ↔ INTEGER |
| 8 | SQL Types vs App | `replay_runs.reset_done INTEGER NOT NULL DEFAULT 0` | mark_complete_pass sets reset_done=1 internally (§3.2 C, §9); no caller param | PASS | Boolean int; always set to 1 by COMPLETE_PASS path; consistent across §3.2, §9, §14 |
| 9 | SQL Types vs App | `replay_runs.status TEXT CHECK (status IN ('PENDING','RUNNING','COMPLETE_PASS','ABORTED'))` | pinned A: `status ∈ {PENDING,RUNNING,COMPLETE_PASS,ABORTED}` (§3.2); `RUN_STATES` constant (§2) | PASS | 4-state enum identical in schema CHECK and pinned decision; NON_DETERMINISTIC correctly absent |
| 10 | SQL Types vs App | `determinism_results.match INTEGER CHECK (match IN (0,1))` | `record_determinism(..., match: int, ...)` (§5) | PASS | int ↔ INTEGER; 0/1 values consistent |
| 11 | SQL Types vs App | `station_state.weight_kg REAL`, `temp_c REAL`; `environmental_state` REAL cols | §8 rule 8: REAL columns use `json.dumps` shortest-round-trip repr (no round) | PASS | REAL type flagged for special serialization treatment; consistent |
| 12 | SQL Types vs App | `station_state.sales_total_cents INTEGER NOT NULL DEFAULT 0` | §4.4: `amount_cents (int)`, additive; §8 rule 7: present-None = no-op for NOT NULL additive counters | PASS | Type, nullability, and additive semantics consistent across schema and apply rules |
| 13 | SQL Types vs App | `auction_state.bid_high_cents INTEGER NOT NULL DEFAULT 0`, `bid_count INTEGER NOT NULL DEFAULT 0` | §4.4: `amount_cents (int)`, MAX/+=; present-None = no-op | PASS | Consistent |
| 14 | Route Methods vs Route Table | Blueprint table §5 (10 routes) | §7 Input Validation Prescriptions | PASS | All 10 routes appear in both sections with matching methods and paths |
| 15 | Route Methods vs Route Table | Blueprint table §5 | §10 Authorization Matrix | PASS | All 10 routes classified; 5 public read/auth, 3 mutating POST = login_required; no route missing from matrix |
| 16 | Route Methods vs Route Table | Blueprint table §5 | §8 rule 13 nav links | PASS | Nav lists 5 targets (dashboard.index, dashboard.runs, replay.start, ingest.run_ingest, validate.run); all exist in blueprint table |
| 17 | Route Methods vs Route Table | Blueprint table §5 | §14 smoke table | PASS | All smoke rows map to declared routes; methods match; 400/404/409 paths covered |
| 18 | Export Names vs Import | `get_db(immediate=False)` / `open_live_ro(path)` defined in db.py (§5) | `from app.db import get_db, open_live_ro` (§6) | PASS | Exact name and signature match |
| 19 | Export Names vs Import | `canonical_hash(conn) -> str` in serialization.py (§5) | §6 wiring: replay_engine and validator; "respective imports" row | PASS | Name, return type, and owner consistent |
| 20 | Export Names vs Import | `append_event(conn, idempotency_key, logical_ts, event_type, payload_canonical, source) -> int` (§5) | `from app.event_models import append_event` (§6) | PASS | Name and positional params match; §6 abbreviates some param names in the wiring row but §5 is the canonical signature |
| 21 | Export Names vs Import | `get_events(conn)`, `events_at_time(conn, t)` in event_models.py (§5) | §6 wiring table | PASS | Names and signatures match across both sections |
| 22 | Export Names vs Import | `record_anomaly(conn, run_id: str\|None, kind, idempotency_key, detail) -> None` (§5) | §6 `record_anomaly(conn, run_id=None, ...)` | PASS | Minor style diff (default shown in §6, type annotation in §5); not a contradiction; both indicate run_id is optional/nullable |
| 23 | Export Names vs Import | `start_run`, `mark_complete_pass`, `mark_aborted`, `reap_stale_runs`, `active_run` in run_models.py (§5) | `from app.run_models import start_run, mark_complete_pass, mark_aborted, reap_stale_runs` (§6 replay_engine row); `from app.run_models import reap_stale_runs, active_run` (§6 ingest_routes row) | PASS | All 5 function names match exactly across §5 and §6 |
| 24 | Export Names vs Import | `write_snapshot(conn, run_id)`, `read_snapshot(conn, run_id)` in snapshot_models.py (§5) | §6 wiring: replay_engine consumes write_snapshot; validator consumes read_snapshot | PASS | Names, signatures, and consumer assignments consistent |
| 25 | Export Names vs Import | `apply_station/reset_station`, `apply_auction/reset_auction`, `apply_environmental/reset_environmental`, `apply_system/reset_system` (§5) | §6 wiring: `from app.proj_station import apply_station, reset_station` (×4 pattern) | PASS | All 8 function names explicit in §5; §6 names proj_station explicitly and uses pattern notation (×4); no ambiguity since §5 names all 4 modules |
| 26 | Export Names vs Import | `build_projection_at(conn, t: str) -> dict` in replay_engine.py (§5) | `from app.replay_engine import build_projection_at` (§6) | PASS | Exact name, signature, and owner match |
| 27 | Export Names vs Import | `live_content_hash(ro_conn) -> str` in live_guard.py owned by A2 (§5) | §6 "respective imports" row covers replay_engine and validator | PASS | Name and A2 ownership consistent; A2-db owns live_guard.py per §15 agent table |
| 28 | Export Names vs Import | `record_determinism(conn, run_a, run_b, match: int, diffs: list[dict]) -> int` in validation_models.py (§5) | §6 wiring: validator.py consumes | PASS | Name, signature, and diff item schema (`{table_name,pk,key,value_a,value_b}`) consistent; diff field names match determinism_diffs schema columns |
| 29 | Export Names vs Import | `login_required` decorator; `auth.login`/`auth.logout` in app/__init__.py (§5) | §10 auth matrix; all mutating routes require login_required | PASS | Decorator defined and applied consistently; no cross-section name conflict |
| 30 | Mock/Fixture vs Schema | §4.4 taxonomy: `system.heartbeat` → upsert `station_state` with PK `station_id` | schema: `station_state (station_id TEXT PRIMARY KEY, ...)` (§4.2) | PASS | PK name and handler assignment match |
| 31 | Mock/Fixture vs Schema | §4.4: `telemetry.culinary.weight` → `weight_kg (num\|null)` | `station_state.weight_kg REAL` (§4.2) | PASS | Field name and nullable REAL type match |
| 32 | Mock/Fixture vs Schema | §4.4: `telemetry.culinary.temperature` → `temp_c (num\|null)` | `station_state.temp_c REAL` (§4.2) | PASS | Field name and nullable REAL type match |
| 33 | Mock/Fixture vs Schema | §4.4: `telemetry.financial.transaction` → `sales_total_cents += amount_cents` | `station_state.sales_total_cents INTEGER NOT NULL DEFAULT 0` (§4.2) | PASS | Field name, INTEGER type, additive-only semantics, NOT NULL (no clear) consistent |
| 34 | Mock/Fixture vs Schema | §4.4: `telemetry.financial.bid` → `bid_high_cents = MAX(...)`, `bid_count += 1` | `auction_state.bid_high_cents INTEGER NOT NULL DEFAULT 0`, `bid_count INTEGER NOT NULL DEFAULT 0` (§4.2) | PASS | Both field names, types, and additive semantics consistent |
| 35 | Mock/Fixture vs Schema | §4.4: `telemetry.environmental.weather` → `temperature_c`, `humidity_pct`, `wind_speed_kmh` (num\|null) | `environmental_state.temperature_c REAL`, `humidity_pct REAL`, `wind_speed_kmh REAL` (§4.2) | PASS | All 3 field names and nullable REAL types match |
| 36 | Mock/Fixture vs Schema | §4.4: `system.operator_note` → `k='note:'+event_id, v=note` | `system_state (k TEXT PRIMARY KEY, v TEXT)` (§4.2) | PASS | k/v field names and string types match |
| 37 | Mock/Fixture vs Schema | §4.4: `system.alert.raised` → `k=alert_type+':'+source, v='raised'`; `system.alert.resolved` → `k=alert_key, v='resolved'` | `system_state (k TEXT PRIMARY KEY, v TEXT)` (§4.2) | PASS | Both alert event types write to same k/v columns; consistent |
| 38 | Mock/Fixture vs Schema | §4.4 event count totals: 1347+88+45+69+20+21+3+1+1 = 1595 events | §1 overview: "read-only corpus of synthetic CPAA gala telemetry"; §4.3 reuse finding: "exact 1,595-event seed" | PASS | Sum matches the stated corpus count exactly |
| 39 | Cross-Boundary Wiring Completeness | All constants: TS_FORMAT, TS_RE, RUN_STATES, ANOMALY_KINDS, _PROJECTION_TABLES, DISPATCH, EMPTY_PROJECTION_HASH (§5) | Consumers declared in §5 and §6 | PASS | All 7 constants have declared consumers; DISPATCH used by event_models and replay_engine |
| 40 | Cross-Boundary Wiring Completeness | `station_state(conn)`, `auction_state(conn)`, `environmental_state(conn)`, `system_state(conn)` — implied read functions from directory tree (§2) | Absent from Export Names Table (§5) and Cross-Boundary Wiring Table (§6); §9 lists dashboard as reader of all 4 projection tables | WARN | Directory tree comments say `proj_station.py # apply_station + station_state (owner)` implying a read function; §5 and §6 list only apply_*/reset_* exports. §9 data ownership shows dashboard as a reader but does not specify a function. If E1-dashboard reads via direct SQL through get_db(), no import needed. If it expects these as exported functions, build will fail. Not a hard spec contradiction (two sections are silent, not contradictory), but agents need clarification. |
| 41 | Cross-Boundary Wiring Completeness | `events_at_time(conn, t)` Used By: `replay_routes.py, replay_engine.py` (§5) | `build_projection_at` internally calls `events_at_time` (§4.4/§5 docstring); replay_routes also separately listed as direct consumer in §5 and §6 | WARN | If replay_routes only calls `build_projection_at`, the direct `events_at_time` import in replay_routes is redundant. Spec does not clarify whether C6-replay-routes has a second use for events_at_time (e.g., raw event list endpoint). Not a contradiction (both sections agree replay_routes uses it); agent should confirm actual usage to avoid unused imports. |
| 42 | Cross-Boundary Wiring Completeness | All other exported functions in §5 | §5 Used By / §6 Wiring Table | PASS | create_app, get_db, open_live_ro, canonical_hash, parse_json, parse_patch, append_event, get_events, record_anomaly, start_run, active_run, mark_complete_pass, mark_aborted, reap_stale_runs, write_snapshot, read_snapshot, apply_*/reset_* (×4), build_projection_at, live_content_hash, record_determinism — all have at least one declared consumer |
| 43 | ON DELETE vs Docstrings | `projection_snapshots.run_id REFERENCES replay_runs(run_id) ON DELETE CASCADE` (§4.2) | No delete-replay_run route or function defined anywhere in spec | PASS | CASCADE silently removes orphan snapshots; no docstring to contradict since no delete operation exists |
| 44 | ON DELETE vs Docstrings | `anomalies.run_id REFERENCES replay_runs(run_id) ON DELETE SET NULL` (§4.2) | No delete-replay_run operation defined | PASS | SET NULL on anomaly run_id; no docstring to contradict |
| 45 | ON DELETE vs Docstrings | `determinism_diffs.result_id REFERENCES determinism_results(id) ON DELETE CASCADE` (§4.2) | No delete-determinism_result operation defined | PASS | CASCADE; no docstring to contradict |
| 46 | Schema vs canonical hash | `_PROJECTION_TABLES = ("station_state","auction_state","environmental_state","system_state")` (§8 rule 8) | Schema §4.2 defines exactly these 4 projection tables; no other writable tables in hash scope | PASS | Excluded tables (replay_runs, events, anomalies, projection_snapshots) explicitly listed in §8 rule 8; consistent |
| 47 | Schema vs canonical hash | §8 rule 8: SQL NULL → JSON null; REAL cols use repr; `*_at` cols excluded | Schema: `appended_at`, `created_at`, `started_at`, `finished_at` all TEXT (timestamps); none appear in projection tables | PASS | All `*_at` cols are in non-projection tables or are metadata; none would appear in canonical hash anyway since they are in excluded tables |

## Summary

- **Total checks:** 47
- **PASS:** 45
- **FAIL:** 0
- **WARN:** 2
- **N/A (section absent):** 0

## WARN Disposition

**WARN #40 — Projection read function exports ambiguous:**
The directory tree (§2) comments imply `station_state(conn)`, `auction_state(conn)`, etc. are defined in proj_*.py, but the Export Names Table (§5) and Wiring Table (§6) list only `apply_*/reset_*`. The Data Ownership table (§9) shows dashboard as a reader. The simplest resolution: E1-dashboard reads projection tables via direct SQL through `get_db()` — no function export needed. This should be confirmed in the E1-dashboard agent brief. Severity: LOW (ambiguity, not contradiction; agents have a clear fallback).

**WARN #41 — replay_routes.py listed as direct events_at_time consumer:**
Both §5 and §6 list `replay_routes.py` as a consumer of `events_at_time`, in addition to `replay_engine.py` (which uses it inside `build_projection_at`). The spec does not describe a route in replay_routes that would need raw event rows independently of `build_projection_at`. C6-replay-routes should confirm this import is needed; if not, it can be omitted. Not a blocking issue — having an extra import does not break correctness. Severity: LOW.

## Notes

- The spec is CONVERGED (Codex GO x2, human zero-P0 per plan frontmatter). This check confirms zero FAIL-level contradictions remain.
- The prior spec-consistency-check.md (2026-06-06, 4 FAILs) found issues in an earlier pre-convergence draft. All 4 prior FAILs have been resolved in the converged spec: (1) `dup_exact` correctly removed from anomalies.kind CHECK; (2) `dedup_counters` table added with proper `kind` column; (3) route paths in §5 blueprint table are authoritative (directory tree comments are supplementary); (4) all apply_*/reset_* function names now explicit in §5 for all 4 projection modules.
- No FK ON DELETE scenarios can produce docstring mismatches: no parent-table delete routes or functions are defined in the spec, so no IntegrityError behavior claims exist to contradict.
- The canonical hash byte recipe (§8 rule 8) is self-consistent: `_PROJECTION_TABLES` order, REAL column handling, excluded tables, and `EMPTY_PROJECTION_HASH` constant all reference the same recipe with no cross-section divergence.
- The `NON_DETERMINISTIC` run status elimination (pinned A in §3.2) is consistently applied: absent from schema CHECK, absent from RUN_STATES references, and properly placed as `determinism_results.match=0` — zero residual contradiction.
