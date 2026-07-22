"""FC68 / 083-W6 -- deterministic firebreak sentinel root anchoring.

The activator must land the run sentinel at the MAIN repo root regardless of the
orchestrator's cwd, and must FAIL CLOSED (never write) when the resolved root is a
worktree or is not a real firebreak repo. These are live-lifecycle tests: they copy
the REAL activator into a hermetic fake-repo tree under tmp_path and invoke it as a
subprocess (the way the orchestrator does), so `__file__` anchoring is exercised for
real. Nothing here touches the actual repo's .claude/.
"""
import json
import os
import shutil
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_ACTIVATE = os.path.join(REPO_ROOT, ".claude", "hooks", "firebreak-activate.py")


def _make_repo(base, worktree=False):
    """Build a fake firebreak repo tree and return its root. With worktree=True the
    root is nested under <base>/.claude/worktrees/agent-x (a worktree-shaped root)."""
    root = os.path.join(base, ".claude", "worktrees", "agent-x") if worktree else base
    hooks = os.path.join(root, ".claude", "hooks")
    os.makedirs(hooks, exist_ok=True)
    # stub classifier so the presence guard passes (isolates the worktree guard)
    open(os.path.join(hooks, "firebreak-classify.py"), "w").close()
    # copy the REAL activator so __file__ two-up resolves to `root`
    shutil.copy(REAL_ACTIVATE, os.path.join(hooks, "firebreak-activate.py"))
    return root


def _script(root):
    return os.path.join(root, ".claude", "hooks", "firebreak-activate.py")


def _run(script, args, cwd):
    return subprocess.run([sys.executable, script, *args], cwd=cwd,
                          capture_output=True, text=True)


def _sentinel(root):
    return os.path.join(root, ".claude", "firebreak-active.json")


def test_root_flag_lands_sentinel_at_main_from_foreign_cwd(tmp_path):
    """--root pins the main root even when cwd is unrelated (the FC68 fix)."""
    main = _make_repo(str(tmp_path / "main"))
    foreign = tmp_path / "elsewhere"
    foreign.mkdir()
    r = _run(_script(main), ["activate", "R1", "--root", main], cwd=str(foreign))
    assert r.returncode == 0, r.stderr
    rec = json.load(open(_sentinel(main)))
    assert rec["repo_root"] == main
    assert rec["run_id"] == "R1"


def test_root_flag_lands_at_main_from_worktree_cwd(tmp_path):
    """The exact FC68 scenario: cwd drifted into a worktree, --root <main> given ->
    sentinel lands at MAIN, not the worktree."""
    main = _make_repo(str(tmp_path / "main"))
    wt = _make_repo(str(tmp_path / "main"), worktree=True)
    r = _run(_script(main), ["activate", "R1", "--root", main], cwd=wt)
    assert r.returncode == 0, r.stderr
    assert json.load(open(_sentinel(main)))["repo_root"] == main
    assert not os.path.exists(_sentinel(wt))


def test_refuses_root_inside_worktree(tmp_path):
    """--root pointing inside .claude/worktrees/ is refused (fail closed)."""
    main = _make_repo(str(tmp_path / "main"))
    wt = _make_repo(str(tmp_path / "main"), worktree=True)
    r = _run(_script(main), ["activate", "R1", "--root", wt], cwd=str(tmp_path))
    assert r.returncode == 3
    assert "worktree" in r.stderr.lower()
    assert not os.path.exists(_sentinel(wt))


def test_refuses_non_firebreak_root(tmp_path):
    """A root without .claude/hooks/firebreak-classify.py is refused."""
    main = _make_repo(str(tmp_path / "main"))
    empty = tmp_path / "empty"
    empty.mkdir()
    r = _run(_script(main), ["status", "--root", str(empty)], cwd=str(main))
    assert r.returncode == 3
    assert "firebreak-classify.py" in r.stderr


def test_file_anchor_from_main_root_no_flag(tmp_path):
    """No --root: __file__ two-up resolves to the (main) repo root and writes there."""
    main = _make_repo(str(tmp_path / "main"))
    r = _run(_script(main), ["activate", "R2"], cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert json.load(open(_sentinel(main)))["repo_root"] == main


def test_file_anchor_refuses_when_script_lives_in_worktree(tmp_path):
    """FC68 core defense: the worktree's OWN tracked copy of the activator, run with
    no --root, fails closed (its __file__ two-up is a worktree root)."""
    _make_repo(str(tmp_path / "main"))
    wt = _make_repo(str(tmp_path / "main"), worktree=True)
    r = _run(_script(wt), ["activate", "R3"], cwd=wt)
    assert r.returncode == 3
    assert "worktree" in r.stderr.lower()
    assert not os.path.exists(_sentinel(wt))


def test_missing_root_value_is_usage_error(tmp_path):
    """`--root` with no value is a usage error (exit 2), not a silent None."""
    main = _make_repo(str(tmp_path / "main"))
    r = _run(_script(main), ["status", "--root"], cwd=str(main))
    assert r.returncode == 2
    assert "--root requires" in r.stderr


def test_set_phase_preserves_fields(tmp_path):
    """set-phase updates phase in place, preserving run_id and repo_root."""
    main = _make_repo(str(tmp_path / "main"))
    assert _run(_script(main), ["activate", "R4", "proj", "build", "--root", main],
                cwd=str(tmp_path)).returncode == 0
    assert _run(_script(main), ["set-phase", "tail", "--root", main],
                cwd=str(tmp_path)).returncode == 0
    rec = json.load(open(_sentinel(main)))
    assert rec["phase"] == "tail"
    assert rec["run_id"] == "R4"
    assert rec["repo_root"] == main
