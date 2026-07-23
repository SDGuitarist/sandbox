#!/usr/bin/env python3
"""Spike 0a — falsify the spec-only premise with a genuine END-TO-END two-wave
spike, AND prove the integrated gate boots create_app() + exercises the
app-context/teardown lifecycle seam (not merely import resolution).

Plan: docs/plans/2026-07-22-p1p2-unattended-swarm-wave-barrier-plan.md  §0.0a

Why this shape (rev5, Codex Finding 1). The prior 0a proved only the narrow
import-resolution premise on two trivial modules. But the §3.4 gate is specified
to BOOT create_app() and exercise app-context/teardown, and Run 083's real
integration failures were lifecycle seams — init_db() called without an app
context (H6/FC39), an unregistered teardown_appcontext (H3/FC3). A bare
import-smoke does NOT catch those. So this spike now builds a minimal Flask app:

  pkgspike/database.py  (Wave 1) — get_db()/query()/init_db()/close_db(), all of
      which touch flask.g / current_app and therefore REQUIRE an app context.
  pkgspike/factory.py   (Wave 2) — create_app() that imports Wave-1 symbols,
      registers a blueprint, calls init_db(), and registers teardown_appcontext.
  pkgspike/routes.py    (Wave 2) — a blueprint importing query (keeps the
      original cross-wave import-resolution premise).

The Wave-2 worker authors a create_app() that calls init_db() BARE (no app
context) — realistic, because with Wave 1 ABSENT it can never boot the app to
discover the bug (Design X: workers are write+commit-only). At assembly the
integrated gate BOOTS create_app(): the broken tree FAILS with "Working outside
of application context" (the H6/H3 class), then swarm-runner's one inline
assembly-fix (`with app.app_context(): init_db()`) makes the gate PASS. This is
exactly the Run 083 H6 sequence.

PASS (ALL four):
  1. Wave-2 author+commit succeeds with Wave-1 ABSENT (write from export NAMES).
  2. Wave-2 cross-wave import FAILS at author time (design-confirming — deferral
     of self-verification to assembly is correct).
  3. The integrated gate on the BROKEN assembly FAILS by BOOTING create_app()
     and hitting the app-context/teardown seam (proves the gate catches the
     lifecycle class, not just imports).
  4. The integrated gate on the FIXED assembly (assembly-fix applied) PASSES.
FAIL (any of): author+commit needs the prior file present, OR the integrated
gate cannot be made to pass, OR the gate does NOT catch the lifecycle break
(broken tree passes) -> STOP for plan revision (do NOT scope-cut).

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

# --- File bodies -----------------------------------------------------------

DATABASE_PY = '''\
"""Wave-1 module. Every accessor REQUIRES a Flask app context (touches g /
current_app) — mirroring a real request-scoped DB handle (Run 083 H6/H3)."""
from flask import current_app, g


def get_db():
    if "db" not in g:               # accessing g outside an app context raises
        g.db = {"rows": []}
        current_app.config.setdefault("DB_READY", True)
    return g.db


def query():
    return get_db()["rows"]


def init_db():
    # Must run INSIDE an app context. Called bare -> "Working outside of
    # application context" (the H6 / FC39 lifecycle seam).
    db = get_db()
    db.setdefault("rows", [])


def close_db(exc=None):
    g.pop("db", None)
'''

ROUTES_PY = '''\
"""Wave-2 module — keeps the original cross-wave import-resolution premise:
it writes `from pkgspike.database import query` from the spec's export NAMES
while the Wave-1 file is ABSENT at author time."""
from flask import Blueprint
from pkgspike.database import query

bp = Blueprint("rows", __name__)


@bp.route("/rows")
def list_rows():
    return {"rows": query()}
'''

# Wave-2 authors this BROKEN factory: init_db() is called BARE (no app context).
# With Wave 1 absent the worker cannot boot it, so it cannot discover the bug.
FACTORY_BROKEN_PY = '''\
"""Wave-2 app factory (as authored by the worker, Wave-1 ABSENT)."""
from flask import Flask
from pkgspike.database import init_db, close_db
from pkgspike.routes import bp


def create_app():
    app = Flask(__name__)
    app.register_blueprint(bp)
    init_db()                       # BUG (H6): bare call, no app context
    app.teardown_appcontext(close_db)
    return app
'''

# The assembly-fix swarm-runner would apply on the first integrated-gate failure.
FACTORY_FIXED_PY = '''\
"""Wave-2 app factory (assembly-fixed): init_db() runs inside an app context."""
from flask import Flask
from pkgspike.database import init_db, close_db
from pkgspike.routes import bp


def create_app():
    app = Flask(__name__)
    app.register_blueprint(bp)
    with app.app_context():         # assembly-fix (H6): app context around init
        init_db()
    app.teardown_appcontext(close_db)
    return app
'''

SPEC_MD = (
    "# Export Names\n"
    "| Name | Type | Defined By | Used By |\n"
    "|------|------|-----------|---------|\n"
    "| pkgspike.database.query | function | database (Wave 1) | routes (Wave 2) |\n"
    "| pkgspike.database.init_db | function | database (Wave 1) | factory (Wave 2) |\n"
    "| pkgspike.database.close_db | function | database (Wave 1) | factory (Wave 2) |\n"
    "| pkgspike.routes.bp | blueprint | routes (Wave 2) | factory (Wave 2) |\n"
    "| pkgspike.factory.create_app | function | factory (Wave 2) | gate (assembly) |\n"
)


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


def gate(tree, extra_env=None):
    """Run the pinned integrated gate on an assembled tree: compileall + the
    pytest import-smoke that BOOTS create_app()."""
    rc_c, out_c = run([VENV_PY, "-m", "compileall", "pkgspike"], tree)
    rc_s, out_s = run(
        [VENV_PYTEST, IMPORTSMOKE, "-q", "-p", "no:cacheprovider"],
        SANDBOX, extra_env=dict(extra_env or {}, PKGSPIKE_ROOT=tree))
    return (rc_c, out_c.splitlines()[-1] if out_c else ""), \
           (rc_s, out_s.strip())


def main():
    repo = tempfile.mkdtemp(prefix="twowave-")
    log = []

    def note(k, rc, out=""):
        log.append((k, rc, out))

    try:
        # --- Fixture: main carries ONLY spec + empty pkgspike (Wave-1 ABSENT) ---
        git(["init", "-b", "main"], repo)
        write(os.path.join(repo, "pkgspike/__init__.py"), "")
        write(os.path.join(repo, "SPEC.md"), SPEC_MD)
        git(["add", "-A"], repo)
        git(["commit", "-m", "base: spec + empty pkgspike"], repo)
        rc, base = git(["rev-parse", "HEAD"], repo)
        git(["branch", "feat-spike", "main"], repo)

        # --- Wave-1 worker (database): app-context-requiring DB module ---
        wt_w1 = os.path.join(repo, ".wt/w1")
        git(["worktree", "add", "-b", "w1-database", wt_w1, "main"], repo)
        write(os.path.join(wt_w1, "pkgspike/database.py"), DATABASE_PY)
        git(["add", "-A"], wt_w1)
        git(["commit", "-m", "wave1: database (app-context DB module)"], wt_w1)
        rc, w1_head = git(["rev-parse", "HEAD"], wt_w1)

        # --- Wave-2 worker (app): rooted on main, database.py ABSENT here ---
        wt_w2 = os.path.join(repo, ".wt/w2")
        git(["worktree", "add", "-b", "w2-app", wt_w2, "main"], repo)
        w1_absent = not os.path.exists(os.path.join(wt_w2, "pkgspike/database.py"))
        note("wave1_file_absent_in_wave2_worktree", 0 if w1_absent else 1,
             str(w1_absent))
        # Author against the SPEC's export NAMES (no execution).
        write(os.path.join(wt_w2, "pkgspike/routes.py"), ROUTES_PY)
        write(os.path.join(wt_w2, "pkgspike/factory.py"), FACTORY_BROKEN_PY)
        git(["add", "-A"], wt_w2)
        rc_commit, commit_out = git(["commit", "-m", "wave2: factory + routes"], wt_w2)
        note("wave2_author_commit", rc_commit,
             commit_out.splitlines()[-1] if commit_out else "")

        # Step-1 self-verification attempts IN the Wave-2 worktree (Wave-1 absent):
        rc_c, out_c = run([VENV_PY, "-m", "compileall", "pkgspike/factory.py"], wt_w2)
        note("wave2_compileall_factory (absent)", rc_c,
             out_c.splitlines()[-1] if out_c else "")
        rc_i, out_i = run([VENV_PY, "-c", "import pkgspike.factory"], wt_w2)
        note("wave2_import_factory (absent, EXPECT FAIL)", rc_i,
             (out_i.splitlines()[-1] if out_i else ""))

        # --- Assembly: cherry-pick Wave-1 then Wave-2 onto an assembly branch ---
        wt_asm = os.path.join(repo, ".wt/asm")
        git(["worktree", "add", "-b", "asm", wt_asm, "feat-spike"], repo)
        rc, mb1 = git(["merge-base", "feat-spike", "w1-database"], repo)
        rc, mb2 = git(["merge-base", "feat-spike", "w2-app"], repo)
        rc_cp1, out_cp1 = git(["cherry-pick", f"{mb1}..w1-database"], wt_asm)
        note("assembly_cherrypick_wave1", rc_cp1, out_cp1.splitlines()[-1] if out_cp1 else "")
        rc_cp2, out_cp2 = git(["cherry-pick", f"{mb2}..w2-app"], wt_asm)
        note("assembly_cherrypick_wave2", rc_cp2, out_cp2.splitlines()[-1] if out_cp2 else "")
        both_present = (os.path.exists(os.path.join(wt_asm, "pkgspike/database.py"))
                        and os.path.exists(os.path.join(wt_asm, "pkgspike/factory.py")))
        note("assembly_both_files_present", 0 if both_present else 1, str(both_present))

        # --- Integrated gate #1: BROKEN tree (as assembled) -> EXPECT FAIL ---
        (rc_bc, det_bc), (rc_bs, out_bs) = gate(wt_asm)
        note("broken_integrated_compileall", rc_bc, det_bc)
        # Faithfulness: match pytest's own error-marker line (stripped-leading "E"),
        # NOT the docstring echo — so "caught the lifecycle seam" cannot
        # false-positive on prose that merely mentions the phrase.
        boot_line = next(
            (ln.strip() for ln in out_bs.splitlines()
             if ln.lstrip().startswith("E")
             and "Working outside of application context" in ln), "")
        summary_line = out_bs.splitlines()[-1] if out_bs else ""
        note("broken_integrated_gate (boots create_app, EXPECT FAIL)", rc_bs,
             (boot_line or summary_line)[:200])

        # --- Assembly-fix: wrap init_db() in an app context (the H6 fix) ---
        write(os.path.join(wt_asm, "pkgspike/factory.py"), FACTORY_FIXED_PY)
        git(["add", "-A"], wt_asm)
        git(["commit", "-m", "assembly-fix: init_db inside app context (H6)"], wt_asm)

        # --- Integrated gate #2: FIXED tree -> EXPECT PASS ---
        (rc_fc, det_fc), (rc_fs, out_fs) = gate(wt_asm)
        note("fixed_integrated_compileall", rc_fc, det_fc)
        note("fixed_integrated_gate (boots create_app, EXPECT PASS)", rc_fs,
             out_fs.splitlines()[-1] if out_fs else "")

        # --- Verdict per plan §0.0a ---
        def ok(key):
            return any(k == key and rc == 0 for k, rc, _ in log)

        def failed(prefix):
            return any(k.startswith(prefix) and rc != 0 for k, rc, _ in log)

        step1_authorcommit = ok("wave2_author_commit")
        step1_import_fails = failed("wave2_import_factory")
        broken_gate_fails = failed("broken_integrated_gate")
        broken_caught_lifecycle = bool(boot_line)  # the app-context error was the cause
        fixed_gate_passes = ok("fixed_integrated_gate (boots create_app, EXPECT PASS)")

        passed = (step1_authorcommit and step1_import_fails and broken_gate_fails
                  and broken_caught_lifecycle and fixed_gate_passes)
        status = "PASS" if passed else "FAIL"

        lines = [f"STATUS: {status}", "",
                 "# Spike 0a — end-to-end two-wave falsification + lifecycle-gate proof", "",
                 f"- repo: {repo}", f"- base sha: {base}", f"- wave1 head: {w1_head}", "",
                 "## Recorded outcomes (rc 0 = success)", "",
                 "| step | rc | detail |", "|------|----|--------|"]
        for k, rc, out in log:
            detail = out.replace("|", "\\|")[:180]
            lines.append(f"| {k} | {rc} | {detail} |")
        lines += ["", "## Verdict (plan §0.0a, rev5)",
                  f"- (1) Wave-2 author+commit with Wave-1 ABSENT succeeds: {step1_authorcommit}",
                  f"- (2) Wave-2 cross-wave import FAILS at author time (design-confirming): {step1_import_fails}",
                  f"- (3) Integrated gate BOOTS create_app() on the BROKEN tree and FAILS on the "
                  f"app-context/teardown seam (H6/H3 class — not just imports): {broken_gate_fails and broken_caught_lifecycle}",
                  f"- (4) Integrated gate on the assembly-FIXED tree PASSES: {fixed_gate_passes}",
                  "- typecheck: N/A — no static type-checker is configured in .venv (no mypy/pyright). "
                  "The gate is an integrated IMPORT-SMOKE (import-time cross-module name resolution + "
                  "create_app() boot), NOT static type checking. Recorded explicitly; no gate is silently skipped.",
                  "",
                  ("PASS: workers can be write+commit-only (import-resolution premise holds), AND the "
                   "integrated assembly gate catches BOTH the import class and the app-context/teardown "
                   "lifecycle class (H3/H6/H9) by booting create_app() — a bare import-smoke would not. "
                   "The precise claim proven is scoped to these two facts, not a blanket 'Design X holds'."
                   if passed else
                   "FAIL: STOP for plan revision + Codex review — do NOT scope-cut to independent waves. "
                   "Either write+commit-only authoring is unsound, or the integrated gate did not catch "
                   "the lifecycle break, or the assembly-fixed tree could not pass.")]
        write(REPORT, "\n".join(lines) + "\n")
        print("\n".join(lines))
        print(f"\n(report: {REPORT})")
        return 0 if passed else 1
    finally:
        subprocess.run(["git", "-C", repo, "worktree", "prune"], capture_output=True)
        shutil.rmtree(repo, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
