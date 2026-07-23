#!/usr/bin/env python3
"""
P1/P2 multi-wave barrier loop -- authoritative wave verifier (plan §4 / §7).

Three pinned modes. In EVERY mode the truth is DERIVED from `--plan` (the
swarm-planner `### Agent:` sections) + `--spec-path` (the shared-interface spec's
Cross-Boundary Wiring Table) + LIVE git + RE-READ evidence files -- NEVER from a
caller-supplied roster. A forged artifact (a recorded PASS whose evidence file's
real STATUS is not PASS) FAILs.

  --validate-schema  (pre-spawn, §4): parse the wave schema, normalize
      Export-Names -> file -> agent, and reject duplicate / missing / unresolved /
      ambiguous / aggregate-without-members / out-of-roster / forward-reference /
      runtime-dependent-or-module-mode-gate. Exit 0 = CLEARED.

  --wave K           (immediate, §7): verify the wave-K artifact against the
      derived roster, re-read every evidence file, check run identity, the blocking
      gate verdicts, the firebreak (independently), the ancestry/fork-point proof,
      the commit-count == Sigma(delta)+1 accounting, the terminal_head_sha
      post-terminal-commit containment, and (mode-sensitive) assembled_output_sha
      == live HEAD.

  --reconcile        (tail, §7): re-run every --wave check across waves 1..N except
      the HEAD check -- waves 1..N-1 outputs must be ANCESTORS of HEAD and only wave
      N's output EQUALS HEAD; plus the SHA chain must be unbroken end to end.

TRUSTED-only pinned in the firebreak (TRUSTED_PIPELINE_SCRIPT_PATHS).

Exit 0 with `STATUS: CLEARED|PASS`; non-zero with `STATUS: FAIL -- <reason>`.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_BAD_ARGS = 5

HERE = os.path.dirname(os.path.abspath(__file__))
FIREBREAK = os.path.join(os.path.dirname(HERE), ".claude", "hooks",
                         "firebreak-activate.py")

# module-mode / package-wide gate directives that §4 rejects pre-spawn (literal
# tokens -- Design X defers ALL cross-module execution to the swarm-runner import
# smoke; a plan may not prescribe an orchestrator/worker module-mode gate).
MODULE_MODE_TOKENS = [
    "python -m compileall", "python3 -m compileall",
    ".venv/bin/python -m compileall",
]
MODULE_SMOKE_RE = re.compile(r"python3?\s+-m\s+[\w.]+\.smoke")
TYPECHECK_GATE_RE = re.compile(r"package-wide\s+typecheck", re.I)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write(f"FAIL[BAD_ARGS]: {message}\n")
        raise SystemExit(EXIT_BAD_ARGS)


def _ok(status):
    print(f"STATUS: {status}")
    return EXIT_OK


def _fail(reason):
    print(f"STATUS: FAIL -- {reason}")
    return EXIT_FAIL


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------------------------------- #
# git helpers
# --------------------------------------------------------------------------- #

def git(root, *args):
    p = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)
    return p.returncode, p.stdout.strip()


def rev_parse(root, ref):
    rc, out = git(root, "rev-parse", ref)
    return out if rc == 0 else None


def is_ancestor(root, a, b):
    rc, _ = git(root, "merge-base", "--is-ancestor", a, b)
    return rc == 0


# --------------------------------------------------------------------------- #
# plan / spec parsing (§4)
# --------------------------------------------------------------------------- #

def parse_waves_frontmatter(text):
    """`waves: N` from the plan frontmatter. None if absent."""
    m = re.search(r"(?m)^waves:\s*([^\s#]+)", text)
    if not m:
        return None
    return m.group(1)


AGENT_HEADER_RE = re.compile(r"(?m)^###\s+Agent:\s*(.+?)\s*$")


def parse_agents(text):
    """Return (agents, error). agents = list of dicts {role, wave, required, files,
    has_command_field, raw}. Parses the swarm-planner `### Agent:` sections."""
    heads = list(AGENT_HEADER_RE.finditer(text))
    agents = []
    for i, h in enumerate(heads):
        start = h.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        block = text[start:end]
        role = h.group(1).strip()
        wave = _field(block, "Wave")
        required = _field(block, "Required")
        files = _files(block)
        has_cmd = bool(re.search(r"(?m)^\*\*(Commands|Run):\*\*", block))
        agents.append({"role": role, "wave": wave, "required": required,
                       "files": files, "has_command_field": has_cmd})
    return agents


def _field(block, name):
    m = re.search(rf"(?m)^\*\*{name}:\*\*\s*(.+?)\s*$", block)
    return m.group(1).strip() if m else None


def _files(block):
    m = re.search(r"(?m)^\*\*Files:\*\*\s*$", block)
    if not m:
        return []
    rest = block[m.end():]
    files = []
    for line in rest.splitlines():
        s = line.strip()
        if s.startswith("**") or s.startswith("###"):
            break
        fm = re.match(r"^[-*]\s+`?([^`]+?)`?\s*$", s)
        if fm:
            files.append(fm.group(1).strip())
        elif s == "":
            continue
    return files


def _find_table(text, *required_header_substrings):
    """Return (header_cells_lower, rows) for the first markdown table whose header
    row contains ALL the given substrings (case-insensitive), else (None, [])."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        low = [c.lower() for c in cells]
        if all(any(sub in c for c in low) for sub in required_header_substrings):
            # the next line should be the |---|---| separator
            rows = []
            for r in lines[i + 2:]:
                if not r.strip().startswith("|"):
                    break
                rc = [c.strip() for c in r.strip().strip("|").split("|")]
                if set("".join(rc)) <= set("-: "):
                    continue
                rows.append(rc)
            return low, rows
    return None, []


def _col(header, *subs):
    for idx, c in enumerate(header):
        if any(s in c for s in subs):
            return idx
    return None


def _clean_cell(v):
    return v.strip().strip("`").strip()


def parse_wiring(text):
    """Parse the Cross-Boundary Wiring Table -> list of {symbol, producer_file,
    consumer_file, build_order_sensitive}."""
    header, rows = _find_table(text, "producer", "consumer")
    if header is None:
        return None
    p_idx = _col(header, "producer")
    c_idx = _col(header, "consumer")
    s_idx = _col(header, "symbol", "name", "export")
    b_idx = _col(header, "build-order", "build order")
    out = []
    for r in rows:
        if max(filter(None, [p_idx, c_idx, s_idx, b_idx] + [0])) >= len(r):
            continue
        out.append({
            "symbol": _clean_cell(r[s_idx]) if s_idx is not None else "",
            "producer_file": _clean_cell(r[p_idx]),
            "consumer_file": _clean_cell(r[c_idx]),
            "build_order_sensitive": (
                _clean_cell(r[b_idx]).lower() == "yes"
                if b_idx is not None and b_idx < len(r) else False),
        })
    return out


def parse_coordinated_members(text):
    """`**Members of <token>:** fileA, fileB` under Coordinated Behaviors -> map
    token(lower) -> [files]."""
    out = {}
    for m in re.finditer(r"(?m)^\*\*Members of (.+?):\*\*\s*(.+?)\s*$", text):
        token = m.group(1).strip().lower()
        members = [_clean_cell(x) for x in re.split(r"[,;]", m.group(2)) if x.strip()]
        out[token] = members
    return out


AGGREGATE_RE = re.compile(r"^\*$|(^|\W)all(\W|$)", re.I)


def _is_aggregate(cell):
    c = cell.strip()
    if c == "*":
        return True
    if "/" in c or c.endswith(".py"):
        return False
    return bool(AGGREGATE_RE.search(c))


def scan_module_mode_gate(text):
    if any(tok in text for tok in MODULE_MODE_TOKENS):
        return "python -m compileall directive present"
    if MODULE_SMOKE_RE.search(text):
        return "python -m <pkg>.smoke directive present"
    if TYPECHECK_GATE_RE.search(text):
        return "package-wide typecheck gate directive present"
    return None


def validate_schema(plan_text, spec_text):
    """§4 total, deterministic schema validation. Returns (status, reason)."""
    waves_raw = parse_waves_frontmatter(plan_text)
    if waves_raw is None or waves_raw == "1":
        return "CLEARED", "single-wave (waves absent or 1) -- validator is a no-op"
    if not re.fullmatch(r"\d+", waves_raw) or int(waves_raw) < 1:
        return "FAIL", f"waves must be a positive integer, got {waves_raw!r}"
    N = int(waves_raw)

    agents = parse_agents(plan_text)
    if not agents:
        return "FAIL", "no `### Agent:` sections found in --plan"

    # per-agent field totality
    owner = {}
    agent_wave = {}
    for a in agents:
        role = a["role"]
        if a["has_command_field"]:
            return "FAIL", (f"agent {role!r} has a **Commands:**/**Run:** field -- "
                            "runtime-dependent edge rejected (workers are write+commit-only)")
        if a["wave"] is None or not re.fullmatch(r"\d+", a["wave"]):
            return "FAIL", f"agent {role!r} has missing/non-integer **Wave:** ({a['wave']!r})"
        w = int(a["wave"])
        if w < 1 or w > N:
            return "FAIL", f"agent {role!r} **Wave:** {w} out of range 1..{N}"
        if a["required"] not in ("yes", "no"):
            return "FAIL", f"agent {role!r} **Required:** must be yes|no, got {a['required']!r}"
        if not a["files"]:
            return "FAIL", f"agent {role!r} has no **Files:**"
        agent_wave[role] = w
        for f in a["files"]:
            if f in owner:
                return "FAIL", f"duplicate: file {f!r} owned by {owner[f]!r} and {role!r}"
            owner[f] = role

    # wave contiguity + no empty wave
    present = sorted(set(agent_wave.values()))
    if present != list(range(1, N + 1)):
        return "FAIL", f"waves not contiguous 1..{N}: present waves {present}"

    # module-mode / package-wide gate rejection (plan-wide)
    mm = scan_module_mode_gate(plan_text)
    if mm:
        return "FAIL", f"module-mode-gate rejected: {mm}"

    # out-of-roster: an Export Names "Defined By" role not in the assignment roster.
    roles = set(agent_wave)
    exp_header, exp_rows = _find_table(spec_text, "defined by", "used by")
    if exp_header is not None:
        db_idx = _col(exp_header, "defined by")
        for r in exp_rows:
            if db_idx is None or db_idx >= len(r):
                continue
            m = re.match(r"([A-Za-z][\w-]*)", _clean_cell(r[db_idx]))
            role_tok = m.group(1) if m else None
            if role_tok and role_tok.lower() not in ("all", "framework", "none") \
                    and role_tok not in roles:
                return "FAIL", (f"out-of-roster: Export Names 'Defined By' names {role_tok!r} "
                                "which is not in the assignment roster")

    # Export-Names -> file -> agent normalization via the wiring table
    wiring = parse_wiring(spec_text)
    if wiring is None:
        return "FAIL", "spec has no Cross-Boundary Wiring Table (producer/consumer columns)"
    members = parse_coordinated_members(spec_text)

    sym_producer = {}
    for row in wiring:
        sym = row["symbol"] or f"{row['producer_file']}->{row['consumer_file']}"
        pf, cf = row["producer_file"], row["consumer_file"]
        if pf not in owner:
            return "FAIL", f"missing: producer file {pf!r} (symbol {sym!r}) owned by no agent"
        prod_agent = owner[pf]
        prod_wave = agent_wave[prod_agent]
        # ambiguous: the same symbol produced by two different agents.
        if sym in sym_producer and sym_producer[sym] != prod_agent:
            return "FAIL", (f"ambiguous: symbol {sym!r} produced by both "
                            f"{sym_producer[sym]!r} and {prod_agent!r}")
        sym_producer[sym] = prod_agent

        # consumer resolution: real file, aggregate token, or unresolved
        consumers = []
        if _is_aggregate(cf):
            key = cf.strip().lower()
            if key not in members:
                return "FAIL", (f"aggregate: consumer {cf!r} (symbol {sym!r}) names a class "
                                "with no explicit member list in Coordinated Behaviors")
            for mfile in members[key]:
                if mfile not in owner:
                    return "FAIL", f"aggregate member {mfile!r} owned by no agent"
                consumers.append(mfile)
        elif cf in owner:
            consumers.append(cf)
        else:
            return "FAIL", (f"unresolved: consumer {cf!r} (symbol {sym!r}) maps to no "
                            "owned file")

        for cfile in consumers:
            cons_agent = owner[cfile]
            cons_wave = agent_wave[cons_agent]
            if cons_wave < prod_wave:
                return "FAIL", (f"forward-reference: symbol {sym!r} consumed in wave "
                                f"{cons_wave} ({cons_agent}) before produced in wave "
                                f"{prod_wave} ({prod_agent})")
            if cons_wave == prod_wave and cons_agent != prod_agent \
                    and row["build_order_sensitive"]:
                return "FAIL", (f"forward-reference: build-order-sensitive symbol {sym!r} "
                                f"crosses agents {prod_agent}->{cons_agent} within wave "
                                f"{prod_wave}")
    return "CLEARED", f"{N}-wave schema valid; {len(owner)} files, {len(wiring)} wiring edges"


# --------------------------------------------------------------------------- #
# artifact / evidence parsing (§7)
# --------------------------------------------------------------------------- #

def load_artifact(reports_dir, wave_index):
    path = os.path.join(reports_dir, "wave.md")
    if not os.path.exists(path):
        return None, f"artifact missing: {path}"
    text = _read(path)
    m = re.search(r"```json\s*(.*?)```", text, re.S)
    if not m:
        return None, f"artifact {path} has no json block"
    try:
        return json.loads(m.group(1)), None
    except json.JSONDecodeError as e:
        return None, f"artifact {path} json parse error: {e}"


def status_line(path):
    if not os.path.exists(path):
        return None
    first = _read(path).splitlines()
    if not first:
        return None
    m = re.match(r"\s*STATUS:\s*(.+?)\s*$", first[0])
    return m.group(1).strip() if m else None


def firebreak_active(root):
    if not os.path.exists(FIREBREAK):
        return False, "firebreak-activate.py not found"
    p = subprocess.run([sys.executable, FIREBREAK, "status", "--root",
                        os.path.abspath(root)], capture_output=True, text=True)
    out = (p.stdout or "").strip()
    tok = out.split()[0] if out else ""
    return tok == "ACTIVE", out


def derive_roster_roles(plan_text, wave_index):
    """Roles the plan assigns to wave K, with their Required flag."""
    agents = parse_agents(plan_text)
    out = {}
    for a in agents:
        if a["wave"] and re.fullmatch(r"\d+", a["wave"]) and int(a["wave"]) == wave_index:
            out[a["role"]] = (a["required"] == "yes")
    return out


TERMINAL_OK = {"COMPLETED"}
TERMINAL_ALL = {"COMPLETED", "FAILED", "TIMED_OUT", "TIMED_OUT_STOPPED"}


def verify_wave(art, plan_text, spec_text, root, reports_dir, run_id, run_start_ts,
                original_branch, default_branch, wave_index, head_mode):
    """Shared §7 reject-set for one wave artifact. head_mode in {'equal','ancestor'}.
    Returns (ok, reason)."""
    # run identity (exact equality)
    if str(art.get("run_id")) != str(run_id):
        return False, f"run_id mismatch: artifact {art.get('run_id')!r} != {run_id!r}"
    if str(art.get("run_start_ts")) != str(run_start_ts):
        return False, f"run_start_ts mismatch: {art.get('run_start_ts')!r} != {run_start_ts!r}"
    if int(art.get("wave_index", -1)) != wave_index:
        return False, f"wave_index mismatch: {art.get('wave_index')!r} != {wave_index}"

    # roster derived from --plan == artifact roster
    derived = derive_roster_roles(plan_text, wave_index)
    art_roster = {r["role"]: r for r in art.get("roster", [])}
    if set(derived) != set(art_roster):
        return False, (f"roster mismatch vs --plan wave {wave_index}: "
                       f"plan={sorted(derived)} artifact={sorted(art_roster)}")

    # terminal states + required-worker health
    for role, req in derived.items():
        r = art_roster[role]
        st = r.get("status")
        if st not in TERMINAL_ALL:
            return False, f"worker {role!r} non-terminal status {st!r}"
        if req and st not in TERMINAL_OK:
            return False, f"REQUIRED worker {role!r} is {st!r}"

    # blocking gate verdicts + evidence re-read (forged-verdict guard)
    if (art.get("ownership_gate") or {}).get("verdict") != "PASS":
        return False, "ownership_gate verdict != PASS"
    gr = art.get("gate_results", {})
    if gr.get("contract", {}).get("verdict") != "PASS":
        return False, "contract verdict != PASS (blocking)"
    if gr.get("integrated_import", {}).get("verdict") != "PASS":
        return False, "integrated_import verdict != PASS (blocking)"
    for nb in ("smoke", "test"):
        if "verdict" not in gr.get(nb, {}):
            return False, f"{nb} verdict absent (must be present though non-blocking)"

    # re-read each referenced evidence file and cross-check its line-1 STATUS
    evidence = [
        (art.get("ownership_gate", {}).get("path"), ("PASS",)),
        (gr.get("contract", {}).get("path"), ("PASS",)),
        (gr.get("integrated_import", {}).get("path"), ("PASS",)),
        (art.get("provenance", {}).get("path"), ("PROVENANCE_OK",)),
    ]
    for rel, want in evidence:
        if not rel:
            return False, "evidence path missing in artifact"
        p = rel if os.path.isabs(rel) else os.path.join(root, rel)
        st = status_line(p)
        if st is None:
            return False, f"evidence file unreadable / no STATUS: {rel}"
        if not any(st.startswith(w) for w in want):
            return False, f"forged verdict: {rel} STATUS {st!r} not in {want}"
    # smoke/test evidence must merely be PRESENT with a STATUS line
    for nb in ("smoke", "test"):
        rel = gr.get(nb, {}).get("path")
        p = rel if os.path.isabs(rel) else os.path.join(root, rel) if rel else None
        if not rel or status_line(p) is None:
            return False, f"{nb} evidence file missing/no STATUS: {rel}"

    if (art.get("provenance") or {}).get("status") != "PROVENANCE_OK":
        return False, "provenance status != PROVENANCE_OK"

    # firebreak ACTIVE at verify time (independent read)
    active, out = firebreak_active(root)
    if not active:
        return False, f"firebreak not ACTIVE at verify time ({out!r})"

    # ancestry / fork-point / accounting proofs (live git)
    expected_base = art.get("expected_base_sha")
    worker_base = art.get("worker_base_sha")
    assembled = art.get("assembled_output_sha")
    default_tip = rev_parse(root, f"origin/{default_branch}") or \
        rev_parse(root, default_branch)
    if default_tip and not is_ancestor(root, default_tip, expected_base):
        return False, "origin/<default> tip is not an ancestor of expected_base_sha"

    completed = [r for r in art.get("roster", []) if r.get("status") == "COMPLETED"]
    deltas = {d["role"]: d for d in art.get("worker_deltas", [])}
    total_delta = 0
    for r in completed:
        role = r["role"]
        d = deltas.get(role)
        if d is None:
            return False, f"no worker_deltas entry for COMPLETED worker {role!r}"
        whead = d.get("worker_head_sha")
        dc = int(d.get("delta_count", 0))
        total_delta += dc
        # terminal_head_sha post-terminal-commit containment (§3.1)
        thead = r.get("terminal_head_sha")
        live = rev_parse(root, r.get("branch")) if r.get("branch") else None
        for label, val in (("terminal_head_sha", thead), ("worker_deltas.worker_head_sha", whead)):
            if live is not None and val is not None and val != live:
                return False, (f"post-terminal-commit containment: worker {role!r} "
                               f"{label} {val[:12]} != live branch head {live[:12]}")
        # fork-point == pinned worker_base_sha
        if whead and dc > 0:
            rc, mb = git(root, "merge-base", whead, expected_base)
            if rc == 0 and worker_base and mb != worker_base:
                return False, (f"worker {role!r} forked from a stale base: merge-base "
                               f"{mb[:12]} != worker_base_sha {worker_base[:12]}")

    # commit count == Sigma(delta over COMPLETED non-empty) + 1 (the --no-ff merge)
    if expected_base and assembled:
        rc, cnt = git(root, "rev-list", "--count", f"{expected_base}..{assembled}")
        if rc == 0:
            want = total_delta + 1
            if int(cnt) != want:
                return False, (f"commit-count {cnt} != Sigma(delta)+1 = {want} "
                               "(the single --no-ff merge)")

    # HEAD check (mode-sensitive)
    head = rev_parse(root, original_branch)
    if head_mode == "equal":
        if assembled != head:
            return False, f"assembled_output_sha {assembled} != live HEAD {head}"
    elif head_mode == "ancestor":
        if not (assembled and head and is_ancestor(root, assembled, head)):
            return False, "assembled_output_sha is not an ancestor of HEAD (reconcile)"
    return True, "ok"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def cmd_validate_schema(args):
    try:
        plan_text = _read(args.plan)
        spec_text = _read(args.spec_path)
    except OSError as e:
        return _fail(f"cannot read plan/spec: {e}")
    status, reason = validate_schema(plan_text, spec_text)
    if status == "CLEARED":
        return _ok(f"CLEARED -- {reason}")
    return _fail(reason)


def cmd_wave(args):
    try:
        plan_text = _read(args.plan)
        spec_text = _read(args.spec_path)
    except OSError as e:
        return _fail(f"cannot read plan/spec: {e}")
    art, err = load_artifact(args.reports_dir, args.wave)
    if err:
        return _fail(err)
    # continuity vs prior wave (prev_wave_output_sha == expected_base_sha)
    if args.wave > 1:
        if art.get("prev_wave_output_sha") != art.get("expected_base_sha"):
            return _fail("continuity break: expected_base_sha != prev_wave_output_sha")
    ok, reason = verify_wave(art, plan_text, spec_text, args.root, args.reports_dir,
                             args.run_id, args.run_start_ts, args.original_branch,
                             args.default_branch, args.wave, head_mode="equal")
    return _ok(f"PASS -- wave {args.wave} verified") if ok else _fail(reason)


def cmd_reconcile(args):
    try:
        plan_text = _read(args.plan)
        spec_text = _read(args.spec_path)
    except OSError as e:
        return _fail(f"cannot read plan/spec: {e}")
    waves_raw = parse_waves_frontmatter(plan_text)
    if not waves_raw or not re.fullmatch(r"\d+", waves_raw):
        return _fail("reconcile requires an integer `waves:` in --plan")
    N = int(waves_raw)
    prev_assembled = None
    prev_artifact_path = None
    verified = 0
    for k in range(1, N + 1):
        wdir = os.path.join(args.reports_dir, f"w{k}")
        art, err = load_artifact(wdir, k)
        if err:
            return _fail(f"reconcile: {err}")
        # SHA chain: wave k expected_base == wave k-1 assembled; prev artifact sha
        if k > 1:
            if art.get("prev_wave_output_sha") != prev_assembled:
                return _fail(f"reconcile: chain break at wave {k} "
                             "(prev_wave_output_sha != wave k-1 assembled_output_sha)")
            if art.get("expected_base_sha") != prev_assembled:
                return _fail(f"reconcile: chain break at wave {k} "
                             "(expected_base_sha != wave k-1 assembled_output_sha)")
        head_mode = "equal" if k == N else "ancestor"
        ok, reason = verify_wave(art, plan_text, spec_text, args.root, wdir,
                                 args.run_id, args.run_start_ts, args.original_branch,
                                 args.default_branch, k, head_mode=head_mode)
        if not ok:
            return _fail(f"reconcile wave {k}: {reason}")
        prev_assembled = art.get("assembled_output_sha")
        prev_artifact_path = os.path.join(wdir, "wave.md")
        verified += 1
    if verified != N:
        return _fail(f"reconcile: verified {verified} artifacts != declared waves {N}")
    return _ok(f"PASS -- reconciled {N} waves")


def main(argv=None):
    parser = _Parser(description="P1/P2 authoritative wave verifier")
    parser.add_argument("--validate-schema", action="store_true")
    parser.add_argument("--wave", type=int, default=None)
    parser.add_argument("--reconcile", action="store_true")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--spec-path", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--reports-dir", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--run-start-ts", default=None)
    parser.add_argument("--original-branch", default=None)
    parser.add_argument("--default-branch", default=None)
    args = parser.parse_args(argv)

    modes = sum([bool(args.validate_schema), args.wave is not None, bool(args.reconcile)])
    if modes != 1:
        return _fail("exactly one of --validate-schema | --wave K | --reconcile required")

    if args.validate_schema:
        return cmd_validate_schema(args)

    need = ["reports_dir", "run_id", "run_start_ts", "original_branch", "default_branch"]
    missing = [f"--{n.replace('_', '-')}" for n in need if getattr(args, n) is None]
    if missing:
        return _fail(f"missing required args for this mode: {missing}")
    if args.wave is not None:
        return cmd_wave(args)
    return cmd_reconcile(args)


if __name__ == "__main__":
    raise SystemExit(main())
