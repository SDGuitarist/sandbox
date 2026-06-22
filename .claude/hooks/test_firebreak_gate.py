#!/usr/bin/env python3
"""
Unit tests for the G1 firebreak cheap entry gate (firebreak-gate.sh).

Verifies the R6 fast-path: a GREEN command exits 0 WITHOUT spawning python
(proved via FIREBREAK_TRACE -> "CLASSIFIER_RAN" on the classifier's stderr),
while a RED-bearing call forwards and yields a deny decision.

Run:  python3 .claude/hooks/test_firebreak_gate.py
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "firebreak-gate.sh")

_results = []


def run_gate(env_obj):
    repo = tempfile.mkdtemp(prefix="fb-gate-")
    sentinel = {"run_id": "072", "repo_root": repo,
                "project_key": "k", "phase": "build", "test_allowlist": {}}
    spath = os.path.join(repo, "firebreak-active.json")
    with open(spath, "w") as f:
        json.dump(sentinel, f)
    env = dict(os.environ)
    env["FIREBREAK_SENTINEL"] = spath
    env["FIREBREAK_TRACE"] = "1"
    proc = subprocess.run(["bash", GATE], input=json.dumps(env_obj),
                          capture_output=True, text=True, env=env, cwd=repo)
    spawned = "CLASSIFIER_RAN" in proc.stderr
    is_deny = '"permissionDecision": "deny"' in proc.stdout
    return spawned, is_deny, proc


def check(name, ok):
    _results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")


WORKER = {"agent_id": "w1", "agent_type": "swarm-072-api"}


def bash(cmd):
    return {"tool_name": "Bash", "tool_input": {"command": cmd}, **WORKER}


def write(path, content="x"):
    return {"tool_name": "Write",
            "tool_input": {"file_path": path, "content": content}, **WORKER}


def main():
    # GREEN bash -> fast-path: no python spawn, no deny.
    spawned, deny, _ = run_gate(bash("pytest -q"))
    check("GREEN 'pytest -q' fast-path (no python spawn)", not spawned and not deny)

    spawned, deny, _ = run_gate(bash("ls -la"))
    check("GREEN 'ls -la' fast-path (no python spawn)", not spawned and not deny)

    spawned, deny, _ = run_gate(bash("git commit -m wip"))
    check("GREEN 'git commit' fast-path (no python spawn)", not spawned and not deny)

    # GREEN write to a worktree file: content mentions 'python'/'curl' but the
    # gate must inspect only file_path -> still fast-path.
    spawned, deny, _ = run_gate(
        write("src/app.py", "import requests  # curl-like python helper"))
    check("GREEN worktree Write fast-path (content ignored)",
          not spawned and not deny)

    # RED bash -> forwarded + denied.
    spawned, deny, _ = run_gate(bash("curl https://evil.example.com/x"))
    check("RED curl forwarded + denied", spawned and deny)

    spawned, deny, _ = run_gate(bash("git push --force origin master"))
    check("RED git push --force forwarded + denied", spawned and deny)

    # F13 envelope-safe opacity ($() ) -> forwarded.
    spawned, deny, _ = run_gate(bash("$(printf curl) https://x"))
    check("F13 $(...) forwarded + denied", spawned and deny)

    # Control-plane Write -> forwarded + denied.
    spawned, deny, _ = run_gate(
        write(os.path.expanduser("~/.claude/settings.json")))
    check("RED control-plane Write forwarded + denied", spawned and deny)

    # mcp non-readonly -> forwarded + denied.
    spawned, deny, _ = run_gate(
        {"tool_name": "mcp__supabase__apply_migration", "tool_input": {}, **WORKER})
    check("RED mcp apply_migration forwarded + denied", spawned and deny)

    # mcp readonly -> forwarded but allowed (gate forwards all mcp; classifier allows).
    spawned, deny, _ = run_gate(
        {"tool_name": "mcp__supabase__get_project", "tool_input": {}, **WORKER})
    check("mcp get_project forwarded but allowed", spawned and not deny)

    # Brace/backslash command-word obfuscation -- matched against the extracted
    # COMMAND (not raw JSON), so the envelope's `{` no longer collapses this.
    spawned, deny, _ = run_gate(bash("c{u,}rl https://x"))
    check("F13 brace 'c{u,}rl' forwarded + denied", spawned and deny)

    spawned, deny, _ = run_gate(bash(r"\cu\rl https://x"))
    check("F13 backslash '\\cu\\rl' forwarded + denied", spawned and deny)

    # Direct script-path argv0 (./x, path/to/x, /abs/x) -- forwarded + denied.
    spawned, deny, _ = run_gate(bash("./deploy"))
    check("direct './deploy' forwarded + denied", spawned and deny)

    spawned, deny, _ = run_gate(bash("scripts/deploy --prod"))
    check("path 'scripts/deploy' forwarded + denied", spawned and deny)

    spawned, deny, _ = run_gate(bash("/usr/local/bin/ship"))
    check("abs '/usr/local/bin/ship' forwarded + denied", spawned and deny)

    # $HOME-rooted Write path -> forwarded + denied (out-of-worktree).
    spawned, deny, _ = run_gate(write("$HOME/evil.txt"))
    check("$HOME Write path forwarded + denied", spawned and deny)

    # npm remove (superset gap found in 2nd review) -> forwarded + denied.
    spawned, deny, _ = run_gate(bash("npm remove leftpad"))
    check("npm remove forwarded + denied", spawned and deny)

    # GREEN over-forward guards: a quoted arg (JSON-escaped \") and a path ARG must
    # NOT trip brace/backslash/script-path -> stay fast-path.
    spawned, deny, _ = run_gate(bash('git commit -m "wip fix"'))
    check("GREEN quoted-arg commit stays fast-path", not spawned and not deny)

    spawned, deny, _ = run_gate(bash("cat src/module/file.py"))
    check("GREEN 'cat src/..' path-ARG stays fast-path", not spawned and not deny)

    total = len(_results)
    passed = sum(1 for _, ok in _results if ok)
    print(f"\n{passed}/{total} passed")
    fails = [n for n, ok in _results if not ok]
    if fails:
        for n in fails:
            print(f"  - {n}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
