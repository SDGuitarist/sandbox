#!/usr/bin/env python3
"""Deterministic fixture harness for tools/verify_delegated_status.py (Plan A, item 1).

Covers all nine verifier cases. Uses os.utime to set mtimes exactly, so "stale"
vs "fresh" is deterministic with no sleeps. Run with one command:

    python3 tests/test_verify_delegated_status.py

Prints "N/N passed" and exits 0 only when every case matches its expected code.
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "tools", "verify_delegated_status.py")

RUN_ID = "069"
RUN_START = 1_000_000_000  # arbitrary fixed epoch; fixtures set mtime relative to this

# Realistic artifact bodies (match the on-disk producer formats).
SELF_AUDIT = (
    "# Self-Audit Report -- Run {rid}\n\n"
    "**Date:** 2026-06-06\n"
    "**Run ID:** {rid}\n"
    "**Final Status:** {status}\n\n"
    "## Final Run Status\n\n"
    "**Status:** {status}\n\n"
    "All gates passed.\n"
)
ASSEMBLY = (
    "STATUS: {status}\n\n"
    "# Assembly Summary — Run {rid}\n\n"
    "- merge_status: all merged\n"
)


def _write(body, mtime_offset_s):
    """Write a fixture in a fresh temp dir; set its mtime relative to RUN_START."""
    d = tempfile.mkdtemp()
    p = os.path.join(d, "artifact.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(body)
    mtime = RUN_START + mtime_offset_s
    os.utime(p, ns=(mtime * 1_000_000_000, mtime * 1_000_000_000))
    return p


def _run(artifact, kind, wire=None, run_id=RUN_ID, run_start=RUN_START):
    cmd = [
        sys.executable, SCRIPT,
        "--artifact", artifact,
        "--artifact-kind", kind,
        "--run-start-ts", str(run_start),
        "--run-id", run_id,
    ]
    if wire is not None:
        cmd += ["--wire-status", wire]
    return subprocess.run(cmd, capture_output=True, text=True).returncode


def main():
    missing = os.path.join(tempfile.mkdtemp(), "does-not-exist.md")

    cases = [
        # label, expected_exit, returncode-thunk
        # --- PASS cases ---
        ("self-audit PIPELINE_PASS, no wire",
         0, lambda: _run(_write(SELF_AUDIT.format(rid=RUN_ID, status="PIPELINE_PASS"), 5),
                         "self-audit")),
        ("self-audit PIPELINE_PASS_WITH_DEFERRED_RISK",
         0, lambda: _run(_write(SELF_AUDIT.format(rid=RUN_ID, status="PIPELINE_PASS_WITH_DEFERRED_RISK"), 5),
                         "self-audit")),
        ("self-audit PIPELINE_PASS, wire contradicts (FAIL) -> disk wins",
         0, lambda: _run(_write(SELF_AUDIT.format(rid=RUN_ID, status="PIPELINE_PASS"), 5),
                         "self-audit", wire="FAIL — agent crashed")),
        ("assembly PASS, wire contradicts (FAIL) -> disk wins",
         0, lambda: _run(_write(ASSEMBLY.format(rid=RUN_ID, status="PASS"), 5),
                         "assembly", wire="FAIL — agent crashed")),
        # --- FAIL cases ---
        ("missing artifact -> 2",
         2, lambda: _run(missing, "self-audit")),
        ("stale self-audit PASS (mtime < run_start) -> 3",
         3, lambda: _run(_write(SELF_AUDIT.format(rid=RUN_ID, status="PIPELINE_PASS"), -60),
                         "self-audit")),
        ("run-id mismatch -> 6",
         6, lambda: _run(_write(SELF_AUDIT.format(rid="999", status="PIPELINE_PASS"), 5),
                         "self-audit")),
        ("self-audit PIPELINE_FAIL, wire says PASS -> 1",
         1, lambda: _run(_write(SELF_AUDIT.format(rid=RUN_ID, status="PIPELINE_FAIL"), 5),
                         "self-audit", wire="PASS")),
        ("no status token -> 4",
         4, lambda: _run(_write("# Self-Audit Report -- Run 069\n\n**Run ID:** 069\n\nbody\n", 5),
                         "self-audit")),
    ]

    passed = 0
    for label, expected, thunk in cases:
        rc = thunk()
        ok = rc == expected
        passed += ok
        print(f"[{'ok' if ok else 'XX'}] {label}: rc={rc} (expected {expected})")

    print(f"{passed}/{len(cases)} passed")
    sys.exit(0 if passed == len(cases) else 1)


if __name__ == "__main__":
    main()
