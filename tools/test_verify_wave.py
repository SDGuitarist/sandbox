#!/usr/bin/env python3
"""
Unit tests for tools/verify_wave.py (plan §4 / §7 / §8).

Plain stdlib; runs the verifier as a real subprocess. `--case <name>` selector
(per plan §8) plus a no-arg full-suite run. Schema cases are pure text fixtures;
--wave / --reconcile cases build a throwaway git repo + evidence files + an
activated firebreak sentinel, and emit the wave.md via tools/wave_artifact.py.

Run:  python3 tools/test_verify_wave.py
      python3 tools/test_verify_wave.py --case test_schema_forward_ref
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VERIFY = os.path.join(HERE, "verify_wave.py")
ARTIFACT = os.path.join(HERE, "wave_artifact.py")
FIREBREAK = os.path.join(os.path.dirname(HERE), ".claude", "hooks",
                         "firebreak-activate.py")

ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@local",
           GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@local")

CASES = {}


def case(fn):
    CASES[fn.__name__] = fn
    return fn


def _mkdir(pfx="vw-"):
    return tempfile.mkdtemp(prefix=pfx)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# --------------------------------------------------------------------------- #
# text fixtures (schema)
# --------------------------------------------------------------------------- #

def build_plan(waves, agents, extra=""):
    """agents = list of (role, wave, required, [files], command_field?)."""
    out = [f"---\ntitle: t\nswarm: true\nwaves: {waves}\n---\n\n# Plan\n{extra}\n"]
    for a in agents:
        role, wave, required, files = a[0], a[1], a[2], a[3]
        cmd = a[4] if len(a) > 4 else False
        out.append(f"### Agent: {role}\n**Wave:** {wave}\n**Required:** {required}\n"
                   "**Files:**\n" + "".join(f"- `{f}`\n" for f in files))
        if cmd:
            out.append("**Commands:**\n- `pytest`\n")
        out.append("**Responsibility:** does things.\n\n")
    return "".join(out)


def build_spec(wiring, members=None, export_rows=None):
    """wiring = list of (symbol, producer_file, consumer_file, build_order_sensitive)."""
    s = ["# Shared Interface Spec\n\n## Cross-Boundary Wiring Table\n\n",
         "| Symbol | Producer File | Consumer File | Build-Order-Sensitive | Import Path |\n",
         "|--------|---------------|---------------|-----------------------|-------------|\n"]
    for sym, pf, cf, bos in wiring:
        s.append(f"| {sym} | {pf} | {cf} | {'yes' if bos else 'no'} | from x import y |\n")
    if export_rows:
        s.append("\n## Export Names Table\n\n| Name | Type | Defined By | Used By | Full Signature |\n")
        s.append("|------|------|-----------|---------|----------------|\n")
        for name, defined_by, used_by in export_rows:
            s.append(f"| {name} | function | {defined_by} | {used_by} | f() -> None |\n")
    if members:
        s.append("\n## Coordinated Behaviors\n\n")
        for token, files in members.items():
            s.append(f"**Members of {token}:** {', '.join(files)}\n")
    return "".join(s)


def _run_schema(plan_text, spec_text):
    d = _mkdir("vw-schema-")
    plan = _write(os.path.join(d, "plan.md"), plan_text)
    spec = _write(os.path.join(d, "spec.md"), spec_text)
    cmd = [sys.executable, VERIFY, "--validate-schema", "--plan", plan,
           "--spec-path", spec, "--root", d]
    p = subprocess.run(cmd, capture_output=True, text=True)
    first = (p.stdout.splitlines() or [""])[0]
    return first, p.returncode, p.stdout


def _assert_cleared(first, rc):
    assert rc == 0 and first.startswith("STATUS: CLEARED"), first


def _assert_fail(first, rc, needle):
    assert rc != 0 and first.startswith("STATUS: FAIL") and needle in first, \
        f"want FAIL containing {needle!r}, got: {first!r}"


# ---- schema happy / parse ----

@case
def test_single_wave_noop():
    first, rc, _ = _run_schema(build_plan.__doc__ and
                               "---\ntitle: t\n---\n# no waves key\n",
                               build_spec([("q", "a.py", "b.py", False)]))
    _assert_cleared(first, rc)


@case
def test_planner_wave_required_parse():
    plan = build_plan(2, [("models", 1, "yes", ["pkg/models.py"]),
                          ("routes", 2, "no", ["pkg/routes.py"])])
    spec = build_spec([("query", "pkg/models.py", "pkg/routes.py", False)])
    _assert_cleared(*_run_schema(plan, spec)[:2])


@case
def test_three_wave_continuity():
    plan = build_plan(3, [("models", 1, "yes", ["pkg/models.py"]),
                          ("routes", 2, "yes", ["pkg/routes.py"]),
                          ("templates", 3, "no", ["pkg/templates.py"])])
    spec = build_spec([("query", "pkg/models.py", "pkg/routes.py", False),
                       ("render", "pkg/routes.py", "pkg/templates.py", False)])
    _assert_cleared(*_run_schema(plan, spec)[:2])


# ---- schema rejects ----

@case
def test_schema_invalid_count():
    plan = build_plan(0, [("models", 1, "yes", ["pkg/models.py"])])
    _assert_fail(*_run_schema(plan, build_spec([]))[:2], "positive integer")


@case
def test_schema_empty_wave():
    plan = build_plan(3, [("models", 1, "yes", ["pkg/models.py"]),
                          ("routes", 2, "yes", ["pkg/routes.py"])])  # no wave 3
    _assert_fail(*_run_schema(plan, build_spec([]))[:2], "not contiguous")


@case
def test_schema_bad_required():
    plan = build_plan(2, [("models", 1, "maybe", ["pkg/models.py"]),
                          ("routes", 2, "yes", ["pkg/routes.py"])])
    _assert_fail(*_run_schema(plan, build_spec([]))[:2], "Required")


@case
def test_schema_forward_ref():
    # consumer in wave 1 uses a producer defined in wave 2 -> forward-reference.
    plan = build_plan(2, [("routes", 1, "yes", ["pkg/routes.py"]),
                          ("models", 2, "yes", ["pkg/models.py"])])
    spec = build_spec([("query", "pkg/models.py", "pkg/routes.py", False)])
    _assert_fail(*_run_schema(plan, spec)[:2], "forward-reference")


@case
def test_schema_same_wave_build_order_sensitive_rejected():
    plan = build_plan(2, [("a", 1, "yes", ["pkg/a.py"]),
                          ("b", 1, "yes", ["pkg/b.py"]),
                          ("c", 2, "yes", ["pkg/c.py"])])
    spec = build_spec([("sym", "pkg/a.py", "pkg/b.py", True)])  # BOS within wave 1
    _assert_fail(*_run_schema(plan, spec)[:2], "forward-reference")


@case
def test_schema_runtime_dependent_edge_rejected():
    plan = build_plan(2, [("models", 1, "yes", ["pkg/models.py"], True),  # has Commands
                          ("routes", 2, "yes", ["pkg/routes.py"])])
    _assert_fail(*_run_schema(plan, build_spec([]))[:2], "runtime-dependent")


@case
def test_schema_module_mode_gate_rejected():
    plan = build_plan(2, [("models", 1, "yes", ["pkg/models.py"]),
                          ("routes", 2, "yes", ["pkg/routes.py"])],
                      extra="Gate: run `python -m compileall pkg` before merge.\n")
    spec = build_spec([("query", "pkg/models.py", "pkg/routes.py", False)])
    _assert_fail(*_run_schema(plan, spec)[:2], "module-mode-gate")


@case
def test_schema_unresolved_mapping():
    plan = build_plan(2, [("models", 1, "yes", ["pkg/models.py"]),
                          ("routes", 2, "yes", ["pkg/routes.py"])])
    spec = build_spec([("query", "pkg/models.py", "pkg/NOPE.py", False)])
    _assert_fail(*_run_schema(plan, spec)[:2], "unresolved")


@case
def test_schema_missing_producer():
    plan = build_plan(2, [("models", 1, "yes", ["pkg/models.py"]),
                          ("routes", 2, "yes", ["pkg/routes.py"])])
    spec = build_spec([("query", "pkg/NOPE.py", "pkg/routes.py", False)])
    _assert_fail(*_run_schema(plan, spec)[:2], "missing")


@case
def test_schema_ambiguous_mapping():
    plan = build_plan(2, [("a", 1, "yes", ["pkg/a.py"]),
                          ("b", 1, "yes", ["pkg/b.py"]),
                          ("c", 2, "yes", ["pkg/c.py"])])
    # same symbol produced by two different agents' files -> ambiguous
    spec = build_spec([("dup", "pkg/a.py", "pkg/c.py", False),
                       ("dup", "pkg/b.py", "pkg/c.py", False)])
    _assert_fail(*_run_schema(plan, spec)[:2], "ambiguous")


@case
def test_schema_aggregate_no_members():
    plan = build_plan(2, [("models", 1, "yes", ["pkg/models.py"]),
                          ("routes", 2, "yes", ["pkg/routes.py"])])
    spec = build_spec([("query", "pkg/models.py", "all routes", False)])
    _assert_fail(*_run_schema(plan, spec)[:2], "aggregate")


@case
def test_schema_aggregate_with_members_ok():
    plan = build_plan(2, [("models", 1, "yes", ["pkg/models.py"]),
                          ("routes", 2, "yes", ["pkg/routes.py"])])
    spec = build_spec([("query", "pkg/models.py", "all routes", False)],
                      members={"all routes": ["pkg/routes.py"]})
    _assert_cleared(*_run_schema(plan, spec)[:2])


@case
def test_schema_duplicate_file():
    plan = build_plan(2, [("models", 1, "yes", ["pkg/shared.py"]),
                          ("routes", 2, "yes", ["pkg/shared.py"])])
    _assert_fail(*_run_schema(plan, build_spec([]))[:2], "duplicate")


@case
def test_schema_out_of_roster():
    plan = build_plan(2, [("models", 1, "yes", ["pkg/models.py"]),
                          ("routes", 2, "yes", ["pkg/routes.py"])])
    spec = build_spec([("query", "pkg/models.py", "pkg/routes.py", False)],
                      export_rows=[("query", "GHOST (Wave 1)", "routes (Wave 2)")])
    _assert_fail(*_run_schema(plan, spec)[:2], "out-of-roster")


# --------------------------------------------------------------------------- #
# git-fixture (--wave / --reconcile)
# --------------------------------------------------------------------------- #

def _git(root, *a):
    return subprocess.run(["git", "-C", root, *a], env=ENV, capture_output=True, text=True)


def _rev(root, ref):
    return _git(root, "rev-parse", ref).stdout.strip()


def _activate_firebreak(root):
    subprocess.run([sys.executable, FIREBREAK, "activate", "085", "--root",
                    os.path.abspath(root)], capture_output=True, text=True)
    p = subprocess.run([sys.executable, FIREBREAK, "status", "--root",
                        os.path.abspath(root)], capture_output=True, text=True)
    return (p.stdout or "").strip().startswith("ACTIVE")


def _evidence(reports_dir, **status_over):
    files = {"ownership-gate.md": "PASS", "contract-check.md": "PASS",
             "integrated-import.md": "PASS", "smoke-test.md": "PASS",
             "test-results.md": "PASS", "spec-provenance.md": "PROVENANCE_OK"}
    files.update(status_over)
    for name, st in files.items():
        _write(os.path.join(reports_dir, name), f"STATUS: {st}\n\n# {name}\n")


def build_wave_repo():
    """A one-wave (wave 1) fixture: master(default)=base, feat(original)=base,
    one worker branch (1 commit) off master, assembled via cherry-pick + --no-ff
    merge into feat. Returns a dict of paths/shas + a helper to emit wave.md."""
    root = _mkdir("vw-repo-")
    _git(root, "init", "-b", "master")
    # FC68: firebreak activate/status refuse a root lacking this file (repo detection).
    _write(os.path.join(root, ".claude/hooks/firebreak-classify.py"),
           "# placeholder so firebreak-activate recognizes this as a firebreak repo\n")
    _write(os.path.join(root, "pkg/__init__.py"), "")
    plan = build_plan(1, [("models", 1, "yes", ["pkg/models.py"])])
    spec = build_spec([("query", "pkg/models.py", "pkg/__init__.py", False)])
    _write(os.path.join(root, "plan.md"), plan)
    _write(os.path.join(root, "spec.md"), spec)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "base")
    base = _rev(root, "HEAD")
    _git(root, "branch", "feat", "master")
    # worker off master
    wt = os.path.join(root, ".wt-models")
    _git(root, "worktree", "add", "-b", "swarm-085-w1-models", wt, "master")
    _write(os.path.join(wt, "pkg/models.py"), "def query():\n    return []\n")
    _git(root, "add", "-A") if False else _git(wt, "add", "-A")
    _git(wt, "commit", "-m", "models")
    worker_head = _rev(root, "swarm-085-w1-models")
    # assemble: feat + cherry-pick worker + --no-ff self-merge
    _git(root, "checkout", "feat")
    _git(root, "checkout", "-b", "swarm-085-w1-assembly")
    mb = _git(root, "merge-base", "feat", "swarm-085-w1-models").stdout.strip()
    _git(root, "cherry-pick", f"{mb}..swarm-085-w1-models")
    _git(root, "checkout", "feat")
    _git(root, "merge", "--no-ff", "-m", "assemble w1", "swarm-085-w1-assembly")
    assembled = _rev(root, "feat")
    reports = os.path.join(root, "reports", "w1")
    _evidence(reports)
    _activate_firebreak(root)

    ctx = {"root": root, "base": base, "worker_head": worker_head, "mb": mb,
           "assembled": assembled, "reports": reports,
           "plan": os.path.join(root, "plan.md"), "spec": os.path.join(root, "spec.md")}

    def payload(**over):
        p = {
            "status": "PASS-EMITTED", "run_id": "085", "wave_count": 1, "wave_index": 1,
            "run_start_ts": 1000, "expected_base_sha": base, "worker_base_sha": base,
            "roster": [{"task_id": "t1", "agent_id": "a1", "role": "models",
                        "branch": "swarm-085-w1-models", "required": "yes",
                        "status": "COMPLETED", "terminal_evidence": "completion-notified",
                        "terminal_head_sha": worker_head}],
            "worker_deltas": [{"role": "models", "worker_head_sha": worker_head,
                               "merge_base_sha": mb, "delta_count": 1}],
            "ownership_gate": {"verdict": "PASS", "path": "reports/w1/ownership-gate.md"},
            "assembled_output_sha": assembled,
            "gate_results": {
                "contract": {"verdict": "PASS", "path": "reports/w1/contract-check.md"},
                "integrated_import": {"verdict": "PASS", "path": "reports/w1/integrated-import.md"},
                "smoke": {"verdict": "PASS", "path": "reports/w1/smoke-test.md"},
                "test": {"verdict": "PASS", "path": "reports/w1/test-results.md"}},
            "firebreak_readback": {"status": "ACTIVE", "ts": 1001},
            "provenance": {"status": "PROVENANCE_OK", "path": "reports/w1/spec-provenance.md"},
            "prev_wave_output_sha": None,
        }
        p.update(over)
        return p

    ctx["payload"] = payload
    return ctx


def _emit_wave(ctx, payload, out=None):
    out = out or os.path.join(ctx["reports"], "wave.md")
    pf = _write(os.path.join(ctx["root"], "payload.json"), json.dumps(payload))
    r = subprocess.run([sys.executable, ARTIFACT, "emit", "--out", out, "--payload", pf,
                        "--emit-ts", "1234567890"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return out


def _run_wave(ctx, wave=1, reports=None):
    cmd = [sys.executable, VERIFY, "--wave", str(wave), "--plan", ctx["plan"],
           "--spec-path", ctx["spec"], "--reports-dir", reports or ctx["reports"],
           "--root", ctx["root"], "--run-id", "085", "--run-start-ts", "1000",
           "--original-branch", "feat", "--default-branch", "master"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return (p.stdout.splitlines() or [""])[0], p.returncode


@case
def test_wave_happy_pass():
    ctx = build_wave_repo()
    _emit_wave(ctx, ctx["payload"]())
    first, rc = _run_wave(ctx)
    assert rc == 0 and first.startswith("STATUS: PASS"), first


@case
def test_wave_artifact_missing():
    ctx = build_wave_repo()  # no wave.md emitted
    first, rc = _run_wave(ctx)
    _assert_fail(first, rc, "artifact missing")


@case
def test_wave_wrong_runid():
    ctx = build_wave_repo()
    _emit_wave(ctx, ctx["payload"](run_id="999"))
    first, rc = _run_wave(ctx)
    _assert_fail(first, rc, "run_id mismatch")


@case
def test_wave_stale_ts():
    ctx = build_wave_repo()
    _emit_wave(ctx, ctx["payload"](run_start_ts=999))
    first, rc = _run_wave(ctx)
    _assert_fail(first, rc, "run_start_ts mismatch")


@case
def test_wave_forged_contract_verdict():
    ctx = build_wave_repo()
    _evidence(ctx["reports"], **{"contract-check.md": "FAIL"})  # disk says FAIL
    _emit_wave(ctx, ctx["payload"]())                            # artifact claims PASS
    first, rc = _run_wave(ctx)
    _assert_fail(first, rc, "forged verdict")


@case
def test_wave_forged_ownership_verdict():
    ctx = build_wave_repo()
    _evidence(ctx["reports"], **{"ownership-gate.md": "FAIL"})
    _emit_wave(ctx, ctx["payload"]())
    first, rc = _run_wave(ctx)
    _assert_fail(first, rc, "forged verdict")


@case
def test_wave_forged_import_verdict():
    ctx = build_wave_repo()
    _evidence(ctx["reports"], **{"integrated-import.md": "FAIL -- integrated-import"})
    _emit_wave(ctx, ctx["payload"]())
    first, rc = _run_wave(ctx)
    _assert_fail(first, rc, "forged verdict")


@case
def test_wave_required_worker_failed():
    ctx = build_wave_repo()
    p = ctx["payload"]()
    p["roster"][0]["status"] = "FAILED"
    _emit_wave(ctx, p)
    first, rc = _run_wave(ctx)
    _assert_fail(first, rc, "REQUIRED worker")


@case
def test_wave_ownership_fail():
    ctx = build_wave_repo()
    p = ctx["payload"]()
    p["ownership_gate"]["verdict"] = "FAIL"
    _emit_wave(ctx, p)
    first, rc = _run_wave(ctx)
    _assert_fail(first, rc, "ownership_gate")


@case
def test_wave_integrated_import_fail_verdict():
    ctx = build_wave_repo()
    p = ctx["payload"]()
    p["gate_results"]["integrated_import"]["verdict"] = "FAIL"
    _emit_wave(ctx, p)
    first, rc = _run_wave(ctx)
    _assert_fail(first, rc, "integrated_import verdict")


@case
def test_wave_provenance_drift():
    ctx = build_wave_repo()
    _evidence(ctx["reports"], **{"spec-provenance.md": "PROVENANCE_REPAIRED_FALLBACK"})
    _emit_wave(ctx, ctx["payload"]())
    first, rc = _run_wave(ctx)
    _assert_fail(first, rc, "forged verdict")  # provenance evidence STATUS != PROVENANCE_OK


@case
def test_wave_head_mismatch():
    ctx = build_wave_repo()
    _emit_wave(ctx, ctx["payload"](assembled_output_sha="e" * 40))
    first, rc = _run_wave(ctx)
    _assert_fail(first, rc, "!= live HEAD")


@case
def test_wave_post_terminal_commit_containment():
    ctx = build_wave_repo()
    # artifact records a terminal_head_sha that != the live worker branch head
    p = ctx["payload"]()
    p["roster"][0]["terminal_head_sha"] = "f" * 40
    p["worker_deltas"][0]["worker_head_sha"] = "f" * 40
    _emit_wave(ctx, p)
    first, rc = _run_wave(ctx)
    _assert_fail(first, rc, "post-terminal-commit containment")


@case
def test_wave_firebreak_inactive_fails():
    ctx = build_wave_repo()
    subprocess.run([sys.executable, FIREBREAK, "deactivate", "--root",
                    os.path.abspath(ctx["root"])], capture_output=True, text=True)
    _emit_wave(ctx, ctx["payload"]())
    first, rc = _run_wave(ctx)
    _assert_fail(first, rc, "firebreak not ACTIVE")


@case
def test_reconcile_single_wave_happy():
    # Degenerate 1-wave reconcile: exercises the reconcile path + the N==verified
    # count check + the terminal-wave HEAD-equality (multi-wave chain/ancestor cases
    # are exercised by the live multi-wave run, plan §8).
    ctx = build_wave_repo()
    _emit_wave(ctx, ctx["payload"]())
    cmd = [sys.executable, VERIFY, "--reconcile", "--plan", ctx["plan"],
           "--spec-path", ctx["spec"], "--reports-dir", os.path.join(ctx["root"], "reports"),
           "--root", ctx["root"], "--run-id", "085", "--run-start-ts", "1000",
           "--original-branch", "feat", "--default-branch", "master"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    first = (p.stdout.splitlines() or [""])[0]
    assert p.returncode == 0 and first.startswith("STATUS: PASS"), first


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default=None)
    args = ap.parse_args(argv)
    if args.case and args.case not in CASES:
        print(f"unknown case: {args.case}\navailable: {sorted(CASES)}")
        return 2
    names = [args.case] if args.case else list(CASES)
    passed = failed = 0
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
