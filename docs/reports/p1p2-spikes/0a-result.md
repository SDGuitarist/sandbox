STATUS: PASS

# Spike 0a — end-to-end two-wave falsification

- repo: /var/folders/6k/_lfrhks967zgr259jltxszjh0000gn/T/twowave-00y8dazk
- base sha: 3d25ddacbdce4298a7c48003f849e7c5d0e43cab
- wave1 head: 11a806428f19e70079e28f80f1b8afcbe6c7dfb7

## Recorded outcomes (rc 0 = success)

| step | rc | detail |
|------|----|--------|
| wave1_file_absent_in_wave2_worktree | 0 | True |
| wave2_author_commit | 0 |  create mode 100644 pkgspike/routes.py |
| wave2_compileall_routes (absent) | 0 | Compiling 'pkgspike/routes.py'... |
| wave2_import (absent, EXPECT FAIL) | 1 | ModuleNotFoundError: No module named 'pkgspike.database' |
| assembly_cherrypick_wave1 | 0 |  create mode 100644 pkgspike/database.py |
| assembly_cherrypick_wave2 | 0 |  create mode 100644 pkgspike/routes.py |
| assembly_both_files_present | 0 | True |
| integrated_compileall | 0 | Compiling 'pkgspike/routes.py'... |
| integrated_import_smoke (pytest) | 0 | 4 passed in 0.02s |

## Verdict (plan §0.0a)
- Step-1 author+commit with Wave-1 ABSENT succeeds: True
- Step-1 cross-wave import FAILS while Wave-1 absent (expected/design-confirming): True
- Step-2 integrated tree passes compileall + import-smoke: True
- typecheck: N/A (no mypy/pyright in .venv; substituted by the import-smoke above)

PASS: workers can be write+commit-only; cross-module self-verification is correctly deferred to per-wave assembly (Design X premise holds).
