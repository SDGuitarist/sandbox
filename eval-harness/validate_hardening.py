#!/usr/bin/env python3
"""Orchestration-hardening fixture runner.

Discovers negative-test fixtures, drives each against the SHIPPED guard it
targets, and prints a per-track fidelity matrix. Run with no flags for the full
matrix, or `--fixture F-B1` for a single fixture.

The honesty contract (M6): the fidelity column reports the label the invocation
actually earned and never rounds up. See `fixtures/README.md` for the vocabulary.

    EXERCISED        drove the shipped artifact itself (e.g. the real agent)
    SPIKE-VALIDATED  ran an existing spike copy of the recipe, not the ship
    PROSE-ASSERTED   checked an orchestrator-prose contract; no executable guard
    MIRRORED         ran a Python reimplementation -- never conflated with EXERCISED

Phase 1 implements F-B1 only (Track B / FC50 -- the merge-blocking gap). Tracks
A / C / FC52 are Phase 2/3 and are shown as PENDING.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
REPO_ROOT = HARNESS_DIR.parent
FIXTURES_DIR = HARNESS_DIR / "fixtures"

# Fidelity labels (honesty contract). Never report a spike/prose/mirror as EXERCISED.
EXERCISED = "EXERCISED"
SPIKE_VALIDATED = "SPIKE-VALIDATED"
PROSE_ASSERTED = "PROSE-ASSERTED"
MIRRORED = "MIRRORED"

# The four hardening tracks, in matrix order. Phase 1 builds Track B only.
TRACKS = ["A", "B", "C", "FC52"]
TRACK_TITLES = {
    "A": "Track A — FC51 cherry-pick assembly + ownership conflict",
    "B": "Track B — FC50 orchestration-entrypoint signature guard",
    "C": "Track C — spec-eval advisory demotion",
    "FC52": "FC52 — spec-provenance divergence detection",
}

# Honest status for tracks with no automated fixture, so they are never rendered
# as a fidelity label they did not earn. (fidelity, outcome, evidence)
#   Track A: P-accept. The cherry-pick assembly is agent-prose in swarm-runner.md;
#   exercising it as-shipped needs a share-not-fork extraction (a deliberate
#   hardening refactor with its own real-build validation), NOT a fixture. Until
#   then it stays field+spike-validated, labelled honestly — not EXERCISED.
TRACK_STATIC = {
    "A": ("FIELD+SPIKE", "N/A",
          "P-accept: cherry-pick assembly is agent-prose (swarm-runner.md:76-138); "
          "field-proven runs 069/070 + spikes. NOT fixtured as EXERCISED — pending a "
          "deliberate P-extract refactor."),
}


@dataclass
class FixtureResult:
    """Outcome of one fixture run."""

    fixture_id: str
    track: str
    fidelity: str          # one of the four labels above
    passed: bool           # did the shipped guard produce the expected verdict?
    verdict: str           # the guard's actual verdict (e.g. "FAIL", "PASS/N/A")
    detail: str            # human-readable evidence line


# --------------------------------------------------------------------------- #
# F-B1 — Track B / FC50: invoke the REAL spec-completeness-checker agent.       #
# --------------------------------------------------------------------------- #

# Identifies the FC50 surface in a Results-table row or Details header.
_FC50_SURFACE = re.compile(r"orchestration entrypoint|FC50", re.IGNORECASE)


def _fc50_surface_failed(lines: list[str]) -> bool:
    """True iff the report marks the Orchestration-Entrypoint (FC50) SURFACE as
    FAIL.

    Reads the STATUS *cell* of the FC50 Results-table row (or a Details header) --
    NOT merely "the word FAIL appears on a line mentioning entrypoints", which
    false-matches explanatory prose when FC50 actually PASSED. This precision is
    what lets the negative case (pinned signature -> FC50 PASS, gate still FAILs
    on an unrelated surface) correctly report the fixture as FAILED.
    """
    for ln in lines:
        s = ln.strip()
        if s.startswith("|"):  # Results-table row: | <surface> | <status> | ... |
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) >= 2 and _FC50_SURFACE.search(cells[0]):
                if cells[1].upper() == "FAIL":
                    return True
        elif s.startswith("#"):  # Details header: ### Orchestration ... (FC50): FAIL
            if _FC50_SURFACE.search(s) and re.search(r":\s*FAIL\b", s, re.IGNORECASE):
                return True
    return False


def evaluate_fb1_report(text: str) -> tuple[bool, str, str]:
    """Decide F-B1's outcome from the agent's report text. Pure + testable.

    PASSES only when the guard FAILED *on the FC50 surface specifically* and
    named `compute_schedule`. Requiring the FC50 surface (not just any FAIL, and
    not merely the symbol appearing somewhere) is what makes the negative case
    discriminate: if the signature were pinned, FC50 flips to PASS/N-A and the
    symbol still appears in the results row -- but the fixture must then report
    FAILED, because Track B's guard did not fire.

    Returns (passed, verdict, detail).
    """
    lines = text.splitlines()
    status_line = lines[0].strip() if lines else ""
    gate_failed = status_line.upper().startswith("STATUS: FAIL")
    fc50_failed = _fc50_surface_failed(lines)
    names_symbol = "compute_schedule" in text

    if gate_failed and fc50_failed and names_symbol:
        return True, "FAIL", (
            f"gate FAILED on the FC50 surface naming compute_schedule "
            f"(line 1: {status_line!r})"
        )
    if gate_failed and names_symbol and not fc50_failed:
        return False, "FAIL", (
            "gate FAILED but NOT on the FC50 surface -- the failure is not "
            f"attributable to the unpinned entrypoint (line 1: {status_line!r})"
        )
    if gate_failed and not names_symbol:
        return False, "FAIL", (
            "gate FAILED but did not name compute_schedule "
            f"(line 1: {status_line!r})"
        )
    return False, (status_line or "UNKNOWN"), (
        "gate did NOT flag the unpinned entrypoint -- Track B unproven "
        f"(line 1: {status_line!r})"
    )


def run_fb1(claude_bin: str = "claude", timeout: int = 420) -> FixtureResult:
    """Drive the shipped spec-completeness-checker agent against the F-B1 spec.

    Faithfulness: we invoke `claude -p --agent spec-completeness-checker`, which
    loads `.claude/agents/spec-completeness-checker.md` verbatim as the session
    agent. That IS the artifact the autopilot pipeline runs (runs 069/070) -- no
    reimplementation, so the label is EXERCISED. We then read line 1 of the
    report the agent writes (its Output Contract) and assert the gate caught the
    unpinned entrypoint.

    The fixture PASSES when the guard correctly FAILS the broken spec naming
    `compute_schedule`. If the guard returns PASS/N/A, Track B is unproven and
    the fixture FAILS.
    """
    fb1_dir = FIXTURES_DIR / "fb1"
    spec_src = fb1_dir / "spec.md"
    bt_src = fb1_dir / "build_tracking.md"

    work = Path(tempfile.mkdtemp(prefix="fb1-"))
    try:
        spec = work / "spec.md"
        build_tracking = work / "build_tracking.md"
        reports = work / "reports"
        reports.mkdir()
        shutil.copy(spec_src, spec)
        shutil.copy(bt_src, build_tracking)

        prompt = (
            "You are being run as the spec-completeness-checker gate on a fixture "
            "spec. Run your full checks and write the report per your Output "
            "Contract. Arguments:\n"
            f"1. Plan document: {spec}\n"
            f"2. Reports directory: {reports}\n"
            f"3. BUILD_TRACKING.md: {build_tracking}\n"
        )
        # The prompt goes via stdin, NOT as a positional: `--add-dir` is variadic
        # and would otherwise swallow the prompt as a second directory.
        cmd = [
            claude_bin, "-p",
            "--agent", "spec-completeness-checker",
            "--dangerously-skip-permissions",
            "--add-dir", str(work),
        ]

        try:
            proc = subprocess.run(
                cmd, input=prompt, cwd=str(REPO_ROOT), capture_output=True,
                text=True, timeout=timeout,
            )
        except FileNotFoundError:
            return FixtureResult(
                "F-B1", "B", EXERCISED, False, "ERROR",
                f"could not invoke '{claude_bin}' -- is the Claude CLI installed?",
            )
        except subprocess.TimeoutExpired:
            return FixtureResult(
                "F-B1", "B", EXERCISED, False, "ERROR",
                f"agent invocation timed out after {timeout}s",
            )

        report = reports / "spec-completeness-check.md"
        if not report.exists():
            tail = (proc.stdout or proc.stderr or "").strip()[-400:]
            return FixtureResult(
                "F-B1", "B", EXERCISED, False, "ERROR",
                f"agent wrote no report. exit={proc.returncode}. output tail: {tail!r}",
            )

        text = report.read_text()
        passed, verdict, detail = evaluate_fb1_report(text)
        return FixtureResult("F-B1", "B", EXERCISED, passed, verdict, detail)
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --------------------------------------------------------------------------- #
# F-D1 — FC52: invoke the SHIPPED spec-provenance detector (detection only).    #
# --------------------------------------------------------------------------- #

PROVENANCE_DETECTOR = REPO_ROOT / "tools" / "check_spec_provenance.py"
_SPEC_REL = "docs/plans/demo-spec.md"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _init_fixture_repo(base_text: str, feat_text: str) -> Path:
    """Temp git repo: `master` carries base_text at the spec path, `feature`
    carries feat_text. Mirrors FC51 worktree-base (master) vs gated feature branch.
    """
    repo = Path(tempfile.mkdtemp(prefix="fd1-"))
    _git(repo, "init", "-q", "-b", "master")
    _git(repo, "config", "user.email", "fixture@example.com")
    _git(repo, "config", "user.name", "fixture")
    spec = repo / _SPEC_REL
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(base_text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base spec on master")
    _git(repo, "checkout", "-q", "-b", "feature")
    spec.write_text(feat_text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "converged spec on feature")
    return repo


def _detect(repo: Path) -> tuple[int, str]:
    """Run the SHIPPED detector on `repo`; return (exit_code, line-1 STATUS)."""
    cp = subprocess.run(
        [sys.executable, str(PROVENANCE_DETECTOR),
         "--default-branch", "master", "--original-branch", "feature",
         "--spec-path", _SPEC_REL, "--repo", str(repo)],
        capture_output=True, text=True,
    )
    out = (cp.stdout + cp.stderr).strip()
    line1 = out.splitlines()[0] if out else ""
    return cp.returncode, line1


def run_fd1(claude_bin: str = "claude") -> FixtureResult:
    """Drive the shipped FC52 detector against a diverged-spec scenario.

    EXERCISED, not MIRRORED: this invokes `tools/check_spec_provenance.py`, the
    SAME script SKILL Step 9w.9.5 now calls -- one implementation, so the fixture
    cannot pass against a copy that drifts from the gate.

    Scope: DETECTION only. The LLM inline-injection REPAIR is agent judgment and
    is out of fixture scope (plan). The fixture asserts the detector FIRES on
    drift AND a positive control (identical spec both branches) reports OK -- so
    it proves discrimination, not an always-DRIFT stub.
    """
    base = (FIXTURES_DIR / "fd1" / "worktree_base_spec.md").read_text()
    gated = (FIXTURES_DIR / "fd1" / "gated_spec.md").read_text()

    if not PROVENANCE_DETECTOR.exists():
        return FixtureResult(
            "F-D1", "FC52", EXERCISED, False, "ERROR",
            f"shipped detector missing: {PROVENANCE_DETECTOR}",
        )

    drift_repo = _init_fixture_repo(base, gated)      # base != gated -> DRIFT
    ok_repo = _init_fixture_repo(gated, gated)         # identical     -> OK (control)
    try:
        drift_code, drift_status = _detect(drift_repo)
        ok_code, ok_status = _detect(ok_repo)
    finally:
        shutil.rmtree(drift_repo, ignore_errors=True)
        shutil.rmtree(ok_repo, ignore_errors=True)

    drift_fired = drift_code == 3 and "PROVENANCE_DRIFT" in drift_status
    control_ok = ok_code == 0 and "PROVENANCE_OK" in ok_status
    passed = drift_fired and control_ok

    if passed:
        verdict, detail = "PROVENANCE_DRIFT", (
            "detector FIRED on the diverged spec (exit 3) and the identical-spec "
            "control reported PROVENANCE_OK (exit 0) — discriminates correctly"
        )
    elif not drift_fired:
        verdict, detail = drift_status or "UNKNOWN", (
            f"detector did NOT flag drift: exit={drift_code} status={drift_status!r}"
        )
    else:
        verdict, detail = ok_status or "UNKNOWN", (
            "control FAILED: detector cried drift on an identical spec "
            f"(exit={ok_code} status={ok_status!r}) — over-firing"
        )
    return FixtureResult("F-D1", "FC52", EXERCISED, passed, verdict, detail)


# --------------------------------------------------------------------------- #
# Registry + matrix                                                             #
# --------------------------------------------------------------------------- #

# fixture id -> runner callable. Phase 3 fixtures (F-B2, F-C1) land here later.
FIXTURES = {
    "F-B1": run_fb1,
    "F-D1": run_fd1,
}

# fixture id -> the track it proves. Lets the matrix tell "built but not selected
# this invocation" apart from "no fixture exists yet".
FIXTURE_TRACKS = {"F-B1": "B", "F-D1": "FC52"}


def render_matrix(results: dict[str, FixtureResult]) -> str:
    """Render the 4-row per-track fidelity matrix from the tracks that ran.

    Tracks with no implemented fixture are shown PENDING -- never given a
    fidelity label they did not earn.
    """
    built_tracks = set(FIXTURE_TRACKS.values())
    rows = []
    for track in TRACKS:
        res = next((r for r in results.values() if r.track == track), None)
        if res is None:
            if track in TRACK_STATIC:
                rows.append((track, *TRACK_STATIC[track]))
            elif track in built_tracks:
                rows.append((track, "NOT RUN", "—", "fixture exists; not selected this invocation"))
            else:
                rows.append((track, "PENDING", "—", "Phase 3 — not built"))
        else:
            outcome = "PASSED" if res.passed else "FAILED"
            rows.append((track, res.fidelity, outcome, f"{res.fixture_id}: {res.detail}"))

    w_track = max(len("Track"), max(len(r[0]) for r in rows))
    w_fid = max(len("Fidelity"), max(len(r[1]) for r in rows))
    w_out = max(len("Outcome"), max(len(r[2]) for r in rows))

    lines = ["", "Orchestration-Hardening Fixture Matrix", ""]
    header = f"| {'Track'.ljust(w_track)} | {'Fidelity'.ljust(w_fid)} | {'Outcome'.ljust(w_out)} | Evidence |"
    sep = f"|{'-' * (w_track + 2)}|{'-' * (w_fid + 2)}|{'-' * (w_out + 2)}|----------|"
    lines += [header, sep]
    for track, fid, out, ev in rows:
        lines.append(f"| {track.ljust(w_track)} | {fid.ljust(w_fid)} | {out.ljust(w_out)} | {ev} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run orchestration-hardening negative-test fixtures.",
    )
    parser.add_argument(
        "--fixture", metavar="ID",
        help="Run a single fixture (e.g. F-B1). Default: run all implemented fixtures.",
    )
    parser.add_argument(
        "--claude-bin", default="claude",
        help="Path to the Claude CLI used to invoke the real agent (default: claude).",
    )
    args = parser.parse_args(argv)

    if args.fixture:
        if args.fixture not in FIXTURES:
            print(f"unknown fixture: {args.fixture}. known: {', '.join(FIXTURES)}")
            return 2
        to_run = {args.fixture: FIXTURES[args.fixture]}
    else:
        to_run = FIXTURES

    results: dict[str, FixtureResult] = {}
    for fid, runner in to_run.items():
        print(f"running {fid} ...", flush=True)
        res = runner(claude_bin=args.claude_bin)
        results[fid] = res
        mark = "PASS" if res.passed else "FAIL"
        print(f"  {fid} [{res.fidelity}] {mark} — {res.detail}", flush=True)

    print(render_matrix(results))

    failed = [r for r in results.values() if not r.passed]
    if failed:
        names = ", ".join(r.fixture_id for r in failed)
        print(f"FAILED fixtures: {names}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
