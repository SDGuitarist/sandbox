"""FC68 / 083-W6 -- deterministic firebreak sentinel root anchoring.

The activator must land the run sentinel at the MAIN worktree root regardless of the
orchestrator's cwd, and must FAIL CLOSED (never write) when the resolved root is a
LINKED worktree or is not a real firebreak repo. Detection is git-metadata-based and
pathname-independent, so a linked worktree placed ANYWHERE -- not just under
.claude/worktrees/ -- reached via a symlink alias or a case-variant spelling is still
rejected (Codex P1).

These are live-lifecycle tests: they build REAL git repos and REAL linked worktrees
(git worktree add) under tmp_path and invoke the activator as a subprocess (the way
the orchestrator does). Nothing here touches the actual repo's .claude/.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_ACTIVATE = os.path.join(REPO_ROOT, ".claude", "hooks", "firebreak-activate.py")


# --------------------------------------------------------------------------- #
# Fixtures / helpers -- real git repos and worktrees
# --------------------------------------------------------------------------- #

def _git(*args, cwd=None):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   capture_output=True, text=True)


def _init_main_repo(path):
    """Create a REAL git repo at `path` carrying a firebreak control-plane tree,
    with one commit so `git worktree add` works. Returns realpath(path)."""
    os.makedirs(path, exist_ok=True)
    _git("init", "-q", path)
    _git("-C", path, "config", "user.email", "t@example.com")
    _git("-C", path, "config", "user.name", "t")
    _git("-C", path, "config", "commit.gpgsign", "false")
    hooks = os.path.join(path, ".claude", "hooks")
    os.makedirs(hooks, exist_ok=True)
    # stub classifier so the presence guard passes
    open(os.path.join(hooks, "firebreak-classify.py"), "w").close()
    # copy the REAL activator so __file__ two-up resolves to this repo
    shutil.copy(REAL_ACTIVATE, os.path.join(hooks, "firebreak-activate.py"))
    _git("-C", path, "add", "-A")
    _git("-C", path, "commit", "-q", "-m", "init")
    return os.path.realpath(path)


def _add_worktree(main, wt_path, branch):
    """Create a REAL linked worktree at `wt_path` (checks out the tree, so it carries
    its OWN tracked .claude/hooks/firebreak-*). Returns realpath(wt_path)."""
    _git("-C", main, "worktree", "add", "-q", "-b", branch, wt_path)
    return os.path.realpath(wt_path)


def _script(root):
    return os.path.join(root, ".claude", "hooks", "firebreak-activate.py")


def _run(script, args, cwd):
    return subprocess.run([sys.executable, script, *args], cwd=cwd,
                          capture_output=True, text=True)


def _sentinel(root):
    return os.path.join(root, ".claude", "firebreak-active.json")


def _fs_is_case_insensitive(base):
    probe = os.path.join(base, "CaseProbe")
    os.makedirs(probe, exist_ok=True)
    return os.path.isdir(os.path.join(base, "caseprobe"))


# --------------------------------------------------------------------------- #
# Happy path / confirmed behaviors
# --------------------------------------------------------------------------- #

def test_root_flag_lands_at_main_from_worktree_cwd(tmp_path):
    """The exact FC68 scenario: cwd drifted into a linked worktree, --root <main abs>
    given -> sentinel lands ONLY at MAIN, with a canonical repo_root."""
    main = _init_main_repo(str(tmp_path / "main"))
    wt = _add_worktree(main, str(tmp_path / "main" / ".claude" / "worktrees" / "agent-x"), "wtx")
    r = _run(_script(main), ["activate", "R1", "--root", main], cwd=wt)
    assert r.returncode == 0, r.stderr
    rec = json.load(open(_sentinel(main)))
    assert rec["repo_root"] == main == os.path.realpath(main)
    assert rec["run_id"] == "R1"
    assert not os.path.exists(_sentinel(wt))


def test_file_anchor_from_main_root_no_flag(tmp_path):
    """No --root: __file__ two-up resolves to the (main) repo root and writes there."""
    main = _init_main_repo(str(tmp_path / "main"))
    r = _run(_script(main), ["activate", "R2"], cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert json.load(open(_sentinel(main)))["repo_root"] == main


def test_set_phase_preserves_run_id_and_repo_root(tmp_path):
    main = _init_main_repo(str(tmp_path / "main"))
    assert _run(_script(main), ["activate", "R4", "--root", main], cwd=str(tmp_path)).returncode == 0
    assert _run(_script(main), ["set-phase", "tail", "--root", main], cwd=str(tmp_path)).returncode == 0
    rec = json.load(open(_sentinel(main)))
    assert rec["phase"] == "tail"
    assert rec["run_id"] == "R4"
    assert rec["repo_root"] == main


# --------------------------------------------------------------------------- #
# Fail-closed: linked worktrees (P1 -- the core of Codex's NO-GO)
# --------------------------------------------------------------------------- #

def test_refuses_linked_worktree_OUTSIDE_dot_claude(tmp_path):
    """A linked worktree placed OUTSIDE .claude/worktrees/ (the substring guard would
    have MISSED this) is rejected via git metadata."""
    main = _init_main_repo(str(tmp_path / "main"))
    wt = _add_worktree(main, str(tmp_path / "external-wt"), "ext")  # NOT under .claude/worktrees/
    assert "/.claude/worktrees/" not in wt + "/"
    r = _run(_script(main), ["activate", "R1", "--root", wt], cwd=str(tmp_path))
    assert r.returncode == 3, r.stdout
    assert "linked worktree" in r.stderr.lower()
    assert not os.path.exists(_sentinel(wt))


def test_file_anchor_refuses_when_script_lives_in_worktree(tmp_path):
    """FC68 core defense: the worktree's OWN tracked copy of the activator, run with
    no --root, fails closed (its __file__ two-up is a linked-worktree root)."""
    main = _init_main_repo(str(tmp_path / "main"))
    wt = _add_worktree(main, str(tmp_path / "external-wt"), "ext")
    r = _run(_script(wt), ["activate", "R3"], cwd=wt)
    assert r.returncode == 3, r.stdout
    assert "linked worktree" in r.stderr.lower()
    assert not os.path.exists(_sentinel(wt))


def test_refuses_symlink_alias_to_linked_worktree(tmp_path):
    """A symlink alias to a linked worktree is canonicalized then rejected."""
    main = _init_main_repo(str(tmp_path / "main"))
    wt = _add_worktree(main, str(tmp_path / "external-wt"), "ext")
    alias = str(tmp_path / "alias-wt")
    os.symlink(wt, alias)
    r = _run(_script(main), ["activate", "R1", "--root", alias], cwd=str(tmp_path))
    assert r.returncode == 3, r.stdout
    assert "linked worktree" in r.stderr.lower()


def test_symlink_alias_to_MAIN_is_accepted(tmp_path):
    """Counterpart: a symlink alias to the MAIN worktree canonicalizes to main and
    IS accepted (the sentinel is stored under the canonical main path)."""
    main = _init_main_repo(str(tmp_path / "main"))
    alias = str(tmp_path / "alias-main")
    os.symlink(main, alias)
    r = _run(_script(main), ["activate", "R1", "--root", alias], cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert json.load(open(_sentinel(main)))["repo_root"] == main


def test_case_variant_of_linked_worktree_rejected(tmp_path):
    """On a case-insensitive filesystem, a case-variant spelling of a linked-worktree
    path must NOT evade the guard (git resolves it case-insensitively -> linked)."""
    if not _fs_is_case_insensitive(str(tmp_path)):
        pytest.skip("filesystem is case-sensitive")
    main = _init_main_repo(str(tmp_path / "main"))
    wt = _add_worktree(main, str(tmp_path / "external-wt"), "ext")
    variant = wt[:-1] + wt[-1].upper() if wt[-1].islower() else wt[:-1] + wt[-1].lower()
    r = _run(_script(main), ["activate", "R1", "--root", variant], cwd=str(tmp_path))
    # Rejected either as a linked worktree (git metadata) or as a top-level mismatch
    # (realpath keeps the typed case, git returns canonical) -- either way fail-closed.
    assert r.returncode == 3, r.stdout
    assert "REFUSING" in r.stderr
    assert not os.path.exists(_sentinel(variant))


# --------------------------------------------------------------------------- #
# Fail-closed: bad --root / non-repo
# --------------------------------------------------------------------------- #

def test_rejects_relative_root(tmp_path):
    """A relative --root would re-introduce cwd coupling; reject it (exit 3)."""
    main = _init_main_repo(str(tmp_path / "main"))
    r = _run(_script(main), ["status", "--root", "some/relative/path"], cwd=main)
    assert r.returncode == 3
    assert "absolute" in r.stderr.lower()


def test_rejects_non_git_root(tmp_path):
    """An absolute root that is not a git working tree is rejected."""
    main = _init_main_repo(str(tmp_path / "main"))
    plain = tmp_path / "plain"
    (plain / ".claude" / "hooks").mkdir(parents=True)
    open(plain / ".claude" / "hooks" / "firebreak-classify.py", "w").close()
    r = _run(_script(main), ["status", "--root", str(plain)], cwd=str(main))
    assert r.returncode == 3
    assert "git working tree" in r.stderr.lower()


def test_rejects_root_missing_classifier(tmp_path):
    """A git repo without .claude/hooks/firebreak-classify.py is not a firebreak repo."""
    bare = tmp_path / "bare"
    _init_main_repo(str(bare))
    os.remove(os.path.join(str(os.path.realpath(bare)), ".claude", "hooks", "firebreak-classify.py"))
    main = _init_main_repo(str(tmp_path / "main"))
    r = _run(_script(main), ["status", "--root", os.path.realpath(str(bare))], cwd=str(main))
    assert r.returncode == 3
    assert "firebreak-classify.py" in r.stderr


def test_rejects_subdir_of_main(tmp_path):
    """--root pointing at a SUBDIR of the main worktree (not its top-level) is rejected
    -- the sentinel would sit below where workers walk up to. (Caught by the
    classifier-presence guard first: a subdir has no .claude/hooks/firebreak-classify.py
    at its own root; a subdir that DID would hit the top-level-mismatch guard. Either
    way fail-closed.)"""
    main = _init_main_repo(str(tmp_path / "main"))
    sub = os.path.join(main, ".claude", "hooks")  # a real dir, but not the top-level
    r = _run(_script(main), ["status", "--root", sub], cwd=str(main))
    assert r.returncode == 3
    assert "REFUSING" in r.stderr


# --------------------------------------------------------------------------- #
# CLI surface (P2)
# --------------------------------------------------------------------------- #

def test_missing_root_value_is_usage_error(tmp_path):
    main = _init_main_repo(str(tmp_path / "main"))
    r = _run(_script(main), ["status", "--root"], cwd=str(main))
    assert r.returncode == 2
    assert "--root requires" in r.stderr


def test_root_equals_form(tmp_path):
    main = _init_main_repo(str(tmp_path / "main"))
    r = _run(_script(main), ["activate", "R5", f"--root={main}"], cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert json.load(open(_sentinel(main)))["repo_root"] == main


def test_root_arg_positions(tmp_path):
    """--root is accepted before, between, and after the positional args."""
    main = _init_main_repo(str(tmp_path / "main"))
    forms = [
        ["activate", "--root", main, "RP", "proj", "build"],
        ["activate", "RP", "--root", main, "proj", "build"],
        ["activate", "RP", "proj", "build", "--root", main],
    ]
    for form in forms:
        assert _run(_script(main), ["deactivate", "--root", main], cwd=str(tmp_path)).returncode == 0
        r = _run(_script(main), form, cwd=str(tmp_path))
        assert r.returncode == 0, (form, r.stderr)
        rec = json.load(open(_sentinel(main)))
        assert rec["run_id"] == "RP" and rec["project_key"] == "proj" and rec["phase"] == "build"


def test_legacy_full_positional_form(tmp_path):
    """The full legacy activate <run_id> <project> <phase> <json_allowlist> form."""
    main = _init_main_repo(str(tmp_path / "main"))
    r = _run(_script(main),
             ["activate", "R6", "myproj", "tail", '{"pytest": true, "ruff": false}', "--root", main],
             cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    rec = json.load(open(_sentinel(main)))
    assert rec["run_id"] == "R6"
    assert rec["project_key"] == "myproj"
    assert rec["phase"] == "tail"
    assert rec["test_allowlist"] == {"pytest": True, "ruff": False}


def test_status_active_and_inactive(tmp_path):
    main = _init_main_repo(str(tmp_path / "main"))
    r = _run(_script(main), ["status", "--root", main], cwd=str(tmp_path))
    assert r.returncode == 0 and "INACTIVE" in r.stdout
    assert _run(_script(main), ["activate", "R7", "--root", main], cwd=str(tmp_path)).returncode == 0
    r = _run(_script(main), ["status", "--root", main], cwd=str(tmp_path))
    assert r.returncode == 0
    assert "ACTIVE" in r.stdout and f"root={main}" in r.stdout and "R7" in r.stdout


def test_deactivate(tmp_path):
    main = _init_main_repo(str(tmp_path / "main"))
    assert _run(_script(main), ["activate", "R8", "--root", main], cwd=str(tmp_path)).returncode == 0
    assert os.path.exists(_sentinel(main))
    r = _run(_script(main), ["deactivate", "--root", main], cwd=str(tmp_path))
    assert r.returncode == 0 and "INACTIVE" in r.stdout
    assert not os.path.exists(_sentinel(main))
    # idempotent
    r = _run(_script(main), ["deactivate", "--root", main], cwd=str(tmp_path))
    assert r.returncode == 0 and "already inactive" in r.stdout
