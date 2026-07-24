#!/usr/bin/env python3
"""Tool-enforce that a swarm run's pitfall harvest is genuine (FC-harvest gate).

Path-B swarm runs justify their cost by HARVESTING pitfalls -- real, evidence-backed
cross-agent failure classes -- not by producing a green build. Run 083 self-certified
its harvest (docs/reports/083/harvest-verification.md) because this tool did not exist;
the disconfirmer (D4) flagged the self-certification and the self-audit accepted it only
as a throwaway-vehicle tradeoff (083-W5). This script replaces that self-certification
with a deterministic gate so a future run cannot wave through a hollow or padded harvest.

It enforces FOUR checks against the run's REAL findings (a finding is REAL iff its
`status` cell begins with the token REAL -- near-miss / benign / resolved-benign / infra
notes do NOT count):

  (a) BREADTH   -- >= --min-real findings, each a DISTINCT root_cause_id.
  (b) BIJECTION -- every REAL finding's root_cause_id resolves to its own
                   `**root_cause_id:**` row in BUILD_TRACKING.md's ## FAILURES section
                   (no finding without a tracked failure; no two findings sharing one).
  (c) EVIDENCE  -- every REAL finding's `evidence` cell cites at least one artifact that
                   RESOLVES ON DISK: a repo-relative path, or a file:line reference whose
                   file exists (anti-gaming -- "was injected" with no resolvable file fails).
  (d) NET-NEW   -- >= --min-netnew of the REAL findings are net-new failure classes,
                   verified against the FROZEN pitfalls-baseline.txt (a self-declared
                   "net-new" word is NOT trusted; the fc_id must reference an FC number
                   absent from the baseline set, or the literal token `net-new`).

The harvest data contract (harvest-findings.md), which the SKILL harvest-authoring step
must satisfy so this gate can read it deterministically:
  * A GitHub pipe table whose header row includes columns: root_cause_id, fc_id, status,
    evidence (column order is free; matched by name; `id` recommended for messages).
  * status begins with REAL for every counted failure; benign/near-miss/infra otherwise.
  * fc_id records the FINAL registered class: a NEW class uses its new id (e.g. FC68);
    a variant uses the existing id (e.g. FC58 / FC58-variant). This is what makes (d)
    verifiable against the baseline rather than by an author's say-so.
  * evidence cites a resolvable file path or file:line for each REAL finding.

Exit codes (kept in 1-255; 256 would wrap to 0 = a false PASS):
  0  PASS         all four checks held
  1  FAIL         one or more checks failed (STATUS line names which)
  2  INPUT_ERROR  a required input file is missing/unreadable, or no findings table
  5  BAD_ARGS     malformed CLI arguments

Usage:
  verify_harvest.py --reports-dir docs/reports/<run-id>
      [--root <repo-root>]                 # base for resolving evidence paths (default cwd)
      [--build-tracking <path>]            # default <root>/BUILD_TRACKING.md
      [--baseline <path>]                  # default <reports-dir>/pitfalls-baseline.txt
      [--out <path>]                       # default <reports-dir>/harvest-verification.md
      [--min-real N] [--min-netnew N]      # default 5 / 2
"""

import argparse
import os
import re
import sys

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_INPUT_ERROR = 2
EXIT_BAD_ARGS = 5

# A finding counts as a REAL failure iff its status cell begins with this token.
_REAL_RE = re.compile(r"^\s*REAL\b", re.IGNORECASE)
# FC references anywhere in a cell, e.g. "FC58", "FC58-family", "FC30/FC5".
_FC_RE = re.compile(r"FC(\d+)")
# A file:line reference, e.g. "swarmlimit/database.py:43" or "__init__.py:48-63".
_FILELINE_RE = re.compile(r"([A-Za-z0-9_./-]+\.[A-Za-z0-9_]+):(\d+)")
# A bare path-like token (has a slash and a dot), e.g. "docs/reports/083/c2-smoke-report.md".
_PATH_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+")
# A self-declared net-new marker (word or hyphen form).
_NETNEW_WORD_RE = re.compile(r"net[-\s]?new", re.IGNORECASE)
# BUILD_TRACKING FAILURES rows pin the id as "**root_cause_id:** RC-..." (· or newline ends it).
_BT_RC_RE = re.compile(r"\*\*root_cause_id:\*\*\s*([A-Za-z0-9_-]+)")


class _Parser(argparse.ArgumentParser):
    """argparse exits 2 on error, which collides with EXIT_INPUT_ERROR. Override to 5."""

    def error(self, message):
        sys.stderr.write(f"STATUS: FAIL -- BAD_ARGS: {message}\n")
        sys.exit(EXIT_BAD_ARGS)


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _parse_table(text):
    """Parse the harvest table's data rows, keyed by lower-cased header name.

    Once the header (the pipe row carrying a root_cause_id column) is found, every
    later pipe row whose column count matches the header is a data row -- EVEN across
    intervening prose. Real harvest logs interleave a "Note:" paragraph between row
    groups (run 083 did); stopping at the first prose line silently drops the tail
    (a truncation the "no silent caps" rule forbids). Separator rows (---) and any
    repeated header row are skipped. Returns None if no root_cause_id table exists.
    """
    header = None
    rows = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue                        # prose -> skip, do NOT terminate the table
        cells = [c.strip() for c in s.strip("|").split("|")]
        low = [c.lower() for c in cells]
        if header is None:
            if "root_cause_id" in low:
                header = low
            continue
        if set(s) <= set("|-: "):           # separator row like |---|---|
            continue
        if "root_cause_id" in low:          # a repeated header row -> not data
            continue
        if len(cells) != len(header):       # arity mismatch -> a different table
            continue
        rows.append({header[i]: cells[i] for i in range(len(header))})
    return rows if header is not None else None


def _real_rows(rows):
    return [r for r in rows if _REAL_RE.match(r.get("status", ""))]


def _baseline_fc_ids(text):
    """Set of FC integer ids frozen at run start (from the failure_class_ids line)."""
    m = re.search(r"failure_class_ids:\s*(.+)", text)
    if not m:
        return None
    return {int(n) for n in _FC_RE.findall(m.group(1))}


def _failures_section(bt_text):
    """The text of BUILD_TRACKING's ## FAILURES section (up to the next ## heading)."""
    start = bt_text.find("## FAILURES")
    if start < 0:
        return None
    rest = bt_text[start + len("## FAILURES"):]
    nxt = re.search(r"^##\s", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def _failure_rows(failures_text):
    """Split the ## FAILURES section into per-failure blocks on `###`(+) headings and
    return, for each block that pins any, the SET of root_cause_ids it declares.

    Row-SCOPED on purpose: BIJECTION must be 1:1, so the id extraction has to prove one
    tracked failure ROW per finding. A global `findall` over the whole section would let a
    single row that lists two `**root_cause_id:**` labels satisfy two different REAL
    findings (and would miss "one finding spread across rows"). Splitting per block closes
    that. Blocks with no `**root_cause_id:**` (advisory / WARN notes) contribute no row.
    """
    rows = []
    for block in re.split(r"(?m)^#{3,}\s", failures_text):
        rcs = set(_BT_RC_RE.findall(block))
        if rcs:
            rows.append(rcs)
    return rows


def _evidence_resolves(evidence, root, reports_dir):
    """True iff the evidence cell cites a file that exists under root or reports_dir."""
    candidates = set()
    for m in _FILELINE_RE.finditer(evidence):
        candidates.add(m.group(1))
    for m in _PATH_RE.finditer(evidence):
        candidates.add(m.group(0))
    for cand in candidates:
        cand = cand.rstrip(".,);:")
        for base in (root, reports_dir):
            if os.path.exists(os.path.join(base, cand)) or os.path.exists(cand):
                return True
    return False


def _is_net_new(fc_id, baseline_ids):
    """A finding is net-new iff it names an FC absent from the frozen baseline, or the
    literal net-new marker. A self-declared marker alone is accepted only when the cell
    carries NO in-baseline FC id (an author cannot relabel an existing class as net-new)."""
    fcs = [int(n) for n in _FC_RE.findall(fc_id)]
    if any(n not in baseline_ids for n in fcs):
        return True
    if fcs:                       # every FC named is in-baseline -> a variant, not net-new
        return False
    return bool(_NETNEW_WORD_RE.search(fc_id))


def _check(reports_dir, root, bt_path, baseline_path, min_real, min_netnew):
    """Run the four checks. Returns (passed, reason, detail_lines)."""
    detail = []

    # ---- load inputs (fail-closed on any missing/unreadable required file) ----
    findings_path = os.path.join(reports_dir, "harvest-findings.md")
    try:
        rows = _parse_table(_read(findings_path))
    except OSError as exc:
        return None, f"INPUT_ERROR: cannot read {findings_path} ({exc})", detail
    if rows is None:
        return None, f"INPUT_ERROR: no root_cause_id table in {findings_path}", detail
    try:
        baseline_ids = _baseline_fc_ids(_read(baseline_path))
    except OSError as exc:
        return None, f"INPUT_ERROR: cannot read baseline {baseline_path} ({exc})", detail
    if not baseline_ids:
        return None, f"INPUT_ERROR: no failure_class_ids in {baseline_path}", detail
    try:
        failures = _failures_section(_read(bt_path))
    except OSError as exc:
        return None, f"INPUT_ERROR: cannot read {bt_path} ({exc})", detail
    if failures is None:
        return None, f"INPUT_ERROR: no ## FAILURES section in {bt_path}", detail
    bt_rows = _failure_rows(failures)               # list of sets, one per ### failure block

    real = _real_rows(rows)
    detail.append(f"parsed {len(rows)} finding rows; {len(real)} REAL "
                  f"(status begins with REAL)")

    # ---- (a) BREADTH: >= min_real distinct root_cause_id among REAL rows ----
    rc_list = [r.get("root_cause_id", "").strip() for r in real]
    dupes = sorted({rc for rc in rc_list if rc_list.count(rc) > 1 and rc})
    distinct = sorted({rc for rc in rc_list if rc})
    detail.append(f"(a) BREADTH: {len(distinct)} distinct REAL root_cause_id "
                  f"(need >= {min_real})")
    if dupes:
        return False, f"BREADTH -- REAL findings share root_cause_id(s): {dupes}", detail
    if "" in rc_list:
        return False, "BREADTH -- a REAL finding has an empty root_cause_id", detail
    if len(distinct) < min_real:
        return False, (f"BREADTH -- only {len(distinct)} distinct REAL root_cause_id "
                       f"(< {min_real})"), detail

    # ---- (b) BIJECTION: each REAL rc has its OWN dedicated FAILURES row (1:1) ----
    # Row-scoped (see _failure_rows): a finding must map to exactly one block, and no block
    # may be shared by two findings.
    rc_to_rows = {}
    for idx, row_rcs in enumerate(bt_rows):
        for rc in row_rcs:
            rc_to_rows.setdefault(rc, set()).add(idx)
    missing = [rc for rc in distinct if rc not in rc_to_rows]
    detail.append(f"(b) BIJECTION: {len(bt_rows)} failure rows in ## FAILURES; "
                  f"{len(missing)} REAL findings unmatched")
    if missing:
        return False, (f"BIJECTION -- REAL root_cause_id(s) with no ## FAILURES row: "
                       f"{missing}"), detail
    multi = sorted(rc for rc in distinct if len(rc_to_rows[rc]) > 1)
    if multi:
        return False, (f"BIJECTION -- root_cause_id(s) span multiple ## FAILURES rows "
                       f"(not 1:1): {multi}"), detail
    distinct_set = set(distinct)
    shared = sorted(tuple(sorted(row_rcs & distinct_set)) for row_rcs in bt_rows
                    if len(row_rcs & distinct_set) > 1)
    if shared:
        return False, (f"BIJECTION -- a single ## FAILURES row satisfies multiple REAL "
                       f"findings (not 1:1): {shared}"), detail

    # ---- (c) EVIDENCE: each REAL finding cites a resolvable on-disk artifact ----
    unresolved = []
    for r in real:
        if not _evidence_resolves(r.get("evidence", ""), root, reports_dir):
            unresolved.append(r.get("id") or r.get("root_cause_id") or "?")
    detail.append(f"(c) EVIDENCE: {len(real) - len(unresolved)}/{len(real)} REAL findings "
                  f"cite a resolvable file")
    if unresolved:
        return False, (f"EVIDENCE -- finding(s) whose evidence cites no on-disk file: "
                       f"{unresolved}"), detail

    # ---- (d) NET-NEW: >= min_netnew REAL findings are net-new vs the frozen baseline ----
    net_new = sorted({r.get("root_cause_id", "").strip() for r in real
                      if _is_net_new(r.get("fc_id", ""), baseline_ids)})
    detail.append(f"(d) NET-NEW: {len(net_new)} net-new vs baseline "
                  f"(FC1..FC{max(baseline_ids)}): {net_new} (need >= {min_netnew})")
    if len(net_new) < min_netnew:
        return False, (f"NET-NEW -- only {len(net_new)} net-new failure class(es) "
                       f"(< {min_netnew}): {net_new}"), detail

    return True, (f"{len(distinct)} distinct real root-causes, {len(net_new)} net-new "
                  f"({', '.join(net_new)})"), detail


def _render(run_id, passed, reason, detail):
    head = "PASS" if passed else "FAIL"
    lines = [f"STATUS: {head}" + ("" if passed else f" -- {reason}"), ""]
    lines.append(f"# verify-harvest gate — run {run_id}")
    lines.append("")
    lines.append("Deterministic FC-harvest gate (tools/verify_harvest.py). Checks the run's "
                 "REAL findings for breadth, bijection to BUILD_TRACKING FAILURES, resolvable "
                 "evidence, and net-new classes verified against the frozen baseline.")
    lines.append("")
    for d in detail:
        lines.append(f"- {d}")
    lines.append("")
    if passed:
        lines.append(f"VERDICT: PASS — {reason}. Genuine evidence-backed harvest, not a "
                     f"hollow green run.")
    else:
        lines.append(f"VERDICT: FAIL — {reason}. The harvest does not meet the gate; do NOT "
                     f"credit this run with a genuine pitfall harvest until fixed.")
    return "\n".join(lines) + "\n"


def main(argv=None):
    p = _Parser(description="Tool-enforce a genuine swarm pitfall harvest (FC-harvest gate).")
    p.add_argument("--reports-dir", required=True,
                   help="the run's report dir, e.g. docs/reports/<run-id>")
    p.add_argument("--root", default=".",
                   help="repo root for resolving evidence file references (default: cwd)")
    p.add_argument("--build-tracking", default=None,
                   help="path to BUILD_TRACKING.md (default <root>/BUILD_TRACKING.md)")
    p.add_argument("--baseline", default=None,
                   help="frozen FC baseline (default <reports-dir>/pitfalls-baseline.txt)")
    p.add_argument("--out", default=None,
                   help="report path (default <reports-dir>/harvest-verification.md)")
    p.add_argument("--min-real", type=int, default=5)
    p.add_argument("--min-netnew", type=int, default=2)
    args = p.parse_args(argv)

    # Thresholds MUST be positive: a zero/negative floor makes every breadth/net-new
    # comparison vacuously true, so a hollow harvest would return PASS. Fail closed at the
    # arg layer (EXIT_BAD_ARGS via _Parser.error) rather than silently accepting it.
    if args.min_real < 1:
        p.error(f"--min-real must be a positive integer, got {args.min_real}")
    if args.min_netnew < 1:
        p.error(f"--min-netnew must be a positive integer, got {args.min_netnew}")

    reports_dir = args.reports_dir
    run_id = os.path.basename(os.path.normpath(reports_dir)) or "unknown"
    bt_path = args.build_tracking or os.path.join(args.root, "BUILD_TRACKING.md")
    baseline_path = args.baseline or os.path.join(reports_dir, "pitfalls-baseline.txt")

    passed, reason, detail = _check(
        reports_dir, args.root, bt_path, baseline_path, args.min_real, args.min_netnew
    )

    # INPUT_ERROR: a required input was missing/unreadable -> fail-closed, distinct code.
    if passed is None:
        sys.stderr.write(f"STATUS: FAIL -- {reason}\n")
        # still leave a report so the orchestrator sees why
        report = _render(run_id, False, reason, detail)
    else:
        report = _render(run_id, passed, reason, detail)

    out = args.out or os.path.join(reports_dir, "harvest-verification.md")
    try:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(report)
    except OSError as exc:
        sys.stderr.write(f"WARN: could not write {out}: {exc}\n")

    if passed is None:
        return EXIT_INPUT_ERROR
    print(report.splitlines()[0])          # STATUS line
    for d in detail:
        print(f"  {d}")
    return EXIT_PASS if passed else EXIT_FAIL


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # fail-closed: an unexpected crash must never read as PASS
        sys.stderr.write(f"STATUS: FAIL -- unexpected error: {exc}\n")
        sys.exit(EXIT_INPUT_ERROR)
