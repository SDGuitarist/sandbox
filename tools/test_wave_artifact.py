#!/usr/bin/env python3
"""
Unit tests for tools/wave_artifact.py (plan §6 / §8).

Plain stdlib; runs the tool as a real subprocess (exactly as the SKILL invokes it).
Exposes a `--case <name>` selector (per plan §8) plus a no-arg full-suite run.

Run:  python3 tools/test_wave_artifact.py                 # full suite
      python3 tools/test_wave_artifact.py --case test_emit_wave1_ok
"""

import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "wave_artifact.py")

CASES = {}


def case(fn):
    CASES[fn.__name__] = fn
    return fn


def _mkdir():
    return tempfile.mkdtemp(prefix="wave-artifact-test-")


def _write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    return path


def _payload(wave_index=1, status="PASS-EMITTED", **over):
    p = {
        "status": status, "run_id": "085", "wave_count": 3, "wave_index": wave_index,
        "run_start_ts": 1000, "expected_base_sha": "a" * 40, "worker_base_sha": "b" * 40,
        "roster": [{"task_id": "t1", "agent_id": "ag1", "role": "models",
                    "branch": "swarm-085-w1-models", "required": "yes",
                    "status": "COMPLETED", "terminal_evidence": "completion-notified",
                    "terminal_head_sha": "c" * 40}],
        "worker_deltas": [{"role": "models", "worker_head_sha": "c" * 40,
                           "merge_base_sha": "b" * 40, "delta_count": 1}],
        "ownership_gate": {"verdict": "PASS", "path": "w1/ownership-gate.md"},
        "assembled_output_sha": "d" * 40,
        "gate_results": {
            "contract": {"verdict": "PASS", "path": "w1/contract-check.md"},
            "integrated_import": {"verdict": "PASS", "path": "w1/integrated-import.md"},
            "smoke": {"verdict": "PASS", "path": "w1/smoke-test.md"},
            "test": {"verdict": "PASS", "path": "w1/test-results.md"}},
        "firebreak_readback": {"status": "ACTIVE", "ts": 1001},
        "provenance": {"status": "PROVENANCE_OK", "path": "w1/spec-provenance.md"},
        "prev_wave_output_sha": None if wave_index == 1 else "d" * 40,
    }
    p.update(over)
    return p


def _emit(out, payload, emit_ts=1234567890, prev_artifact=None):
    d = _mkdir()
    pf = _write_json(os.path.join(d, "payload.json"), payload)
    cmd = [sys.executable, TOOL, "emit", "--out", out, "--payload", pf]
    if emit_ts is not None:
        cmd += ["--emit-ts", str(emit_ts)]
    if prev_artifact:
        cmd += ["--prev-artifact", prev_artifact]
    return subprocess.run(cmd, capture_output=True, text=True)


def _state(file, phase, payload=None):
    cmd = [sys.executable, TOOL, "state", "--file", file, "--phase", phase]
    if payload is not None:
        d = _mkdir()
        cmd += ["--payload", _write_json(os.path.join(d, "merge.json"), payload)]
    return subprocess.run(cmd, capture_output=True, text=True)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _json_block(text):
    body = text.split("```json", 1)[1].split("```", 1)[0]
    return json.loads(body)


# --------------------------------------------------------------------------- #
# emit cases
# --------------------------------------------------------------------------- #

@case
def test_emit_wave1_ok():
    d = _mkdir()
    out = os.path.join(d, "wave.md")
    r = _emit(out, _payload(1))
    assert r.returncode == 0, r.stderr + r.stdout
    text = _read(out)
    assert text.splitlines()[0] == "STATUS: PASS-EMITTED", text
    obj = _json_block(text)
    assert obj["prev_wave_artifact_sha"] is None
    assert obj["emit_ts"] == 1234567890
    assert obj["abort_reason"] is None


@case
def test_emit_atomic_no_tmp_left():
    d = _mkdir()
    out = os.path.join(d, "wave.md")
    assert _emit(out, _payload(1)).returncode == 0
    leftovers = glob.glob(os.path.join(d, ".*tmp*"))
    assert leftovers == [], f"temp file left behind: {leftovers}"


@case
def test_emit_wave2_prev_sha():
    d = _mkdir()
    w1 = os.path.join(d, "w1_wave.md")
    assert _emit(w1, _payload(1)).returncode == 0
    import hashlib
    want = hashlib.sha256(_read(w1).encode("utf-8")).hexdigest()
    w2 = os.path.join(d, "w2_wave.md")
    r = _emit(w2, _payload(2), prev_artifact=w1)
    assert r.returncode == 0, r.stderr + r.stdout
    assert _json_block(_read(w2))["prev_wave_artifact_sha"] == want


@case
def test_emit_missing_key_fails():
    p = _payload(1)
    del p["assembled_output_sha"]
    r = _emit(os.path.join(_mkdir(), "wave.md"), p)
    assert r.returncode != 0 and "assembled_output_sha" in r.stdout


@case
def test_emit_bad_status_fails():
    r = _emit(os.path.join(_mkdir(), "wave.md"), _payload(1, status="PASS"))
    assert r.returncode != 0 and "status must be one of" in r.stdout


@case
def test_emit_abort_requires_reason():
    r = _emit(os.path.join(_mkdir(), "wave.md"), _payload(1, status="ABORT"))
    assert r.returncode != 0 and "abort_reason" in r.stdout


@case
def test_emit_abort_ok_with_reason():
    d = _mkdir()
    out = os.path.join(d, "wave.md")
    r = _emit(out, _payload(1, status="ABORT", abort_reason="worker timeout unstoppable"))
    assert r.returncode == 0, r.stderr + r.stdout
    assert _read(out).splitlines()[0] == "STATUS: ABORT"


@case
def test_emit_passemitted_with_reason_fails():
    r = _emit(os.path.join(_mkdir(), "wave.md"),
              _payload(1, abort_reason="should not be here"))
    assert r.returncode != 0 and "abort_reason must be null" in r.stdout


@case
def test_emit_wave1_with_prev_output_fails():
    r = _emit(os.path.join(_mkdir(), "wave.md"),
              _payload(1, prev_wave_output_sha="d" * 40))
    assert r.returncode != 0 and "must be null for wave 1" in r.stdout


@case
def test_emit_wave2_without_prev_output_fails():
    p = _payload(2)
    p["prev_wave_output_sha"] = None
    r = _emit(os.path.join(_mkdir(), "wave.md"), p)
    assert r.returncode != 0 and "required for wave > 1" in r.stdout


@case
def test_emit_roster_missing_terminal_head_fails():
    p = _payload(1)
    del p["roster"][0]["terminal_head_sha"]
    r = _emit(os.path.join(_mkdir(), "wave.md"), p)
    assert r.returncode != 0 and "terminal_head_sha" in r.stdout


@case
def test_emit_wave2_without_prev_artifact_flag_fails():
    r = _emit(os.path.join(_mkdir(), "wave.md"), _payload(2))  # no --prev-artifact
    assert r.returncode != 0 and "prev-artifact" in r.stdout


# --------------------------------------------------------------------------- #
# state cases
# --------------------------------------------------------------------------- #

@case
def test_state_write_and_merge():
    d = _mkdir()
    f = os.path.join(d, "transition-state.json")
    r1 = _state(f, "roster_prepared",
                {"run_id": "085", "wave_index": 1, "expected_base_sha": "a" * 40})
    assert r1.returncode == 0, r1.stderr + r1.stdout
    st = json.loads(_read(f))
    assert st["phase"] == "roster_prepared" and st["run_id"] == "085"
    # second call advances the phase + merges new keys, preserving old ones.
    r2 = _state(f, "merge_completed", {"assembled_output_sha": "d" * 40})
    assert r2.returncode == 0, r2.stderr + r2.stdout
    st = json.loads(_read(f))
    assert st["phase"] == "merge_completed"
    assert st["assembled_output_sha"] == "d" * 40
    assert st["expected_base_sha"] == "a" * 40  # preserved across the merge


@case
def test_state_bad_phase_fails():
    r = _state(os.path.join(_mkdir(), "transition-state.json"), "not_a_phase")
    assert r.returncode != 0 and "phase must be one of" in r.stdout


@case
def test_state_atomic_no_tmp_left():
    d = _mkdir()
    f = os.path.join(d, "transition-state.json")
    assert _state(f, "roster_prepared", {"run_id": "085"}).returncode == 0
    assert glob.glob(os.path.join(d, ".*tmp*")) == []


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default=None)
    args = ap.parse_args(argv)
    names = [args.case] if args.case else list(CASES)
    if args.case and args.case not in CASES:
        print(f"unknown case: {args.case}\navailable: {sorted(CASES)}")
        return 2
    passed = 0
    failed = 0
    for name in names:
        try:
            CASES[name]()
            print(f"[PASS] {name}")
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {name}: {e}")
            failed += 1
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] {name}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed + failed} passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
