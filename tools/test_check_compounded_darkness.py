#!/usr/bin/env python3
"""
Unit tests for tools/check_compounded_darkness.py (080-W5).

Builds temp report dirs with fixture artifacts and asserts the STATUS token the
checker prints (COMPOUNDED_DARKNESS iff all three surfaces DARK). Pure stdlib;
runs the checker as a real subprocess, exactly as the tail step invokes it.

Run:  python3 tools/test_check_compounded_darkness.py
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKER = os.path.join(HERE, "check_compounded_darkness.py")

_results = []


def _run(reports_dir, **overrides):
    cmd = [sys.executable, CHECKER, "--reports-dir", reports_dir]
    for k, v in overrides.items():
        cmd += [f"--{k.replace('_', '-')}", v]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    first = proc.stdout.splitlines()[0] if proc.stdout else ""
    token = first.replace("STATUS:", "").strip() if first.startswith("STATUS:") else ""
    return token, proc.returncode, proc.stdout


def check(name, got, want):
    ok = got == want
    _results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  (got {got!r}, want {want!r})")


def _mkdir():
    return tempfile.mkdtemp(prefix="cd-test-")


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _dark_provenance(d):
    _write(os.path.join(d, "spec-provenance.md"),
           "STATUS: PROVENANCE_REPAIRED -- inline-injection-FALLBACK\n\n# prov\n")


def _dark_smoke(d):
    _write(os.path.join(d, "smoke-test.md"), "STATUS: FIREBREAK_DEFERRED\n\n# smoke\n")


def main():
    # ---- all three DARK -> COMPOUNDED_DARKNESS (the 080-W5 pattern) ----
    d = _mkdir()
    _dark_provenance(d)                       # provenance FALLBACK
    _dark_smoke(d)                            # dynamic FIREBREAK_DEFERRED
    # spec-eval: no artifact at all (ENV_ERROR writes nothing) -> DARK
    tok, rc, _ = _run(d)
    check("all three dark -> COMPOUNDED_DARKNESS", tok, "COMPOUNDED_DARKNESS")
    check("observability-only: exit 0 even when compounded", str(rc), "0")

    # report file is written
    check("report written", str(os.path.exists(os.path.join(d, "compounded-darkness.md"))),
          "True")

    # ---- spec-eval LIT via verification.md (nested) -> OK ----
    d = _mkdir()
    _dark_provenance(d)
    _dark_smoke(d)
    _write(os.path.join(d, "spec-eval-1780000000", "spec-eval-verification.md"),
           "STATUS: PASS\nhigh_passed: 5/5\n")
    tok, _, _ = _run(d)
    check("spec-eval PASS artifact lights it -> OK", tok, "OK")

    # ---- spec-eval LIT via gate.json FAIL verdict -> OK ----
    d = _mkdir()
    _dark_provenance(d)
    _dark_smoke(d)
    _write(os.path.join(d, "spec-eval-1780000001", "spec-eval-gate.json"),
           json.dumps({"status": "GateStatus.FAIL"}))
    tok, _, _ = _run(d)
    check("spec-eval FAIL gate.json is a real verdict -> OK", tok, "OK")

    # ---- spec-eval gate.json RETRY (no verdict) stays DARK -> COMPOUNDED ----
    d = _mkdir()
    _dark_provenance(d)
    _dark_smoke(d)
    _write(os.path.join(d, "spec-eval-1780000002", "spec-eval-gate.json"),
           json.dumps({"status": "GateStatus.RETRY"}))
    tok, _, _ = _run(d)
    check("spec-eval RETRY is no verdict -> still COMPOUNDED_DARKNESS", tok,
          "COMPOUNDED_DARKNESS")

    # ---- provenance PROVENANCE_OK lights it -> OK ----
    d = _mkdir()
    _write(os.path.join(d, "spec-provenance.md"),
           "STATUS: PROVENANCE_OK -- docs/plans/x.md\n")
    _dark_smoke(d)
    tok, _, _ = _run(d)
    check("provenance OK proof lights it -> OK", tok, "OK")

    # ---- provenance OK-but-FALLBACK is NOT a proof -> DARK ----
    d = _mkdir()
    _write(os.path.join(d, "spec-provenance.md"),
           "STATUS: PROVENANCE_OK_FALLBACK -- non-proof\n")
    _dark_smoke(d)
    tok, _, _ = _run(d)
    check("provenance OK+FALLBACK is non-proof -> COMPOUNDED_DARKNESS", tok,
          "COMPOUNDED_DARKNESS")

    # ---- dynamic smoke PASS lights it -> OK ----
    d = _mkdir()
    _dark_provenance(d)
    _write(os.path.join(d, "smoke-test.md"), "STATUS: PASS\n\n# smoke\n")
    tok, _, _ = _run(d)
    check("smoke PASS (executed) lights it -> OK", tok, "OK")

    # ---- dynamic LIT via post-teardown rerun even if smoke deferred -> OK ----
    d = _mkdir()
    _dark_provenance(d)
    _dark_smoke(d)
    _write(os.path.join(d, "smoke-rerun-postteardown.md"),
           "STATUS: PASS\n16/16\n")
    tok, _, _ = _run(d)
    check("smoke-rerun PASS lights dynamic -> OK", tok, "OK")

    # ---- dynamic LIT via c2-smoke-report.md (083 D2 regression) -> OK ----
    d = _mkdir()
    _dark_provenance(d)
    _dark_smoke(d)                            # smoke-test.md deferred
    _write(os.path.join(d, "c2-smoke-report.md"),
           "STATUS: PASS\n\n# swarmlimit C2 smoke report\n- exercised endpoints: 31\n")
    tok, _, _ = _run(d)
    check("c2-smoke-report PASS lights dynamic (083 D2 regression) -> OK", tok, "OK")

    # ---- overrides win over disk (orchestrator can pass authoritative status) ----
    d = _mkdir()
    _dark_provenance(d)
    _dark_smoke(d)
    tok, _, _ = _run(d, spec_eval_status="ENV_ERROR", provenance_status="PROVENANCE_OK",
                     dynamic_status="FIREBREAK_DEFERRED")
    check("provenance override OK lights it -> OK", tok, "OK")

    # ---- empty dir: everything absent -> COMPOUNDED_DARKNESS ----
    d = _mkdir()
    tok, _, _ = _run(d)
    check("empty reports dir -> COMPOUNDED_DARKNESS (fail-to-dark)", tok,
          "COMPOUNDED_DARKNESS")

    # ---- summary ----
    passed = sum(1 for _n, ok in _results if ok)
    total = len(_results)
    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
