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
import json
import os
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

# Honest status for tracks with no automated fixture. The fidelity column is
# reserved for the canonical labels a fixture can EARN (EXERCISED /
# SPIKE-VALIDATED / PROSE-ASSERTED / MIRRORED). A track with NO fixture earned no
# fidelity, so its fidelity cell is "—" and its real coverage provenance
# ("FIELD+SPIKE") lives in the evidence column — never in the fidelity column,
# never rounded up to EXERCISED. (fidelity, outcome, evidence)
#   Track A: P-accept. The cherry-pick assembly is agent-prose in swarm-runner.md;
#   exercising it as-shipped needs a share-not-fork extraction (a deliberate
#   hardening refactor with its own real-build validation), NOT a fixture.
TRACK_STATIC = {
    "A": ("—", "NOT FIXTURED",
          "FIELD+SPIKE (P-accept): cherry-pick assembly is agent-prose "
          "(swarm-runner.md:76-138); field-proven runs 069/070 + spikes. No fixture, "
          "so no fidelity is claimed — pending a deliberate P-extract refactor."),
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


def _fc50_surface_status(lines: list[str]) -> str | None:
    """Return the FC50 surface's STATUS cell (upper-cased), or None if absent.
    Reads the Results-table row for the Orchestration-Entrypoint surface."""
    for ln in lines:
        s = ln.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) >= 2 and _FC50_SURFACE.search(cells[0]):
                return cells[1].upper()
    return None


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


def _invoke_spec_completeness_checker(
    fixture_dir: Path, claude_bin: str, timeout: int, prefix: str,
) -> tuple[str | None, str]:
    """Run the SHIPPED spec-completeness-checker agent on a fixture spec.

    Faithfulness: `claude -p --agent spec-completeness-checker` loads
    `.claude/agents/spec-completeness-checker.md` verbatim as the session agent --
    the artifact the autopilot pipeline runs (runs 069/070), no reimplementation.
    Returns (report_text, "") on success, or (None, error_detail) on failure.
    Both F-B1 and F-B2 share this; only the report-evaluation differs.
    """
    work = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        spec = work / "spec.md"
        build_tracking = work / "build_tracking.md"
        reports = work / "reports"
        reports.mkdir()
        shutil.copy(fixture_dir / "spec.md", spec)
        shutil.copy(fixture_dir / "build_tracking.md", build_tracking)

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
            return None, f"could not invoke '{claude_bin}' -- is the Claude CLI installed?"
        except subprocess.TimeoutExpired:
            return None, f"agent invocation timed out after {timeout}s"

        report = reports / "spec-completeness-check.md"
        if not report.exists():
            tail = (proc.stdout or proc.stderr or "").strip()[-400:]
            return None, f"agent wrote no report. exit={proc.returncode}. output tail: {tail!r}"
        return report.read_text(), ""
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_fb1(claude_bin: str = "claude", timeout: int = 420, **_) -> FixtureResult:
    """F-B1: the gate must FAIL on the FC50 surface naming the unpinned entrypoint.
    PASSES when the guard catches it; if it returns PASS/N/A, Track B is unproven.
    """
    text, err = _invoke_spec_completeness_checker(
        FIXTURES_DIR / "fb1", claude_bin, timeout, "fb1-")
    if text is None:
        return FixtureResult("F-B1", "B", EXERCISED, False, "ERROR", err)
    passed, verdict, detail = evaluate_fb1_report(text)
    return FixtureResult("F-B1", "B", EXERCISED, passed, verdict, detail)


def evaluate_fb2_report(text: str) -> tuple[bool, str, str]:
    """F-B2 documents the FC50 blind spot: a wholly-OMITTED entrypoint row.

    Check 1b is a signature-PRESENCE guard, not a call-site classifier
    (spec-completeness-checker.md:88-90) -- with zero `orchestration entrypoint`
    rows it returns N/A, NOT FAIL. The honest outcome is N/A: the guard reports
    "I can't see this" rather than a false PASS that hides the omission. A
    non-N/A status here would misreport the blind spot.
    """
    status = _fc50_surface_status(text.splitlines())
    if status == "N/A":
        return True, "N/A", (
            "FC50 surface returned N/A on a wholly-omitted entrypoint — the "
            "documented blind spot reported honestly (not a false PASS). The "
            "downstream backstop is the assembly contract-check "
            "(PROSE-ASSERTED — agent-prose, not exercised here)."
        )
    if status is None:
        return False, "UNKNOWN", "could not find the FC50/Orchestration-Entrypoints surface row"
    if status == "FAIL":
        return False, "FAIL", (
            "FC50 surface FAILED — unexpected: F-B2 declares NO entrypoint row, so "
            "Check 1b should return N/A. (Did the spec accidentally declare one?)"
        )
    return False, status, (
        f"FC50 surface is {status!r}, expected N/A — a non-N/A here misreports the "
        "blind spot (a false PASS would hide the omitted entrypoint)"
    )


def run_fb2(claude_bin: str = "claude", timeout: int = 420, **_) -> FixtureResult:
    """F-B2: with a wholly-omitted entrypoint row, the gate must return N/A for
    FC50 (the honest blind spot), never a false PASS. Exercises the real agent."""
    text, err = _invoke_spec_completeness_checker(
        FIXTURES_DIR / "fb2", claude_bin, timeout, "fb2-")
    if text is None:
        return FixtureResult("F-B2", "B", EXERCISED, False, "ERROR", err)
    passed, verdict, detail = evaluate_fb2_report(text)
    return FixtureResult("F-B2", "B", EXERCISED, passed, verdict, detail)


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


def run_fd1(claude_bin: str = "claude", **_) -> FixtureResult:
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
# F-C1 — Track C: scorer (layer 1, EXERCISED) + advisory demotion (layer 2).    #
# --------------------------------------------------------------------------- #

SKILL_MD = REPO_ROOT / ".claude" / "skills" / "autopilot" / "SKILL.md"
SPEC_EVAL_GATE = HARNESS_DIR / "spec_eval_gate.py"
# Stable substrings that encode the advisory/non-blocking contract in Step 9w.8 +
# the Step 10w precondition. If either is gone, the demotion was weakened.
_ADVISORY_CONTRACT = ("ADVISORY (non-blocking)", "NEVER aborts the pipeline")

# Layer-1 (scorer) outcome classes. The split is the point of review issue #1:
# a SCORER_DEFECT must NOT be hidden as an environment miss. Only genuine
# environment unavailability is non-failing; everything else where the scorer
# was reachable but produced no verdict is a defect that FAILS the fixture.
L1_EXERCISED = "EXERCISED"        # scorer ran in a working env and produced a verdict + JSON
L1_ENV_UNAVAILABLE = "ENV_UNAVAILABLE"  # env/transport: no API key, timeout, connection — could not exercise
L1_SCORER_DEFECT = "SCORER_DEFECT"      # reachable but no verdict (WARN_UNSCORABLE/RETRY/no-JSON/malformed)


def _valid_gate_statuses() -> set[str]:
    """The SHIPPED GateStatus enum values, read from the gate's own models so the
    valid set can NEVER drift from the scorer (share-not-fork — the same principle
    the whole suite rests on). Falls back to the known set only if `models` is not
    importable in this context. NOTE: ENV_ERROR is an exit code, not a GateStatus,
    so it is correctly absent here — it never appears in the JSON report.
    """
    try:
        from models import GateStatus  # co-located in eval-harness/; authoritative
        return {s.value for s in GateStatus}
    except Exception:
        return {"PASS", "FAIL", "WARN_UNSCORABLE", "RETRY"}


def _classify_scorer_report(status, report_name: str) -> tuple[str, str]:
    """Classify a scorer run that DID write a JSON report, by its `status` field.
    A written report means the scorer reached scoring — but the status must still
    be a KNOWN GateStatus. A non-empty but unrecognized status is schema drift (a
    defect), NOT a verdict, and must not read as EXERCISED success (the hole Codex
    flagged). Any non-string/missing status (a drifted schema) is likewise a
    defect — a schema-drift defense must not itself crash on drifted data. Pure +
    unit-tested.
    """
    if not isinstance(status, str) or not status:
        return L1_SCORER_DEFECT, f"scorer JSON has no valid status field ({report_name})"
    valid = _valid_gate_statuses()
    if status not in valid:
        return L1_SCORER_DEFECT, (
            f"scorer JSON status {status!r} is not a known GateStatus "
            f"{sorted(valid)} — schema drift, not a verdict ({report_name})"
        )
    return L1_EXERCISED, (
        f"scorer ran and produced verdict={status!r} + JSON report ({report_name})"
    )


def _check_advisory_prose() -> tuple[bool, str]:
    """Layer 2 (PROSE-ASSERTED): the advisory/non-blocking demotion lives in the
    Step 9w.8 wrapper prose, NOT in spec_eval_gate.py (the script still exits 1 on
    non-PASS). So the only honest way to assert the demotion is to check the
    shipped SKILL contract text. Deterministic and free.
    """
    if not SKILL_MD.exists():
        return False, f"SKILL.md not found: {SKILL_MD}"
    # Normalize whitespace so a contract phrase that wraps across a line break
    # (e.g. "it NEVER\naborts the pipeline") still matches.
    text = re.sub(r"\s+", " ", SKILL_MD.read_text())
    missing = [s for s in _ADVISORY_CONTRACT if s not in text]
    if missing:
        return False, f"advisory contract weakened — missing from SKILL.md: {missing}"
    return True, "advisory/non-blocking contract present in SKILL Step 9w.8"


def _run_scorer(timeout: int = 420) -> tuple[str, str]:
    """Layer 1: invoke the real spec_eval_gate.py on the vague fixture spec,
    bounded. Returns (outcome, detail) where outcome is one of L1_EXERCISED /
    L1_ENV_UNAVAILABLE / L1_SCORER_DEFECT.

    The fixture spec is DESIGNED to be scorable (>= 1 HIGH claim with
    --min-high-claims 1). So WARN_UNSCORABLE (extraction no longer finds the
    claims), RETRY (the gate never produced a verdict after its own retries), a
    missing/unreadable JSON report, or a malformed status are all SCORER DEFECTS
    on this controlled input — NOT environment misses — and must surface, never
    pass silently (review issue #1). Only a genuinely unreachable environment
    (no API key / ENV_ERROR exit 2, a hard timeout, or a transport/connection
    error) is L1_ENV_UNAVAILABLE: the scorer's logic was never exercised, so it
    is neither a pass nor a defect.
    """
    if not SPEC_EVAL_GATE.exists():
        return L1_SCORER_DEFECT, f"shipped scorer missing: {SPEC_EVAL_GATE}"
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return L1_ENV_UNAVAILABLE, "ANTHROPIC_API_KEY not set — scorer not exercised (env)"
    out_dir = Path(tempfile.mkdtemp(prefix="fc1-"))
    try:
        cmd = [
            sys.executable, str(SPEC_EVAL_GATE),
            str(FIXTURES_DIR / "fc1" / "vague_spec.md"),
            "--output-dir", str(out_dir),
            "--cost-cap", "0.50",
            "--min-high-claims", "1",  # let a tiny spec reach the scorer cheaply
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return L1_ENV_UNAVAILABLE, f"scorer timed out after {timeout}s (transport/env)"

        reports = list(out_dir.glob("spec-eval-*/spec-eval-gate.json"))
        if reports:
            try:
                data = json.loads(reports[0].read_text())
            except (json.JSONDecodeError, OSError) as exc:
                return L1_SCORER_DEFECT, f"scorer wrote unreadable JSON: {exc}"
            # A report that is not a JSON object is itself schema drift.
            status = data.get("status") if isinstance(data, dict) else None
            return _classify_scorer_report(status, reports[0].name)

        # No gate JSON: the scorer did not reach a verdict. Classify the cause.
        return _classify_scorer_miss(proc.returncode, proc.stdout + proc.stderr)
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


# Clear environment/transport markers that mean the scorer was never exercised
# (a present-but-INVALID key, DNS, refused connection) — NOT a scorer defect.
_ENV_FAULT = re.compile(
    r"AuthenticationError|invalid x-api-key|\b401\b|PermissionDenied|"
    r"getaddrinfo|Could not resolve|Connection refused|Network is unreachable|"
    r"Temporary failure in name resolution",
    re.IGNORECASE,
)


def _classify_scorer_miss(returncode: int, blob: str) -> tuple[str, str]:
    """Classify a scorer run that produced NO gate JSON. Pure + unit-tested.

    Order is load-bearing (review issue #1): WARN_UNSCORABLE and RETRY are checked
    BEFORE the auth/transport markers, so a RETRY whose error details happen to
    mention a connection cannot be reclassified as "environment" and slip through
    as a non-failing INCONCLUSIVE. Only the gate's own ENV_ERROR (exit 2) or a
    clear auth/transport fault with no WARN/RETRY present is environment.
    """
    if returncode == 2 or "ENV_ERROR" in blob:
        return L1_ENV_UNAVAILABLE, "scorer returned ENV_ERROR (env) — scorer not exercised"
    if "WARN_UNSCORABLE" in blob:
        return L1_SCORER_DEFECT, (
            "scorer returned WARN_UNSCORABLE on a spec built to be scorable — "
            "extraction regression (no verdict)"
        )
    if "RETRY" in blob:
        return L1_SCORER_DEFECT, (
            "scorer returned RETRY (no verdict after its own retries) — not silently passed"
        )
    if _ENV_FAULT.search(blob):
        return L1_ENV_UNAVAILABLE, "scorer hit an auth/transport fault (env) — scorer not exercised"
    return L1_SCORER_DEFECT, (
        f"scorer produced no verdict/JSON. exit={returncode}. tail: {blob.strip()[-300:]!r}"
    )


def run_fc1(claude_bin: str = "claude", with_api: bool = False, **_) -> FixtureResult:
    """Track C is two-layer (per the deepen pass):
      * layer 2 (always, free): the advisory/non-blocking DEMOTION — the real
        Track-C behavior — is orchestrator-prose, so it is PROSE-ASSERTED against
        the shipped SKILL contract.
      * layer 1 (opt-in via --with-api): the scorer itself is real callable
        infrastructure, EXERCISED by invoking spec_eval_gate.py. Gated behind a
        flag because it makes real (bounded) LLM calls — the regression net stays
        hermetic and free by default.

    Outcome policy (review issue #1): layer 2 must hold. With --with-api, a
    L1_SCORER_DEFECT FAILS the fixture (a real scorer regression is never hidden);
    L1_ENV_UNAVAILABLE does not fail (the scorer was never exercised) but is
    reported, never dressed up as EXERCISED.
    """
    l2_ok, l2_detail = _check_advisory_prose()

    if not with_api:
        fidelity = PROSE_ASSERTED
        detail = f"layer2 {l2_detail}; layer1 scorer run is opt-in (--with-api)"
        return FixtureResult("F-C1", "C", fidelity, l2_ok, "ADVISORY-PROSE", detail)

    l1_outcome, l1_detail = _run_scorer()
    passed = l2_ok and l1_outcome != L1_SCORER_DEFECT
    if l1_outcome == L1_EXERCISED:
        fidelity = f"{EXERCISED}(L1)+{PROSE_ASSERTED}(L2)"
    else:
        # ENV_UNAVAILABLE or SCORER_DEFECT — layer 1 was NOT exercised; never
        # round up to EXERCISED.
        fidelity = f"{PROSE_ASSERTED}(L2)"
    detail = f"layer1 [{l1_outcome}] {l1_detail}; layer2 {l2_detail}"
    return FixtureResult("F-C1", "C", fidelity, passed, "ADVISORY-PROSE+SCORER", detail)


# --------------------------------------------------------------------------- #
# Registry + matrix                                                             #
# --------------------------------------------------------------------------- #

# fixture id -> runner callable.
FIXTURES = {
    "F-B1": run_fb1,
    "F-B2": run_fb2,
    "F-D1": run_fd1,
    "F-C1": run_fc1,
}

# fixture id -> the track it proves. Lets the matrix tell "built but not selected
# this invocation" apart from "no fixture exists yet".
FIXTURE_TRACKS = {"F-B1": "B", "F-B2": "B", "F-D1": "FC52", "F-C1": "C"}


def render_matrix(results: dict[str, FixtureResult]) -> str:
    """Render the 4-row per-track fidelity matrix from the tracks that ran.

    Tracks with no implemented fixture are shown PENDING -- never given a
    fidelity label they did not earn.
    """
    built_tracks = set(FIXTURE_TRACKS.values())
    rows = []
    for track in TRACKS:
        track_res = [r for r in results.values() if r.track == track]
        if not track_res:
            if track in TRACK_STATIC:
                rows.append((track, *TRACK_STATIC[track]))
            elif track in built_tracks:
                rows.append((track, "NOT RUN", "—", "fixture exists; not selected this invocation"))
            else:
                rows.append((track, "PENDING", "—", "Phase 3 — not built"))
        else:
            # A track may carry several fixtures (e.g. B = F-B1 + F-B2). The track
            # PASSES only if every fixture passed; fidelity joins the distinct
            # labels earned across them.
            all_pass = all(r.passed for r in track_res)
            outcome = "PASSED" if all_pass else "FAILED"
            fids = sorted({r.fidelity for r in track_res})
            fidelity = " / ".join(fids)
            evidence = "; ".join(
                f"{r.fixture_id} {'PASS' if r.passed else 'FAIL'}: {r.detail}"
                for r in sorted(track_res, key=lambda r: r.fixture_id)
            )
            rows.append((track, fidelity, outcome, evidence))

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
    lines.append(
        "Fidelity column = the canonical label a fixture EARNED "
        "(EXERCISED / SPIKE-VALIDATED / PROSE-ASSERTED / MIRRORED). "
        "'—', PENDING, NOT RUN are no-result sentinels — no fidelity is claimed; "
        "see Evidence for a non-fixtured track's coverage provenance."
    )
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
    parser.add_argument(
        "--with-api", action="store_true",
        help="Run opt-in layers that make real (bounded) LLM calls — currently "
             "F-C1 layer 1 (the spec-eval scorer). Off by default so the suite "
             "stays hermetic and free.",
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
        res = runner(claude_bin=args.claude_bin, with_api=args.with_api)
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
