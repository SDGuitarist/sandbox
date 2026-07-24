#!/usr/bin/env python3
"""Unit tests for tools/verify_harvest.py (FC-harvest gate).

Builds a temp run dir (harvest-findings.md + pitfalls-baseline.txt + BUILD_TRACKING.md
+ evidence files) in the strict harvest contract, then asserts the STATUS line and exit
code the gate emits for the happy path and each failure mode. Pure stdlib; runs the gate
as a real subprocess, exactly as the tail step invokes it.

Run:  python3 tools/test_verify_harvest.py
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "verify_harvest.py")

_results = []

# Canonical valid harvest: 6 REAL findings (distinct root_cause_id), 2 net-new (FC68/FC69
# absent from a FC1..FC67 baseline), each evidence citing a file that exists on disk. Plus
# two non-REAL rows (near-miss / benign) that must NOT be counted.
_REAL = [
    # id,  rc,     fc_id,            status,               evidence (resolvable)
    ("H1", "RC-1", "FC3",            "REAL — fixed",       "src/a.py:1"),
    ("H2", "RC-2", "FC39-family",    "REAL — C2-blocking", "src/a.py:2"),
    ("H3", "RC-3", "FC58",           "REAL (infra)",       "c2-smoke-report.md:3"),
    ("H4", "RC-4", "FC5",            "REAL",               "src/a.py:4"),
    ("H5", "RC-5", "FC68",           "REAL (net-new)",     "c2-smoke-report.md:5"),
    ("H6", "RC-6", "FC69",           "REAL",               "c2-smoke-report.md:6"),
]
_BENIGN = [
    ("B1", "RC-7", "FC5", "near-miss (converged)", "src/a.py:7"),
    ("B2", "RC-8", "n/a", "RESOLVED-BENIGN",        "src/a.py:8"),
]


def _run(reports_dir, root, **extra):
    cmd = [sys.executable, GATE, "--reports-dir", reports_dir, "--root", root]
    for k, v in extra.items():
        cmd += [f"--{k.replace('_', '-')}", str(v)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout + proc.stderr).splitlines()
    first = next((ln for ln in out if ln.startswith("STATUS:")), "")
    return first, proc.returncode


def check(name, cond):
    _results.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _table(rows):
    out = ["| id | root_cause_id | fc_id | status | evidence |",
           "|----|---------------|-------|--------|----------|"]
    for (rid, rc, fc, st, ev) in rows:
        out.append(f"| {rid} | {rc} | {fc} | {st} | {ev} |")
    return "\n".join(out) + "\n"


def _build_tracking(real_rows):
    blocks = ["## FAILURES", ""]
    for (rid, rc, fc, _st, _ev) in real_rows:
        blocks.append(f"### [seam] {rid} {rc}")
        blocks.append(f"**root_cause_id:** {rc} · **Failure class:** {fc}")
        blocks.append("")
    blocks += ["## RUN_METRICS", ""]
    return "\n".join(blocks)


def _baseline():
    ids = ", ".join(f"FC{n}" for n in range(1, 68))    # FC1..FC67
    return f"failure_class_count: 67\nfailure_class_ids: {ids}\n"


def _make(real=_REAL, benign=_BENIGN, bt_real=None, with_baseline=True, bt_text=None):
    """Materialize a run dir. Returns (reports_dir, root). bt_real defaults to `real`;
    bt_text (when given) is written to BUILD_TRACKING.md verbatim (for row-scope tests)."""
    root = tempfile.mkdtemp(prefix="vh-root-")
    reports_dir = os.path.join(root, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    # evidence targets
    _write(os.path.join(root, "src", "a.py"), "# fixture\n" * 10)
    _write(os.path.join(reports_dir, "c2-smoke-report.md"), "STATUS: PASS\n")
    # harvest table + BUILD_TRACKING + baseline
    _write(os.path.join(reports_dir, "harvest-findings.md"),
           "# harvest\n\n" + _table(list(real) + list(benign)))
    _write(os.path.join(root, "BUILD_TRACKING.md"),
           bt_text if bt_text is not None
           else _build_tracking(bt_real if bt_real is not None else real))
    if with_baseline:
        _write(os.path.join(reports_dir, "pitfalls-baseline.txt"), _baseline())
    return reports_dir, root


def main():
    # ---- happy path -> PASS, exit 0 ----
    rd, rt = _make()
    line, rc = _run(rd, rt)
    check("valid harvest -> STATUS: PASS", line == "STATUS: PASS")
    check("valid harvest -> exit 0", rc == 0)
    check("report written", os.path.exists(os.path.join(rd, "harvest-verification.md")))

    # ---- BREADTH: only 4 REAL (demote H5,H6) -> FAIL BREADTH ----
    demoted = _REAL[:4] + [(i, rc_, fc, "benign", ev) for (i, rc_, fc, _s, ev) in _REAL[4:]]
    rd, rt = _make(real=demoted, bt_real=_REAL)
    line, rc = _run(rd, rt)
    check("4 REAL -> FAIL BREADTH", line.startswith("STATUS: FAIL") and "BREADTH" in line)
    check("breadth fail -> exit 1", rc == 1)

    # ---- BIJECTION: BUILD_TRACKING missing one REAL rc -> FAIL BIJECTION ----
    rd, rt = _make(bt_real=_REAL[:-1])          # drop RC-6's failures row
    line, rc = _run(rd, rt)
    check("missing FAILURES row -> FAIL BIJECTION",
          line.startswith("STATUS: FAIL") and "BIJECTION" in line)

    # ---- EVIDENCE: a REAL finding cites no resolvable file -> FAIL EVIDENCE ----
    hollow = list(_REAL)
    hollow[3] = ("H4", "RC-4", "FC5", "REAL", "the finding was injected, by construction")
    rd, rt = _make(real=hollow, bt_real=_REAL)
    line, rc = _run(rd, rt)
    check("unresolvable evidence -> FAIL EVIDENCE",
          line.startswith("STATUS: FAIL") and "EVIDENCE" in line)

    # ---- NET-NEW: both net-new relabeled to in-baseline FCs -> FAIL NET-NEW ----
    variants = list(_REAL)
    variants[4] = ("H5", "RC-5", "FC58", "REAL", "c2-smoke-report.md:5")
    variants[5] = ("H6", "RC-6", "FC30", "REAL", "c2-smoke-report.md:6")
    rd, rt = _make(real=variants, bt_real=_REAL)
    line, rc = _run(rd, rt)
    check("no net-new -> FAIL NET-NEW",
          line.startswith("STATUS: FAIL") and "NET-NEW" in line)

    # ---- ANTI-GAMING: 'net-new' word on an in-baseline FC is NOT trusted -> FAIL NET-NEW ----
    gamed = list(_REAL)
    gamed[4] = ("H5", "RC-5", "FC58 net-new", "REAL", "c2-smoke-report.md:5")  # variant, not net-new
    # H6 stays FC69 (1 real net-new) -> below min 2
    rd, rt = _make(real=gamed, bt_real=_REAL)
    line, rc = _run(rd, rt)
    check("self-declared net-new on in-baseline FC rejected -> FAIL NET-NEW",
          line.startswith("STATUS: FAIL") and "NET-NEW" in line)

    # ---- BREADTH dupe: two REAL rows share a root_cause_id -> FAIL BREADTH ----
    dup = list(_REAL)
    dup[5] = ("H6", "RC-5", "FC69", "REAL", "c2-smoke-report.md:6")   # RC-5 twice
    rd, rt = _make(real=dup, bt_real=_REAL)
    line, rc = _run(rd, rt)
    check("duplicate root_cause_id -> FAIL BREADTH",
          line.startswith("STATUS: FAIL") and "BREADTH" in line)

    # ---- INPUT_ERROR: missing baseline -> exit 2 ----
    rd, rt = _make(with_baseline=False)
    line, rc = _run(rd, rt)
    check("missing baseline -> exit 2 (INPUT_ERROR)", rc == 2)
    check("missing baseline -> STATUS: FAIL line", line.startswith("STATUS: FAIL"))

    # ---- BIJECTION row-scope: ONE FAILURES block lists two REAL rcs -> FAIL BIJECTION ----
    # A global findall would PASS (each rc appears once); row-scoping must reject a single
    # tracked row standing in for two findings. RC-1..RC-4 get their own blocks; RC-5+RC-6
    # share one -> the shared-row check fires.
    merged_bt = (
        "## FAILURES\n\n"
        "### block RC-1\n**root_cause_id:** RC-1 · **Failure class:** FC3\n\n"
        "### block RC-2\n**root_cause_id:** RC-2 · **Failure class:** FC39\n\n"
        "### block RC-3\n**root_cause_id:** RC-3 · **Failure class:** FC58\n\n"
        "### block RC-4\n**root_cause_id:** RC-4 · **Failure class:** FC5\n\n"
        "### shared row\n**root_cause_id:** RC-5 · **Failure class:** FC68\n"
        "**root_cause_id:** RC-6 · **Failure class:** FC69\n\n"
        "## RUN_METRICS\n")
    rd, rt = _make(bt_text=merged_bt)
    line, rc = _run(rd, rt)
    check("one FAILURES row with two REAL rcs -> FAIL BIJECTION",
          line.startswith("STATUS: FAIL") and "BIJECTION" in line)

    # ---- THRESHOLDS: non-positive --min-real / --min-netnew -> EXIT_BAD_ARGS (fail closed) ----
    # A zero/negative floor makes breadth/net-new vacuously true -> a hollow harvest would
    # PASS; reject it at the arg layer instead.
    rd, rt = _make()
    line, rc = _run(rd, rt, min_real=0)
    check("--min-real 0 -> exit 5 (BAD_ARGS)", rc == 5)
    check("--min-real 0 -> STATUS: FAIL line", line.startswith("STATUS: FAIL"))
    line, rc = _run(rd, rt, min_netnew=0)
    check("--min-netnew 0 -> exit 5 (BAD_ARGS)", rc == 5)
    line, rc = _run(rd, rt, min_real=-3)
    check("--min-real negative -> exit 5 (BAD_ARGS)", rc == 5)

    passed = sum(1 for _n, ok in _results if ok)
    total = len(_results)
    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
