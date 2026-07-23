STATUS: PASS

# Spike 0a — end-to-end two-wave falsification + lifecycle-gate proof

- repo: /var/folders/6k/_lfrhks967zgr259jltxszjh0000gn/T/twowave-g_e9st5y
- base sha: 8c818fd1b5388aa12b54ae3d8487ba856ac7420a
- wave1 head: 4ee5c3ae8110d205b3a1470e26c84b89156e66b2

## Recorded outcomes (rc 0 = success)

| step | rc | detail |
|------|----|--------|
| wave1_file_absent_in_wave2_worktree | 0 | True |
| wave2_author_commit | 0 |  create mode 100644 pkgspike/routes.py |
| wave2_compileall_factory (absent) | 0 | Compiling 'pkgspike/factory.py'... |
| wave2_import_factory (absent, EXPECT FAIL) | 1 | ModuleNotFoundError: No module named 'pkgspike.database' |
| assembly_cherrypick_wave1 | 0 |  create mode 100644 pkgspike/database.py |
| assembly_cherrypick_wave2 | 0 |  create mode 100644 pkgspike/routes.py |
| assembly_both_files_present | 0 | True |
| broken_integrated_compileall | 0 | Compiling 'pkgspike/routes.py'... |
| broken_integrated_gate (boots create_app, EXPECT FAIL) | 1 | E           RuntimeError: Working outside of application context. |
| fixed_integrated_compileall | 0 | Listing 'pkgspike'... |
| fixed_integrated_gate (boots create_app, EXPECT PASS) | 0 | 6 passed in 0.04s |

## Verdict (plan §0.0a, rev5)
- (1) Wave-2 author+commit with Wave-1 ABSENT succeeds: True
- (2) Wave-2 cross-wave import FAILS at author time (design-confirming): True
- (3) Integrated gate BOOTS create_app() on the BROKEN tree and FAILS on the app-context/teardown seam (H6/H3 class — not just imports): True
- (4) Integrated gate on the assembly-FIXED tree PASSES: True
- typecheck: N/A — no static type-checker is configured in .venv (no mypy/pyright). The gate is an integrated IMPORT-SMOKE (import-time cross-module name resolution + create_app() boot), NOT static type checking. Recorded explicitly; no gate is silently skipped.

PASS: workers can be write+commit-only (import-resolution premise holds), AND the integrated assembly gate catches BOTH the import class and the app-context/teardown lifecycle class (H3/H6/H9) by booting create_app() — a bare import-smoke would not. The precise claim proven is scoped to these two facts, not a blanket 'Design X holds'.
