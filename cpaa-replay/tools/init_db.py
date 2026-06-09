import os
import sqlite3
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"
LIVE_SCHEMA = SCHEMA_DIR / "live_schema.sql"
SHADOW_SCHEMA = SCHEMA_DIR / "shadow_schema.sql"


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required (no fallback)")
    return value


def init_live(path: str) -> None:
    schema_text = LIVE_SCHEMA.read_text(encoding="utf-8")
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(schema_text)
    finally:
        conn.close()


def init_shadow(path: str) -> None:
    schema_text = SHADOW_SCHEMA.read_text(encoding="utf-8")
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(schema_text)
    finally:
        conn.close()


def main() -> None:
    live_path = _require_env("LIVE_DB")
    shadow_path = _require_env("SHADOW_DB")
    init_live(live_path)
    init_shadow(shadow_path)


if __name__ == "__main__":
    main()
