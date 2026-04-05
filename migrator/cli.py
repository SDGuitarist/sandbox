"""CLI for the migration runner.

Usage:
    python -m migrator.cli up [--dry-run] [--target VERSION] [--db PATH] [--dir PATH]
    python -m migrator.cli down [--steps N] [--dry-run] [--db PATH] [--dir PATH]
    python -m migrator.cli status [--db PATH] [--dir PATH]

Exit codes:
    0 — success
    1 — error (file error, checksum mismatch, no down SQL, etc.)
    2 — lock contention
"""
import argparse
import json
import os
import sys

from .db import ChecksumMismatchError, MigrationLockError
from .files import MigrationFileError
from .runner import migrate_down, migrate_up, migration_status


def _get_db(args):
    return args.db or os.environ.get("MIGRATIONS_DB", "migrator.db")


def _get_dir(args):
    d = args.dir or os.environ.get("MIGRATIONS_DIR", "migrations")
    return d


def cmd_up(args):
    try:
        result = migrate_up(
            _get_db(args), _get_dir(args),
            dry_run=args.dry_run,
            target=args.target,
            locked_by=f"cli:pid={os.getpid()}",
        )
        if args.dry_run:
            print("[dry-run] Migrations that would be applied:")
        if result["applied"]:
            for v in result["applied"]:
                stmts = result["sql"].get(v, [])
                print(f"  {v}: {len(stmts)} statement(s)")
                if args.verbose:
                    for stmt in stmts:
                        print(f"    {stmt}")
        else:
            print("  No pending migrations.")
        return 0
    except MigrationLockError as e:
        print(f"[lock] {e}", file=sys.stderr)
        return 2
    except (ChecksumMismatchError, MigrationFileError, ValueError) as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1


def cmd_down(args):
    if args.steps < 1:
        print("[error] --steps must be >= 1", file=sys.stderr)
        return 1
    try:
        result = migrate_down(
            _get_db(args), _get_dir(args),
            steps=args.steps,
            dry_run=args.dry_run,
            locked_by=f"cli:pid={os.getpid()}",
        )
        if args.dry_run:
            print("[dry-run] Migrations that would be rolled back:")
        if result["rolled_back"]:
            for v in result["rolled_back"]:
                stmts = result["sql"].get(v, [])
                print(f"  {v}: {len(stmts)} statement(s)")
                if args.verbose:
                    for stmt in stmts:
                        print(f"    {stmt}")
        else:
            print("  No migrations to roll back.")
        return 0
    except MigrationLockError as e:
        print(f"[lock] {e}", file=sys.stderr)
        return 2
    except (ChecksumMismatchError, MigrationFileError, ValueError) as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1


def cmd_status(args):
    try:
        result = migration_status(_get_db(args), _get_dir(args))
        print(f"Applied ({len(result['applied'])}):")
        for m in result["applied"]:
            print(f"  [x] {m['version']} {m['name']} — {m['applied_at']}")
        print(f"Pending ({len(result['pending'])}):")
        for m in result["pending"]:
            print(f"  [ ] {m['version']} {m['name']}")
        if result["missing"]:
            print(f"Missing files ({len(result['missing'])}):")
            for m in result["missing"]:
                print(f"  [!] {m['version']} {m['name']} — file not found")
        return 0
    except (MigrationFileError, ValueError) as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(description="Database migration runner")
    parser.add_argument("--db", help="SQLite DB path (default: $MIGRATIONS_DB or migrator.db)")
    parser.add_argument("--dir", help="Migrations directory (default: $MIGRATIONS_DIR or migrations)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show SQL statements")

    sub = parser.add_subparsers(dest="command", required=True)

    up_p = sub.add_parser("up", help="Apply pending migrations")
    up_p.add_argument("--dry-run", action="store_true", help="Show SQL without applying")
    up_p.add_argument("--target", metavar="VERSION", help="Stop after this version (e.g. 0003)")

    down_p = sub.add_parser("down", help="Roll back applied migrations")
    down_p.add_argument("--steps", type=int, default=1, metavar="N", help="Number of migrations to roll back")
    down_p.add_argument("--dry-run", action="store_true", help="Show SQL without rolling back")

    sub.add_parser("status", help="Show migration status")

    args = parser.parse_args()

    if args.command == "up":
        sys.exit(cmd_up(args))
    elif args.command == "down":
        sys.exit(cmd_down(args))
    elif args.command == "status":
        sys.exit(cmd_status(args))


if __name__ == "__main__":
    main()
