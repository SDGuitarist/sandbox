#!/usr/bin/env python3
"""
P1/P2 multi-wave barrier loop -- durable artifact writer (plan §6).

TWO subcommands, both ATOMIC (temp file in the SAME dir + os.replace, which is
atomic on POSIX -- a crash never leaves a half-written artifact):

  emit   -- write `w<k>/wave.md`: line 1 `STATUS: <PASS-EMITTED|ABORT>`, then a
            fenced ```json block carrying the full §6 field set. The orchestrator
            passes the assembled values as an explicit JSON payload (this tool
            does NOT re-derive them from git -- that is verify_wave.py's job, which
            re-reads truth independently so a forged artifact is caught). This tool
            computes only `emit_ts` and `prev_wave_artifact_sha` (sha256 of the
            prior wave's wave.md bytes -- tamper evidence), and validates the schema.

  state  -- create/update the durable `w<k>/transition-state.json` (the resume
            source of truth, §5). Loads any existing state, sets `phase`, merges a
            payload, writes atomically. Called write-ahead BEFORE each guarded action.

This tool is TRUSTED-only pinned in the firebreak (TRUSTED_PIPELINE_SCRIPT_PATHS);
workers can never run it.

Usage:
  wave_artifact.py emit  --out <w_k_dir>/wave.md --payload <file|-> [--emit-ts N]
                         [--prev-artifact <w_{k-1}/wave.md>]
  wave_artifact.py state --file <w_k_dir>/transition-state.json --phase <phase>
                         [--payload <file|->]

Exit 0 on success (prints a STATUS line); non-zero with `FAIL[...]` on bad args or
a schema violation.
"""

import argparse
import hashlib
import json
import os
import sys
import time

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_BAD_ARGS = 5

WAVE_STATUS = {"PASS-EMITTED", "ABORT"}

# §6 required top-level fields the orchestrator must supply in the emit payload.
REQUIRED_EMIT_KEYS = {
    "status", "run_id", "wave_count", "wave_index", "run_start_ts",
    "expected_base_sha", "worker_base_sha", "roster", "worker_deltas",
    "ownership_gate", "assembled_output_sha", "gate_results",
    "firebreak_readback", "provenance", "prev_wave_output_sha",
}
ROSTER_KEYS = {"task_id", "agent_id", "role", "branch", "required", "status",
               "terminal_evidence", "terminal_head_sha"}
DELTA_KEYS = {"role", "worker_head_sha", "merge_base_sha", "delta_count"}
GATE_KEYS = {"contract", "integrated_import", "smoke", "test"}

# §5 durable phases (write-ahead). `abort` is terminal.
VALID_PHASES = {
    "roster_prepared", "spawn_in_progress", "workers_terminal", "assembly_started",
    "merge_completed", "provenance_reverified", "artifact_emitted", "wave_verified",
    "readback_ok", "abort",
}
# Fields mirrored into transition-state.json (§6): the resume source of truth.
STATE_MIRROR_KEYS = {"run_id", "wave_index", "phase", "roster", "expected_base_sha",
                     "worker_base_sha", "assembled_output_sha"}


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write(f"FAIL[BAD_ARGS]: {message}\n")
        raise SystemExit(EXIT_BAD_ARGS)


def _fail(msg):
    print(f"FAIL[SCHEMA]: {msg}")
    return EXIT_FAIL


def _load_payload(spec):
    """Read a JSON payload from a file path or '-' (stdin)."""
    if spec == "-":
        raw = sys.stdin.read()
    else:
        with open(spec, encoding="utf-8") as f:
            raw = f.read()
    return json.loads(raw)


def _atomic_write(path, data_bytes):
    """Write `data_bytes` to `path` atomically: a temp file in the SAME directory
    then os.replace (atomic on POSIX). fsync so the rename can't outrun the data."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, f".{os.path.basename(path)}.tmp.{os.getpid()}")
    with open(tmp, "wb") as f:
        f.write(data_bytes)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# --------------------------------------------------------------------------- #
# emit
# --------------------------------------------------------------------------- #

def _validate_emit(p):
    missing = REQUIRED_EMIT_KEYS - set(p)
    if missing:
        return f"payload missing required keys: {sorted(missing)}"
    if p["status"] not in WAVE_STATUS:
        return f"status must be one of {sorted(WAVE_STATUS)}, got {p['status']!r}"
    if not isinstance(p["wave_index"], int) or p["wave_index"] < 1:
        return "wave_index must be an integer >= 1"
    if not isinstance(p["wave_count"], int) or p["wave_count"] < 1:
        return "wave_count must be an integer >= 1"
    if p["wave_index"] > p["wave_count"]:
        return f"wave_index {p['wave_index']} > wave_count {p['wave_count']}"
    if not isinstance(p["roster"], list) or not p["roster"]:
        return "roster must be a non-empty list"
    for i, r in enumerate(p["roster"]):
        miss = ROSTER_KEYS - set(r or {})
        if miss:
            return f"roster[{i}] missing keys: {sorted(miss)}"
    if not isinstance(p["worker_deltas"], list):
        return "worker_deltas must be a list"
    for i, wd in enumerate(p["worker_deltas"]):
        miss = DELTA_KEYS - set(wd or {})
        if miss:
            return f"worker_deltas[{i}] missing keys: {sorted(miss)}"
    if not isinstance(p["gate_results"], dict) or GATE_KEYS - set(p["gate_results"]):
        return f"gate_results must be a dict with keys {sorted(GATE_KEYS)}"
    # ABORT <-> abort_reason coupling.
    reason = p.get("abort_reason")
    if p["status"] == "ABORT" and not reason:
        return "status ABORT requires a non-empty abort_reason"
    if p["status"] == "PASS-EMITTED" and reason:
        return "abort_reason must be null unless status is ABORT"
    # k=1 has no prior wave; k>1 must carry prev_wave_output_sha.
    if p["wave_index"] == 1 and p["prev_wave_output_sha"] is not None:
        return "prev_wave_output_sha must be null for wave 1"
    if p["wave_index"] > 1 and not p["prev_wave_output_sha"]:
        return "prev_wave_output_sha is required for wave > 1"
    return None


def cmd_emit(args):
    try:
        payload = _load_payload(args.payload)
    except (OSError, json.JSONDecodeError) as e:
        return _fail(f"cannot read/parse payload: {e}")
    if not isinstance(payload, dict):
        return _fail("payload must be a JSON object")

    err = _validate_emit(payload)
    if err:
        return _fail(err)

    # Computed fields (this tool owns these two).
    payload["emit_ts"] = int(args.emit_ts) if args.emit_ts is not None \
        else int(time.time())
    if payload["wave_index"] == 1:
        payload["prev_wave_artifact_sha"] = None
        if args.prev_artifact:
            return _fail("--prev-artifact must not be given for wave 1")
    else:
        if not args.prev_artifact:
            return _fail("--prev-artifact <w_{k-1}/wave.md> is required for wave > 1")
        if not os.path.exists(args.prev_artifact):
            return _fail(f"prev artifact not found: {args.prev_artifact}")
        payload["prev_wave_artifact_sha"] = _sha256_file(args.prev_artifact)
    payload.setdefault("abort_reason", None)

    body = json.dumps(payload, indent=2, sort_keys=True)
    text = f"STATUS: {payload['status']}\n\n" \
           f"# Wave Artifact -- run {payload['run_id']} wave {payload['wave_index']}" \
           f"/{payload['wave_count']}\n\n```json\n{body}\n```\n"
    _atomic_write(args.out, text.encode("utf-8"))
    print(f"STATUS: {payload['status']}")
    print(f"artifact: {args.out}")
    return EXIT_OK


# --------------------------------------------------------------------------- #
# state
# --------------------------------------------------------------------------- #

def cmd_state(args):
    if args.phase not in VALID_PHASES:
        return _fail(f"phase must be one of {sorted(VALID_PHASES)}, got {args.phase!r}")
    state = {}
    if os.path.exists(args.file):
        try:
            with open(args.file, encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            return _fail(f"cannot read existing state: {e}")
        if not isinstance(state, dict):
            return _fail("existing state file is not a JSON object")
    if args.payload:
        try:
            merge = _load_payload(args.payload)
        except (OSError, json.JSONDecodeError) as e:
            return _fail(f"cannot read/parse payload: {e}")
        if not isinstance(merge, dict):
            return _fail("payload must be a JSON object")
        state.update(merge)
    state["phase"] = args.phase
    _atomic_write(args.file, (json.dumps(state, indent=2, sort_keys=True) + "\n")
                  .encode("utf-8"))
    print(f"STATUS: STATE-WRITTEN {args.phase}")
    print(f"state: {args.file}")
    return EXIT_OK


def main(argv=None):
    parser = _Parser(description="P1/P2 multi-wave durable artifact writer")
    sub = parser.add_subparsers(dest="command", required=True)

    e = sub.add_parser("emit", help="write w<k>/wave.md atomically")
    e.add_argument("--out", required=True, help="path to w<k>/wave.md")
    e.add_argument("--payload", required=True, help="JSON payload file or '-' for stdin")
    e.add_argument("--emit-ts", default=None, help="override emit_ts (int epoch); default now")
    e.add_argument("--prev-artifact", default=None,
                   help="path to w_{k-1}/wave.md (required for wave > 1)")
    e.set_defaults(func=cmd_emit)

    st = sub.add_parser("state", help="create/update w<k>/transition-state.json atomically")
    st.add_argument("--file", required=True, help="path to transition-state.json")
    st.add_argument("--phase", required=True, help=f"one of {sorted(VALID_PHASES)}")
    st.add_argument("--payload", default=None, help="JSON merge payload file or '-'")
    st.set_defaults(func=cmd_state)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
