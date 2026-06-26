#!/usr/bin/env python3
"""Disk-verify a delegated agent's terminal STATUS (Plan A, item 1).

The autopilot orchestrator delegates two heavy phases to fresh-context agents
and must decide PASS/FAIL for the run. The agent's echoed "wire" STATUS line is
unreliable (it can be forgotten or truncated), so this script moves authority to
the on-disk artifact the agent produced.

Authority model (do NOT weaken):
  * The on-disk artifact is the source of truth.
  * The wire STATUS (--wire-status) is logged context only; it NEVER vetoes a
    fresh, run-id-matching, non-FAIL artifact, and it NEVER upgrades a
    missing/stale/FAIL artifact.
  * This script checks ONLY existence, freshness, run-id, and terminal status.
    Deferred-risk adjudication remains owned by /verify-self-audit.
  * The `disconfirmer` kind is ADVISORY and carries NO terminal status line by
    contract -- so it is checked for existence + freshness + run-id ONLY (the
    status parse/accept-set steps are skipped). Its findings get their teeth
    downstream from Gate 8 in /verify-self-audit (literal-token, fail-closed),
    not from a self-reported status here.

Exit codes (kept in 1-255; 256 would wrap to 0 = a false pass):
  0  PASS              all checks held
  1  FAIL_STATUS       terminal status is a FAIL (not in the accept-set)
  2  MISSING           artifact absent or unreadable
  3  STALE             artifact older than run start (mtime < run_start_ts)
  4  NO_STATUS         no recognized terminal status token found
  5  BAD_ARGS          malformed CLI arguments
  6  RUNID_MISMATCH    embedded run-id missing or != --run-id

Usage:
  verify_delegated_status.py --artifact <path>
      --artifact-kind self-audit|assembly|disconfirmer
      --run-start-ts <epoch-seconds> --run-id <id> [--wire-status <text>]
"""

import argparse
import os
import re
import sys

EXIT_PASS = 0
EXIT_FAIL_STATUS = 1
EXIT_MISSING = 2
EXIT_STALE = 3
EXIT_NO_STATUS = 4
EXIT_BAD_ARGS = 5
EXIT_RUNID_MISMATCH = 6

# Accept-sets per artifact kind. A token NOT in the set is a FAIL.
# self-audit: PIPELINE_PASS_WITH_DEFERRED_RISK is a genuine pass (run 068 shipped
# with it); /verify-self-audit owns the deferred-risk disposition, not this script.
ACCEPT_SETS = {
    "self-audit": {"PIPELINE_PASS", "PIPELINE_PASS_WITH_DEFERRED_RISK"},
    "assembly": {"PASS"},
}

# assembly-summary.md REQUIRES the STATUS token on LINE 1 (swarm-runner contract).
# No MULTILINE: this is matched against the first line only, so a later "STATUS:" line
# cannot rescue a missing/malformed line 1 (fail-closed). Token compared whole (PASS != BYPASS).
_ASSEMBLY_STATUS_RE = re.compile(r"^\s*STATUS:\s*(\S+)")
_SELFAUDIT_STATUS_RE = re.compile(r"^\*\*Status:\*\*\s*(\S+)", re.MULTILINE)
_SELFAUDIT_RUNID_RE = re.compile(r"^\*\*Run ID:\*\*\s*(\S+)", re.MULTILINE)
# assembly run-id lives in the heading, e.g. "# Assembly Summary — Run 068"
_ASSEMBLY_RUNID_RE = re.compile(r"^#.*\bRun\s+(\S+)", re.MULTILINE)


class _Parser(argparse.ArgumentParser):
    """argparse exits 2 on error, which collides with EXIT_MISSING. Override to 5."""

    def error(self, message):
        sys.stderr.write(f"FAIL[BAD_ARGS]: {message}\n")
        sys.exit(EXIT_BAD_ARGS)


def _fail(code, reason):
    sys.stderr.write(f"FAIL[{code}]: {reason}\n")
    sys.exit(code)


def _extract_run_id(text, kind):
    # assembly embeds the run-id in its heading; self-audit AND disconfirmer both
    # use the "**Run ID:**" header line.
    rx = _ASSEMBLY_RUNID_RE if kind == "assembly" else _SELFAUDIT_RUNID_RE
    m = rx.search(text)
    return m.group(1).strip() if m else None


def _extract_status(text, kind):
    if kind == "assembly":
        # Line 1 only. A later "STATUS:" line must NOT count if line 1 is missing/malformed.
        first_line = text.split("\n", 1)[0]
        m = _ASSEMBLY_STATUS_RE.match(first_line)
        return m.group(1).strip() if m else None
    # self-audit: anchor to the "## Final Run Status" section so we read the
    # section's "**Status:**" line, not the header's "**Final Status:**" line.
    idx = text.find("## Final Run Status")
    scope = text[idx:] if idx >= 0 else text
    m = _SELFAUDIT_STATUS_RE.search(scope)
    return m.group(1).strip() if m else None


def main():
    parser = _Parser(description="Disk-verify a delegated agent's terminal STATUS.")
    parser.add_argument("--artifact", required=True, help="path to the artifact on disk")
    parser.add_argument(
        "--artifact-kind", required=True, choices=["self-audit", "assembly", "disconfirmer"]
    )
    parser.add_argument("--run-start-ts", required=True, help="run start time, epoch seconds")
    parser.add_argument("--run-id", required=True, help="this run's id (e.g. 069)")
    parser.add_argument("--wire-status", default=None, help="agent's echoed status (logged only)")
    args = parser.parse_args()

    try:
        run_start_ns = int(float(args.run_start_ts) * 1_000_000_000)
    except (TypeError, ValueError):
        _fail(EXIT_BAD_ARGS, f"--run-start-ts not numeric: {args.run_start_ts!r}")

    # 1. exists & readable (fail-closed on any OS error)
    try:
        st = os.stat(args.artifact)
    except OSError as exc:
        _fail(EXIT_MISSING, f"artifact missing/unreadable: {args.artifact} ({exc})")

    # 2. fresh — written at or after run start. >= accepts a same-instant write.
    if st.st_mtime_ns < run_start_ns:
        _fail(EXIT_STALE, f"artifact mtime {st.st_mtime_ns}ns < run_start {run_start_ns}ns (stale)")

    try:
        with open(args.artifact, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        _fail(EXIT_MISSING, f"artifact unreadable: {args.artifact} ({exc})")

    # 3. run-id match (fail-closed if the artifact embeds none)
    embedded = _extract_run_id(text, args.artifact_kind)
    if embedded is None:
        _fail(EXIT_RUNID_MISMATCH, "no embedded run-id found in artifact")
    if embedded != args.run_id:
        _fail(EXIT_RUNID_MISMATCH, f"embedded run-id {embedded!r} != --run-id {args.run_id!r}")

    # disconfirmer is advisory: no terminal status line by contract. Existence +
    # freshness + run-id (checks 1-3 above) are the whole verdict; skip status.
    # Gate 8 in /verify-self-audit enforces its findings (literal-token, fail-closed).
    if args.artifact_kind == "disconfirmer":
        if args.wire_status is not None:
            sys.stderr.write(f"note: wire-status logged, non-decisive: {args.wire_status!r}\n")
        print(f"PASS: {args.artifact_kind} {args.artifact} run_id={embedded} (advisory; no status)")
        sys.exit(EXIT_PASS)

    # 4. status parses
    status = _extract_status(text, args.artifact_kind)
    if status is None:
        _fail(EXIT_NO_STATUS, "no recognized terminal status token found")

    # 5. status non-FAIL
    accept = ACCEPT_SETS[args.artifact_kind]
    if status not in accept:
        _fail(EXIT_FAIL_STATUS, f"status {status!r} not in accept-set {sorted(accept)}")

    # PASS. The wire status is logged but did not affect the verdict.
    if args.wire_status is not None:
        sys.stderr.write(f"note: wire-status logged, non-decisive: {args.wire_status!r}\n")
    print(f"PASS: {args.artifact_kind} {args.artifact} status={status} run_id={embedded}")
    sys.exit(EXIT_PASS)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # fail-closed: an unexpected crash must never read as PASS
        sys.stderr.write(f"FAIL[{EXIT_MISSING}]: unexpected error: {exc}\n")
        sys.exit(EXIT_MISSING)
