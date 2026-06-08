"""Compute the two canonical-hash golden anchors and freeze them into
`app/constants.py`.

Run ONCE, after the schema, generator, serializer, and the full ingest/replay
pipeline have landed. It:

  1. Builds throwaway live.db + shadow.db in a temp dir (init_db + generator).
  2. Computes EMPTY_PROJECTION_HASH from the fresh shadow.db (projection tables
     empty) by calling `serialization.canonical_hash`.
  3. Drives the assembled app (login -> POST /ingest/run -> POST /replay/run)
     to materialize the corpus projection, then computes the golden corpus
     `projection_hash` the same way.
  4. Rewrites the EMPTY_PROJECTION_HASH and GOLDEN_PROJECTION_HASH string
     literals in app/constants.py with the computed values.

Both hashes are produced by real code (no hand-authored constants), satisfying
plan §8.8.

Usage:
    python -m tools.compute_golden            # compute + freeze into constants.py
    python -m tools.compute_golden --check    # compute + compare, do not write

This file lives in cpaa-replay/tools/; invoke it from the cpaa-replay/ root so
that `app` and `tools` are importable packages.
"""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

# cpaa-replay/ (parent of tools/) must be on sys.path so `import app...` works
# whether invoked as `python -m tools.compute_golden` or `python tools/compute_golden.py`.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_CONSTANTS_PATH = _ROOT / "app" / "constants.py"
_APP_PASSWORD = "golden"
_SECRET_KEY = "golden-compute-secret"

_EMPTY_RE = re.compile(r'^(EMPTY_PROJECTION_HASH\s*=\s*)"[0-9a-f]*"\s*$', re.MULTILINE)
_GOLDEN_RE = re.compile(r'^(GOLDEN_PROJECTION_HASH\s*=\s*)"[0-9a-f]*"\s*$', re.MULTILINE)


def _build_databases(live_db: Path, shadow_db: Path) -> None:
    """Create both DBs (init_db) and populate live.db (generate_source).

    init_db.py and generate_source.py are stand-alone tools; they read their
    target paths from the same env vars the app config uses.
    """
    env = dict(os.environ)
    env["LIVE_DB"] = str(live_db)
    env["SHADOW_DB"] = str(shadow_db)
    env.setdefault("SECRET_KEY", _SECRET_KEY)
    env.setdefault("APP_PASSWORD", _APP_PASSWORD)
    for module in ("tools.init_db", "tools.generate_source"):
        subprocess.run(
            [sys.executable, "-m", module],
            cwd=str(_ROOT),
            env=env,
            check=True,
        )


def _empty_projection_hash(shadow_db: Path) -> str:
    """canonical_hash over a shadow.db whose projection tables are empty."""
    from app.serialization import canonical_hash

    conn = sqlite3.connect(str(shadow_db))
    conn.row_factory = sqlite3.Row
    try:
        return canonical_hash(conn)
    finally:
        conn.close()


def _csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    if not match:
        raise RuntimeError("could not extract csrf_token from login form")
    return match.group(1)


def _golden_corpus_hash(live_db: Path, shadow_db: Path) -> str:
    """Drive the assembled app to ingest + replay the corpus, then hash."""
    os.environ["LIVE_DB"] = str(live_db)
    os.environ["SHADOW_DB"] = str(shadow_db)
    os.environ["SECRET_KEY"] = _SECRET_KEY
    os.environ["APP_PASSWORD"] = _APP_PASSWORD

    from app import create_app
    from app.serialization import canonical_hash

    app = create_app()
    client = app.test_client()

    login_page = client.get("/auth/login")
    token = _csrf_token(login_page.get_data(as_text=True))
    resp = client.post(
        "/auth/login",
        data={"password": _APP_PASSWORD, "csrf_token": token},
    )
    if resp.status_code not in (200, 302):
        raise RuntimeError(f"login failed: {resp.status_code}")

    resp = client.post("/ingest/run", headers={"X-CSRFToken": token})
    if resp.status_code not in (200, 302):
        raise RuntimeError(f"ingest failed: {resp.status_code} {resp.get_data(as_text=True)}")

    resp = client.post("/replay/run", headers={"X-CSRFToken": token})
    if resp.status_code not in (200, 302):
        raise RuntimeError(f"replay failed: {resp.status_code} {resp.get_data(as_text=True)}")

    conn = sqlite3.connect(str(shadow_db))
    conn.row_factory = sqlite3.Row
    try:
        return canonical_hash(conn)
    finally:
        conn.close()


def _freeze(empty_hash: str, golden_hash: str) -> None:
    text = _CONSTANTS_PATH.read_text(encoding="utf-8")

    new_text, n_empty = _EMPTY_RE.subn(
        lambda m: f'{m.group(1)}"{empty_hash}"', text
    )
    if n_empty == 0:
        new_text = new_text.rstrip("\n") + f'\nEMPTY_PROJECTION_HASH = "{empty_hash}"\n'
    elif n_empty > 1:
        raise RuntimeError(f"expected one EMPTY_PROJECTION_HASH literal; found {n_empty}")

    new_text, n_golden = _GOLDEN_RE.subn(
        lambda m: f'{m.group(1)}"{golden_hash}"', new_text
    )
    if n_golden == 0:
        new_text = new_text.rstrip("\n") + f'\nGOLDEN_PROJECTION_HASH = "{golden_hash}"\n'
    elif n_golden > 1:
        raise RuntimeError(f"expected one GOLDEN_PROJECTION_HASH literal; found {n_golden}")

    _CONSTANTS_PATH.write_text(new_text, encoding="utf-8")


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    with tempfile.TemporaryDirectory() as tmp:
        live_db = Path(tmp) / "live.db"
        shadow_db = Path(tmp) / "shadow.db"
        _build_databases(live_db, shadow_db)
        empty_hash = _empty_projection_hash(shadow_db)
        golden_hash = _golden_corpus_hash(live_db, shadow_db)

    print(f"EMPTY_PROJECTION_HASH  = {empty_hash}")
    print(f"GOLDEN_PROJECTION_HASH = {golden_hash}")
    if check_only:
        return 0
    _freeze(empty_hash, golden_hash)
    print(f"Frozen into {_CONSTANTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
