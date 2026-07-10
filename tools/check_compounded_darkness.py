#!/usr/bin/env python3
"""
Compounded-darkness gate signal (080-W5).

Each of a run's THREE independent verification surfaces has its own standing,
routine waiver:
  * spec-eval        -> ENV_ERROR / RETRY / WARN_UNSCORABLE (no API key, etc.)
  * spec-provenance  -> inline-injection FALLBACK (sanctioned when master UNCHANGED)
  * dynamic tests    -> FIREBREAK_DEFERRED (smoke deferred under an active firebreak)

Any ONE dark surface is unremarkable. But when ALL THREE are dark at once, the
run's correctness rests entirely on by-construction claims + static analysis --
no independent mechanism produced a verdict. Run 080's disconfirmer raised this
(docs/reports/080/disconfirmer.md#D5); the self-audit filed it as 080-W5 with the
note "the compounded state is not currently detectable by existing gates." This
script is that detector.

It reads the REAL on-disk artifacts (not hand-passed strings -- a context-saturated
orchestrator drops manual bookkeeping, run 050), classifies each surface LIT/DARK by
allowlisting its "produced a real verdict" state, and reports COMPOUNDED_DARKNESS iff
all three are DARK.

OBSERVABILITY-ONLY: this NEVER blocks. It always exits 0 and prints a STATUS line;
the caller folds a WARN into the tail when STATUS is COMPOUNDED_DARKNESS.

  A surface is LIT (produced a usable verdict) iff:
    spec-eval        -- a spec-eval-verification.md (PASS) OR a spec-eval-gate.json
                        with status PASS|FAIL exists (nested under spec-eval-*/ or flat)
    spec-provenance  -- spec-provenance.md STATUS is PROVENANCE_OK (a real equivalence
                        proof) and NOT a *_FALLBACK
    dynamic tests    -- smoke-test.md (or smoke-rerun-postteardown.md) STATUS is PASS|FAIL
                        (the tests actually executed against the run's code)
  Everything else (fallback / deferred / no-verdict / absent) is DARK -- the safe
  default: a false WARN is cheap, a missed compounded-darkness is the risk we close.

Usage:
  check_compounded_darkness.py --reports-dir docs/reports/<run-id>
      [--out <path>]                       # default <reports-dir>/compounded-darkness.md
      [--spec-eval-status <text>]          # override (else read from disk)
      [--provenance-status <text>]         # override (else read from disk)
      [--dynamic-status <text>]            # override (else read from disk)
"""

import argparse
import glob
import json
import os
import re
import sys

EXIT_OK = 0
EXIT_BAD_ARGS = 5

_STATUS_RE = re.compile(r"^\s*STATUS:\s*(.+?)\s*$")
_EXECUTED_VERDICTS = {"PASS", "FAIL"}


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write(f"FAIL[BAD_ARGS]: {message}\n")
        sys.exit(EXIT_BAD_ARGS)


def _read_status_line(path):
    """Return the full text after `STATUS:` on the file's first line, or None."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            first = f.readline()
    except OSError:
        return None
    m = _STATUS_RE.match(first)
    return m.group(1).strip() if m else None


def _first_token(status_text):
    """The leading whitespace/`--`-delimited token of a STATUS text, upper-cased."""
    if not status_text:
        return None
    return re.split(r"[\s-]", status_text.strip(), maxsplit=1)[0].upper()


def classify_spec_eval(reports_dir, override):
    """LIT iff a real spec-eval verdict artifact exists (PASS verification file, or a
    gate json whose status is PASS|FAIL). ENV_ERROR/RETRY write no artifact -> DARK."""
    if override is not None:
        tok = _first_token(override)
        lit = tok in _EXECUTED_VERDICTS
        return ("LIT" if lit else "DARK", f"override STATUS: {override}")

    # spec-eval writes into a nested spec-eval-<ts>/ dir (Path(output_dir)/run_id);
    # tolerate both the nested and a flat layout.
    verif = (glob.glob(os.path.join(reports_dir, "spec-eval-*", "spec-eval-verification.md"))
             + glob.glob(os.path.join(reports_dir, "spec-eval-verification.md")))
    if verif:
        return ("LIT", f"verdict artifact: {os.path.relpath(sorted(verif)[0], reports_dir)}")

    gates = (glob.glob(os.path.join(reports_dir, "spec-eval-*", "spec-eval-gate.json"))
             + glob.glob(os.path.join(reports_dir, "spec-eval-gate.json")))
    for g in sorted(gates):
        try:
            with open(g, encoding="utf-8") as f:
                status = str(json.load(f).get("status", "")).upper()
        except (OSError, ValueError):
            continue
        if any(v in status for v in _EXECUTED_VERDICTS):   # "GateStatus.PASS" etc.
            return ("LIT", f"gate verdict {status} in {os.path.relpath(g, reports_dir)}")

    return ("DARK", "no spec-eval verdict artifact (ENV_ERROR / RETRY / absent)")


def classify_provenance(reports_dir, override):
    """LIT iff the provenance channel produced a real equivalence proof
    (PROVENANCE_OK, not a *_FALLBACK). DRIFT/REPAIRED/FALLBACK/absent -> DARK."""
    status = override if override is not None else \
        _read_status_line(os.path.join(reports_dir, "spec-provenance.md"))
    if not status:
        return ("DARK", "spec-provenance.md absent or no STATUS line")
    up = status.upper()
    lit = ("PROVENANCE_OK" in up) and ("FALLBACK" not in up)
    return ("LIT" if lit else "DARK", f"STATUS: {status}")


def classify_dynamic(reports_dir, override):
    """LIT iff dynamic tests actually executed against the run's code (smoke STATUS
    PASS|FAIL). FIREBREAK_DEFERRED / deferred / absent -> DARK."""
    if override is not None:
        tok = _first_token(override)
        return ("LIT" if tok in _EXECUTED_VERDICTS else "DARK", f"override STATUS: {override}")
    for name in ("smoke-test.md", "smoke-rerun-postteardown.md"):
        status = _read_status_line(os.path.join(reports_dir, name))
        if status and _first_token(status) in _EXECUTED_VERDICTS:
            return ("LIT", f"{name} STATUS: {status}")
    smoke = _read_status_line(os.path.join(reports_dir, "smoke-test.md"))
    return ("DARK", f"smoke-test.md STATUS: {smoke}" if smoke
            else "no executed dynamic tests against run code (deferred / absent)")


def _render(run_id, compounded, surfaces):
    lines = [f"STATUS: {'COMPOUNDED_DARKNESS' if compounded else 'OK'}", ""]
    lines.append(f"# Compounded-Darkness Check — run {run_id}")
    lines.append("")
    lines.append("All three independent verification surfaces dark: "
                 f"{'YES' if compounded else 'no'}")
    lines.append("")
    lines.append("| Surface | State | Evidence |")
    lines.append("|---------|-------|----------|")
    for name, (state, evidence) in surfaces:
        lines.append(f"| {name} | {state} | {evidence} |")
    lines.append("")
    if compounded:
        lines.append("**WARN (080-W5):** every independent verification mechanism "
                     "(spec-eval, spec-provenance, dynamic tests) produced no verdict "
                     "this run. Build correctness rests entirely on by-construction "
                     "claims and static analysis. Each waiver is individually routine; "
                     "the compounded state is not. For a throwaway governance vehicle "
                     "this may be acceptable, but for any build whose app carries real "
                     "stakes, light at least one surface (provide an API key for "
                     "spec-eval, run the smoke suite post-teardown, or produce a real "
                     "provenance proof) before trusting the pass status.")
    else:
        lines.append("At least one independent verification surface produced a real "
                     "verdict; not compounded darkness.")
    return "\n".join(lines) + "\n"


def main():
    p = _Parser(description="Flag when all three independent verification surfaces "
                            "are simultaneously dark (080-W5).")
    p.add_argument("--reports-dir", required=True,
                   help="the run's report dir, e.g. docs/reports/<run-id>")
    p.add_argument("--out", default=None,
                   help="report path (default <reports-dir>/compounded-darkness.md)")
    p.add_argument("--spec-eval-status", default=None)
    p.add_argument("--provenance-status", default=None)
    p.add_argument("--dynamic-status", default=None)
    args = p.parse_args()

    reports_dir = args.reports_dir
    run_id = os.path.basename(os.path.normpath(reports_dir)) or "unknown"

    surfaces = [
        ("spec-eval", classify_spec_eval(reports_dir, args.spec_eval_status)),
        ("spec-provenance", classify_provenance(reports_dir, args.provenance_status)),
        ("dynamic tests", classify_dynamic(reports_dir, args.dynamic_status)),
    ]
    compounded = all(state == "DARK" for _, (state, _ev) in surfaces)

    report = _render(run_id, compounded, surfaces)
    out = args.out or os.path.join(reports_dir, "compounded-darkness.md")
    try:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(report)
    except OSError as exc:
        sys.stderr.write(f"WARN: could not write {out}: {exc}\n")

    # OBSERVABILITY-ONLY: always exit 0. The STATUS line on stdout is the signal.
    print(f"STATUS: {'COMPOUNDED_DARKNESS' if compounded else 'OK'}")
    for name, (state, evidence) in surfaces:
        print(f"  {name}: {state} -- {evidence}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
