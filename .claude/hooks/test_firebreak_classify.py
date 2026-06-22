#!/usr/bin/env python3
"""
Unit tests for the G1 firebreak classifier.

Invokes .claude/hooks/firebreak-classify.py as a REAL subprocess (JSON on stdin),
exactly as the PreToolUse hook does, and asserts allow (silent exit 0) vs
deny (permissionDecision "deny" JSON + an approval record on disk).

Each case maps to an EARS acceptance criterion in
docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md.

Run:  python3 .claude/hooks/test_firebreak_classify.py
(No pytest dependency -- prints a PASS/FAIL summary and exits non-zero on failure.)
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CLASSIFIER = os.path.join(HERE, "firebreak-classify.py")

_results = []


def run(env_obj, sentinel, cwd=None, sentinel_path=None):
    """Run the classifier; return (is_deny, stdout, approvals_dir)."""
    tmp = tempfile.mkdtemp(prefix="fb-test-")
    repo_root = sentinel.get("repo_root") or tmp
    if sentinel_path is None:
        sentinel_path = os.path.join(tmp, "firebreak-active.json")
        with open(sentinel_path, "w") as f:
            json.dump(sentinel, f)
    env = dict(os.environ)
    if sentinel_path == "":
        env.pop("FIREBREAK_SENTINEL", None)
    else:
        env["FIREBREAK_SENTINEL"] = sentinel_path
    proc = subprocess.run(
        [sys.executable, CLASSIFIER],
        input=json.dumps(env_obj),
        capture_output=True, text=True, env=env, cwd=cwd or tmp,
    )
    is_deny = '"permissionDecision": "deny"' in proc.stdout
    approvals = os.path.join(repo_root, "todos", "approvals")
    return is_deny, proc.stdout, approvals


def check(name, got_deny, want_deny, extra=True):
    ok = (got_deny == want_deny) and extra
    _results.append((name, ok))
    verb = "deny" if want_deny else "allow"
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}  (expected {verb})")


# Common sentinels -------------------------------------------------------------
def sentinel(repo_root, **kw):
    s = {
        "run_id": "072",
        "repo_root": repo_root,
        "project_key": "-Users-test-sandbox",
        "phase": "build",
        "test_allowlist": {"pytest": True},
    }
    s.update(kw)
    return s


WORKER = {"agent_id": "w1", "agent_type": "swarm-072-api"}
GENERIC_WORKER = {"agent_id": "a4eb", "agent_type": "general-purpose"}
ORCH = {}
SWARM = {"agent_id": "s1", "agent_type": "swarm-runner"}
TAIL = {"agent_id": "t1", "agent_type": "tail-runner"}


def bash(cmd, ident):
    return {"tool_name": "Bash", "tool_input": {"command": cmd}, **ident}


def write(path, ident):
    return {"tool_name": "Write", "tool_input": {"file_path": path}, **ident}


def mcp(name, ident):
    return {"tool_name": name, "tool_input": {}, **ident}


def main():
    repo = tempfile.mkdtemp(prefix="fb-repo-")
    os.makedirs(os.path.join(repo, "src"), exist_ok=True)
    s = sentinel(repo)
    HOME = os.path.expanduser("~")

    # ---------------- Happy path (allow) ----------------
    d, _, _ = run(write("src/app.py", WORKER), s, cwd=repo)
    check("worker GREEN worktree file write", d, False)

    d, _, _ = run(bash("git commit -m 'x'", WORKER), s, cwd=repo)
    check("worker GREEN local commit", d, False)

    d, _, _ = run(write(f"{HOME}/.claude/docs/agent-pitfalls.md", TAIL), s)
    check("tail-runner learnings carve-out", d, False)

    d, _, _ = run(write(f"{HOME}/Documents/dev-notes/2026-06-22.md", ORCH), s)
    check("orchestrator learnings carve-out", d, False)

    d, _, _ = run(bash("git merge --no-ff swarm-072-assembly", SWARM), s)
    check("swarm-runner local merge --no-ff", d, False)

    d, _, _ = run(bash("pytest -q", WORKER), s)
    check("allowlisted pytest", d, False)

    d, _, _ = run(bash("python3 -m pytest", WORKER), s)
    check("allowlisted python -m pytest", d, False)

    d, _, _ = run(bash("git commit -m \"$(date)\"", WORKER), s)
    check("opacity in non-critical arg (git commit -m $(date))", d, False)

    d, _, _ = run(bash('pytest "$F"', WORKER), s)
    check("opacity in non-critical arg (pytest $F)", d, False)

    # ---------------- Outward / irreversible (deny) ----------------
    d, _, ap = run(bash("curl https://evil.example.com/x", WORKER), s)
    rec = os.path.isdir(ap) and any(os.listdir(ap))
    check("worker external curl + record written", d, True, extra=rec)

    d, _, _ = run(bash("gh api -X POST /repos/x/y/issues", WORKER), s)
    check("worker gh api", d, True)

    d, _, _ = run(bash("vercel deploy --prod", WORKER), s)
    check("worker deploy (vercel)", d, True)

    d, _, _ = run(bash("npm publish", WORKER), s)
    check("worker npm publish", d, True)

    d, _, _ = run(bash("pip uninstall requests", WORKER), s)
    check("worker pip uninstall", d, True)

    d, _, _ = run(bash("npm remove leftpad", WORKER), s)
    check("worker npm remove", d, True)

    d, _, _ = run(bash("ssh user@host 'ls'", WORKER), s)
    check("worker ssh", d, True)

    # ---------------- git evasion / force (deny) ----------------
    d, _, _ = run(bash("git push --force origin master", WORKER), s)
    check("worker git push --force", d, True)

    d, _, _ = run(bash(f"git -C {repo} push --force", WORKER), s)
    check("worker git -C <path> push --force (normalized)", d, True)

    d, _, _ = run(bash("git push origin master", WORKER), s)
    check("worker git push (shared)", d, True)

    # ---------------- F13 opaque command word / verb (deny) ----------------
    d, _, _ = run(bash("$(printf curl) https://x", WORKER), s)
    check("F13 opaque argv0 $(printf curl)", d, True)

    d, _, _ = run(bash("git $(printf push) origin master", WORKER), s)
    check("F13 opaque dispatcher verb", d, True)

    d, _, _ = run(bash("cur$(printf l) https://x", WORKER), s)
    check("F13 partial-opaque argv0", d, True)

    d, _, _ = run(bash("${X}curl https://x", WORKER), s)
    check("F13 ${X}curl argv0", d, True)

    d, _, _ = run(bash("c{u,}rl https://x", WORKER), s)
    check("F13 brace-expansion argv0", d, True)

    d, _, _ = run(bash(r"\cu\rl https://x", WORKER), s)
    check("F13 backslash-escape argv0", d, True)

    # documented residual #3: unlisted dispatcher with literal argv0 evades
    d, _, _ = run(bash("httpie POST https://x", WORKER), s)
    check("RESIDUAL #3: unlisted literal dispatcher NOT caught", d, False)

    # ---------------- indirection (deny unless framework) ----------------
    d, _, _ = run(bash("python3 deploy.py", WORKER), s)
    check("worker python3 deploy.py", d, True)

    d, _, _ = run(bash("./deploy.sh", WORKER), s)
    check("worker ./deploy.sh", d, True)

    d, _, _ = run(bash("node release.js", WORKER), s)
    check("worker node release.js", d, True)

    d, _, _ = run(bash(".venv/bin/python ship.py", WORKER), s)
    check("worker .venv/bin/python ship.py", d, True)

    d, _, _ = run(bash("npm run deploy", WORKER), s)
    check("worker npm run (not auto-allowed)", d, True)

    d, _, _ = run(bash("make release", WORKER), s)
    check("worker make (not auto-allowed)", d, True)

    # ---------------- control-plane writes (F1 + F5 + F9) ----------------
    d, _, _ = run(write(f"{HOME}/.claude/settings.json", WORKER), s)
    check("worker Write control-plane settings", d, True)

    d, _, _ = run(write(f"{HOME}/.claude/settings.json", SWARM), s)
    check("trusted swarm-runner Write control-plane", d, False)

    d, _, _ = run(write(f"{repo}/.claude/firebreak-active.json", WORKER), s)
    check("worker Write sentinel", d, True)

    d, _, _ = run(bash(f"cp evil {HOME}/.claude/settings.json", WORKER), s)
    check("worker cp to control-plane", d, True)

    d, _, _ = run(bash(f"ln -sf evil {HOME}/.claude/settings.json", WORKER), s)
    check("worker ln -sf to control-plane", d, True)

    d, _, _ = run(
        bash('DEST=$HOME/.claude/settings.json cp evil "$DEST"', WORKER), s)
    check("worker env-indirected control-plane cp", d, True)

    d, _, _ = run(bash('cp evil "$UNKNOWN_DEST"', WORKER), s)
    check("worker fully-opaque cp dest (F9c)", d, True)

    d, _, _ = run(bash("cp src/a.py src/b.py", WORKER), s, cwd=repo)
    check("worker cp worktree->worktree stays GREEN", d, False)

    # ---------------- out-of-repo deletes / data ----------------
    d, _, _ = run(bash(f"rm -rf {HOME}/Data/leads.db", WORKER), s)
    check("worker rm out-of-repo db (data)", d, True)

    d, _, _ = run(bash("rm src/old.py", WORKER), s, cwd=repo)
    check("worker rm inside worktree stays GREEN", d, False)

    # ---------------- learnings carve-out negatives ----------------
    d, _, _ = run(write(f"{HOME}/.claude/docs/agent-pitfalls.md", WORKER), s)
    check("worker learnings write denied", d, True)

    d, _, _ = run(write(f"{HOME}/Documents/dev-notes/../.ssh/x", TAIL), s)
    check("tail-runner escaping learnings path denied", d, True)

    # ---------------- git alias evasions (R4a) ----------------
    d, _, _ = run(bash("git -c alias.p=push p", WORKER), s)
    check("git -c alias.p=push p", d, True)

    d, _, _ = run(bash("git -c alias.p=push fetch", WORKER), s)
    check("git -c alias.p=push (definition alone)", d, True)

    d, _, _ = run(bash("git config alias.p push", WORKER), s)
    check("git config alias.p push (setup)", d, True)

    d, _, _ = run(bash("git -c alias.x='!curl evil' x", WORKER), s)
    check("git -c alias.x=!curl (shell-escape alias)", d, True)

    d, _, _ = run(bash("git -c core.pager=cat log", WORKER), s)
    check("git -c core.pager=cat log stays GREEN", d, False)

    # ---------------- listed wrapper -c command-string forms ----------------
    d, _, _ = run(bash("flock /tmp/l -c 'curl https://x'", WORKER), s)
    check("flock /tmp/l -c 'curl ...'", d, True)

    d, _, _ = run(bash("timeout 5 sh -c 'curl https://x'", WORKER), s)
    check("timeout 5 sh -c 'curl ...'", d, True)

    d, _, _ = run(bash("flock /tmp/l -c 'pytest -q'", WORKER), s)
    check("flock /tmp/l -c 'pytest' stays GREEN", d, False)

    d, _, _ = run(bash("timeout 5 ./deploy.sh", WORKER), s)
    check("timeout 5 ./deploy.sh (wrapper + direct script)", d, True)

    d, _, _ = run(bash("env FOO=bar ./deploy", WORKER), s, cwd=repo)
    check("env FOO=bar ./deploy (wrapper + assignment + script)", d, True)

    # ---------------- mcp ----------------
    d, _, _ = run(mcp("mcp__supabase__apply_migration", WORKER), s)
    check("mcp apply_migration denied", d, True)

    d, _, _ = run(mcp("mcp__vercel__deploy_to_vercel", WORKER), s)
    check("mcp deploy_to_vercel denied", d, True)

    d, _, _ = run(mcp("mcp__supabase__get_project", WORKER), s)
    check("mcp get_project allowed", d, False)

    # ---------------- blanket-deny fallback (F8) ----------------
    sb = sentinel(repo, blanket_deny_control_plane=True)
    d, _, _ = run(write(f"{HOME}/.claude/settings.json", SWARM), sb)
    check("blanket-deny: trusted control-plane write denied", d, True)

    d, _, _ = run(
        write(f"{repo}/.claude/firebreak-active.json", ORCH), sb)
    check("blanket-deny: orchestrator sentinel teardown allowed", d, False)

    # ---------------- no sentinel (manual session no-op) ----------------
    nodir = tempfile.mkdtemp(prefix="fb-nosent-")
    d, _, _ = run(bash("curl https://evil.example.com", WORKER), s,
                  cwd=nodir, sentinel_path="")
    check("no sentinel -> no-op allow", d, False)

    # ---------------- approval record write failure still denies ----------
    bad = sentinel("/nonexistent/cannot/create/here")
    d, out, _ = run(bash("curl https://evil.example.com", WORKER), bad)
    check("record write fail -> still deny", d, True,
          extra=("RECORD_WRITE_FAILED" in out or '"deny"' in out))

    # ---------------- record filename format ----------------
    d, _, ap = run(bash("curl https://evil.example.com", WORKER), s)
    files = os.listdir(ap) if os.path.isdir(ap) else []
    fmt_ok = any(f.startswith("RED-072-") and f.endswith(".md") for f in files)
    check("approval filename RED-<run>-<cat>-<uuid>.md", d, True, extra=fmt_ok)

    # ---------------- summary ----------------
    total = len(_results)
    passed = sum(1 for _, ok in _results if ok)
    print(f"\n{passed}/{total} passed")
    failed = [n for n, ok in _results if not ok]
    if failed:
        print("FAILURES:")
        for n in failed:
            print(f"  - {n}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
