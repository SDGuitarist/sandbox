#!/usr/bin/env python3
"""Spike 0a — falsify the spec-only premise with a genuine END-TO-END two-wave spike.

Plan: docs/plans/2026-07-22-p1p2-unattended-swarm-wave-barrier-plan.md  §0.0a

Builds a throwaway git repo, simulates a Wave-2 worker authoring a file that
imports a Wave-1 export while the Wave-1 FILE IS ABSENT, records whether
author+commit / compileall / import succeed, THEN assembles BOTH waves and runs
the pinned integrated gate (`python -m compileall` + the pytest import-smoke) on
the integrated tree.

PASS (both): (1) Wave-2 author+commit succeeds with Wave-1 absent, AND (2) the
integrated tree passes compileall + import-smoke.
FAIL (either): author+commit needs the prior file present, OR the integrated
tree cannot pass the gate -> STOP for plan revision (do NOT scope-cut).

Writes docs/reports/p1p2-spikes/0a-result.md and prints STATUS on the last line.
Run:  python3 tools/spike_two_wave_setup.py
"""

import os
import shutil
import subprocess
import tempfile

SANDBOX = "/Users/alejandroguillen/Projects/sandbox"
VENV_PY = os.path.join(SANDBOX, ".venv/bin/python")
VENV_PYTEST = os.path.join(SANDBOX, ".venv/bin/pytest")
IMPORTSMOKE = os.path.join(SANDBOX, "tools/spike_two_wave_importsmoke.py")
REPORT = os.path.join(SANDBOX, "docs/reports/p1p2-spikes/0a-result.md")

ENV = dict(os.environ, GIT_AUTHOR_NAME="spike", GIT_AUTHOR_EMAIL="spike@local",
           GIT_COMMITTER_NAME="spike", GIT_COMMITTER_EMAIL="spike@local")


def run(args, cwd, extra_env=None):
    env = dict(ENV, **(extra_env or {}))
    p = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def git(args, cwd):
    return run(["git"] + args, cwd)


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    repo = tempfile.mkdtemp(prefix="twowave-")
    log = []

    def note(k, rc, out=""):
        log.append((k, rc, out))

    try:
        # --- Fixture: main branch with spec + empty pkgspike (Wave-1 file ABSENT) ---
        git(["init", "-b", "main"], repo)
        write(os.path.join(repo, "pkgspike/__init__.py"), "")
        write(os.path.join(repo, "SPEC.md"),
              "# Export Names\n"
              "| Name | Type | Defined By | Used By |\n"
              "|------|------|-----------|---------|\n"
              "| pkgspike.database.query | function | database (Wave 1) | routes (Wave 2) |\n")
        git(["add", "-A"], repo)
        git(["commit", "-m", "base: spec + empty pkgspike"], repo)
        rc, base = git(["rev-parse", "HEAD"], repo)
        git(["branch", "feat-spike", "main"], repo)

        # --- Wave-1 worker (database): authors pkgspike/database.py on its own branch ---
        wt_w1 = os.path.join(repo, ".wt/w1")
        git(["worktree", "add", "-b", "w1-database", wt_w1, "main"], repo)
        write(os.path.join(wt_w1, "pkgspike/database.py"),
              "def query():\n    return []\n")
        git(["add", "-A"], wt_w1)
        git(["commit", "-m", "wave1: database.query"], wt_w1)
        rc, w1_head = git(["rev-parse", "HEAD"], wt_w1)

        # --- Wave-2 worker (routes): rooted on main, database.py ABSENT here ---
        wt_w2 = os.path.join(repo, ".wt/w2")
        git(["worktree", "add", "-b", "w2-routes", wt_w2, "main"], repo)
        w1_absent = not os.path.exists(os.path.join(wt_w2, "pkgspike/database.py"))
        note("wave1_file_absent_in_wave2_worktree", 0 if w1_absent else 1,
             str(w1_absent))
        # Author against the SPEC's export NAME (no execution).
        write(os.path.join(wt_w2, "pkgspike/routes.py"),
              "from pkgspike.database import query\n\n\n"
              "def list_rows():\n    return query()\n")
        rc_add, _ = git(["add", "-A"], wt_w2)
        rc_commit, commit_out = git(["commit", "-m", "wave2: routes uses query"], wt_w2)
        note("wave2_author_commit", rc_commit, commit_out.splitlines()[-1] if commit_out else "")

        # Step-1 self-verification attempts IN the Wave-2 worktree (Wave-1 absent):
        rc_c, out_c = run([VENV_PY, "-m", "compileall", "pkgspike/routes.py"], wt_w2)
        note("wave2_compileall_routes (absent)", rc_c, out_c.splitlines()[-1] if out_c else "")
        rc_i, out_i = run([VENV_PY, "-c", "import pkgspike.routes"], wt_w2)
        note("wave2_import (absent, EXPECT FAIL)", rc_i,
             (out_i.splitlines()[-1] if out_i else ""))

        # --- Assembly: cherry-pick Wave-1 then Wave-2 onto an assembly branch ---
        wt_asm = os.path.join(repo, ".wt/asm")
        git(["worktree", "add", "-b", "asm", wt_asm, "feat-spike"], repo)
        rc, mb1 = git(["merge-base", "feat-spike", "w1-database"], repo)
        rc, mb2 = git(["merge-base", "feat-spike", "w2-routes"], repo)
        rc_cp1, out_cp1 = git(["cherry-pick", f"{mb1}..w1-database"], wt_asm)
        note("assembly_cherrypick_wave1", rc_cp1, out_cp1.splitlines()[-1] if out_cp1 else "")
        rc_cp2, out_cp2 = git(["cherry-pick", f"{mb2}..w2-routes"], wt_asm)
        note("assembly_cherrypick_wave2", rc_cp2, out_cp2.splitlines()[-1] if out_cp2 else "")
        both_present = (os.path.exists(os.path.join(wt_asm, "pkgspike/database.py"))
                        and os.path.exists(os.path.join(wt_asm, "pkgspike/routes.py")))
        note("assembly_both_files_present", 0 if both_present else 1, str(both_present))

        # --- Integrated gate on the assembled tree ---
        rc_ic, out_ic = run([VENV_PY, "-m", "compileall", "pkgspike"], wt_asm)
        note("integrated_compileall", rc_ic, out_ic.splitlines()[-1] if out_ic else "")
        rc_is, out_is = run(
            [VENV_PYTEST, IMPORTSMOKE, "-q", "-p", "no:cacheprovider"],
            SANDBOX, extra_env={"PKGSPIKE_ROOT": wt_asm})
        note("integrated_import_smoke (pytest)", rc_is,
             out_is.splitlines()[-1] if out_is else "")

        # --- Verdict per plan §0.0a ---
        def ok(key):
            return any(k == key and rc == 0 for k, rc, _ in log)

        step1_authorcommit = ok("wave2_author_commit")
        step2_integrated = ok("integrated_compileall") and ok("integrated_import_smoke (pytest)")
        import_failed_absent = any(k.startswith("wave2_import") and rc != 0 for k, rc, _ in log)

        passed = step1_authorcommit and step2_integrated
        status = "PASS" if passed else "FAIL"

        lines = [f"STATUS: {status}", "", "# Spike 0a — end-to-end two-wave falsification", "",
                 f"- repo: {repo}", f"- base sha: {base}", f"- wave1 head: {w1_head}", "",
                 "## Recorded outcomes (rc 0 = success)", "",
                 "| step | rc | detail |", "|------|----|--------|"]
        for k, rc, out in log:
            detail = out.replace("|", "\\|")[:160]
            lines.append(f"| {k} | {rc} | {detail} |")
        lines += ["", "## Verdict (plan §0.0a)",
                  f"- Step-1 author+commit with Wave-1 ABSENT succeeds: {step1_authorcommit}",
                  f"- Step-1 cross-wave import FAILS while Wave-1 absent (expected/design-confirming): {import_failed_absent}",
                  f"- Step-2 integrated tree passes compileall + import-smoke: {step2_integrated}",
                  "- typecheck: N/A (no mypy/pyright in .venv; substituted by the import-smoke above)",
                  "",
                  ("PASS: workers can be write+commit-only; cross-module self-verification is "
                   "correctly deferred to per-wave assembly (Design X premise holds)."
                   if passed else
                   "FAIL: STOP for plan revision + Codex review — do NOT scope-cut to independent waves.")]
        write(REPORT, "\n".join(lines) + "\n")
        print("\n".join(lines))
        print(f"\n(report: {REPORT})")
        return 0 if passed else 1
    finally:
        # best-effort cleanup of the throwaway repo
        subprocess.run(["git", "-C", repo, "worktree", "prune"], capture_output=True)
        shutil.rmtree(repo, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
