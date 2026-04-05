import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = "flags.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"
MAX_EVAL_DEPTH = 10

# Whitelist of columns allowed in PATCH updates
_PATCHABLE_COLUMNS = frozenset(
    {"name", "description", "enabled", "default_enabled", "environments", "allowlist", "percentage"}
)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _hash_bucket(flag_key: str, user_id: str) -> int:
    """Return a stable 0-99 bucket for (flag_key, user_id).

    Uses SHA-256 — never Python's built-in hash() (salted per-process in Python 3.3+)
    and never random (non-deterministic).
    """
    digest = hashlib.sha256(f"{flag_key}:{user_id}".encode()).hexdigest()
    return int(digest, 16) % 100


@contextmanager
def get_db(path=None, immediate=False):
    db_path = path or DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        if immediate:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path=None):
    """Initialize DB schema using a raw connection.

    Does NOT use get_db() because executescript() issues an implicit COMMIT
    before running, bypassing the context manager's transaction semantics.
    """
    db_path = path or DB_PATH
    schema = SCHEMA_PATH.read_text()
    conn = sqlite3.connect(db_path)
    try:
        # WAL must be set before executescript — executescript issues an implicit
        # COMMIT which would lock out mode changes if issued after schema creation.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(schema)
    finally:
        conn.close()


def _row_to_flag(row) -> dict:
    """Convert a DB row to a flag dict, deserializing JSON fields."""
    d = dict(row)
    d["environments"] = json.loads(d["environments"]) if d["environments"] else None
    d["allowlist"] = json.loads(d["allowlist"]) if d["allowlist"] else None
    d["enabled"] = bool(d["enabled"])
    d["default_enabled"] = bool(d["default_enabled"])
    return d


# ── Flags CRUD ────────────────────────────────────────────────────────────────

def create_flag(
    key,
    name,
    description=None,
    enabled=True,
    default_enabled=False,
    environments=None,
    allowlist=None,
    percentage=None,
    db_path=None,
):
    """Create a flag. Returns flag dict. Raises sqlite3.IntegrityError on duplicate key."""
    now = _now()
    env_json = json.dumps(environments) if environments is not None else None
    allow_json = json.dumps(allowlist) if allowlist is not None else None

    with get_db(path=db_path) as conn:
        conn.execute(
            """INSERT INTO flags
               (key, name, description, enabled, default_enabled, environments, allowlist,
                percentage, eval_count, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            (key, name, description, int(enabled), int(default_enabled),
             env_json, allow_json, percentage, now, now),
        )
        row = conn.execute("SELECT * FROM flags WHERE key = ?", (key,)).fetchone()
        return _row_to_flag(row)


def get_flag(key, db_path=None):
    """Return flag dict or None."""
    with get_db(path=db_path) as conn:
        row = conn.execute("SELECT * FROM flags WHERE key = ?", (key,)).fetchone()
        return _row_to_flag(row) if row else None


def list_flags(db_path=None):
    with get_db(path=db_path) as conn:
        rows = conn.execute("SELECT * FROM flags ORDER BY key ASC").fetchall()
        return [_row_to_flag(r) for r in rows]


def update_flag(key, updates: dict, db_path=None):
    """Partially update a flag. Only keys in _PATCHABLE_COLUMNS are applied.

    Serializes environments/allowlist to JSON. Returns updated flag dict or None if not found.
    """
    allowed = {k: v for k, v in updates.items() if k in _PATCHABLE_COLUMNS}
    if not allowed:
        return get_flag(key, db_path=db_path)

    # Serialize JSON fields
    if "environments" in allowed:
        allowed["environments"] = json.dumps(allowed["environments"]) if allowed["environments"] is not None else None
    if "allowlist" in allowed:
        allowed["allowlist"] = json.dumps(allowed["allowlist"]) if allowed["allowlist"] is not None else None
    if "enabled" in allowed:
        allowed["enabled"] = int(allowed["enabled"])
    if "default_enabled" in allowed:
        allowed["default_enabled"] = int(allowed["default_enabled"])

    allowed["updated_at"] = _now()

    # Column names are double-quoted for safety against reserved words.
    # They come exclusively from _PATCHABLE_COLUMNS so there is no injection risk.
    set_clause = ", ".join(f'"{col}" = ?' for col in allowed)
    values = list(allowed.values()) + [key]

    with get_db(path=db_path) as conn:
        cursor = conn.execute(
            f"UPDATE flags SET {set_clause} WHERE key = ?", values
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM flags WHERE key = ?", (key,)).fetchone()
        return _row_to_flag(row)


def delete_flag(key, db_path=None):
    """Delete a flag and its dependencies (CASCADE). Returns True if deleted."""
    with get_db(path=db_path) as conn:
        cursor = conn.execute("DELETE FROM flags WHERE key = ?", (key,))
        return cursor.rowcount > 0


# ── Dependencies ──────────────────────────────────────────────────────────────

def _detect_cycle(flag_key: str, new_dep_key: str, conn) -> bool:
    """Return True if adding edge flag_key → new_dep_key would create a cycle.

    DFS walks from new_dep_key following existing dependencies.
    If we reach flag_key, the new edge would close a cycle.
    """
    visited = set()
    stack = [new_dep_key]
    while stack:
        node = stack.pop()
        if node == flag_key:
            return True
        if node in visited:
            continue
        visited.add(node)
        deps = conn.execute(
            "SELECT depends_on_key FROM flag_dependencies WHERE flag_key = ?", (node,)
        ).fetchall()
        for dep in deps:
            stack.append(dep["depends_on_key"])
    return False


def add_dependency(flag_key, depends_on_key, db_path=None):
    """Add a dependency edge flag_key → depends_on_key.

    Raises ValueError if this would create a cycle.
    Raises sqlite3.IntegrityError if the dependency already exists or a flag doesn't exist.
    Returns True on success.
    """
    if flag_key == depends_on_key:
        raise ValueError(f"Flag '{flag_key}' cannot depend on itself")

    with get_db(path=db_path, immediate=True) as conn:
        if _detect_cycle(flag_key, depends_on_key, conn):
            raise ValueError(
                f"Adding dependency '{flag_key}' → '{depends_on_key}' would create a cycle"
            )
        conn.execute(
            "INSERT INTO flag_dependencies (flag_key, depends_on_key) VALUES (?, ?)",
            (flag_key, depends_on_key),
        )
    return True


def remove_dependency(flag_key, depends_on_key, db_path=None):
    """Remove a dependency edge. Returns True if removed, False if not found."""
    with get_db(path=db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM flag_dependencies WHERE flag_key = ? AND depends_on_key = ?",
            (flag_key, depends_on_key),
        )
        return cursor.rowcount > 0


def get_dependencies(flag_key, db_path=None):
    """Return list of flag keys that flag_key depends on."""
    with get_db(path=db_path) as conn:
        rows = conn.execute(
            "SELECT depends_on_key FROM flag_dependencies WHERE flag_key = ?", (flag_key,)
        ).fetchall()
        return [r["depends_on_key"] for r in rows]


# ── Evaluation ────────────────────────────────────────────────────────────────

def evaluate_flag(flag_key, user_id, environment=None, db_path=None, _depth=0):
    """Evaluate a flag for a given user/context.

    Returns dict: {enabled: bool, reason: str, flag_key: str}

    Evaluation priority:
    1. disabled (global kill switch)
    2. environment_mismatch
    3. dependency_disabled (recursive evaluation)
    4. allowlist
    5. percentage
    6. default

    Increments eval_count atomically via SQL UPDATE.
    Depth limit: MAX_EVAL_DEPTH to prevent infinite recursion on cycles.
    """
    if _depth >= MAX_EVAL_DEPTH:
        return {"enabled": False, "reason": "max_depth_exceeded", "flag_key": flag_key}

    with get_db(path=db_path, immediate=True) as conn:
        row = conn.execute("SELECT * FROM flags WHERE key = ?", (flag_key,)).fetchone()
        if row is None:
            return {"enabled": False, "reason": "not_found", "flag_key": flag_key}

        flag = _row_to_flag(row)

        # Atomically increment eval_count and capture the new value in one round-trip
        new_count = conn.execute(
            "UPDATE flags SET eval_count = eval_count + 1 WHERE key = ? RETURNING eval_count",
            (flag_key,)
        ).fetchone()
        eval_count = new_count["eval_count"] if new_count else None

        # 1. Global kill switch
        if not flag["enabled"]:
            result = {"enabled": False, "reason": "disabled", "flag_key": flag_key}
            if _depth == 0:
                result["eval_count"] = eval_count
            return result

        # 2. Allowlist — checked BEFORE environment so explicitly allowlisted users
        #    receive the feature regardless of which environment they are in.
        if flag["allowlist"] is not None and user_id in flag["allowlist"]:
            result = {"enabled": True, "reason": "allowlist", "flag_key": flag_key}
            if _depth == 0:
                result["eval_count"] = eval_count
            return result

        # 3. Environment targeting (checked after allowlist)
        if flag["environments"] is not None:
            if environment is None or environment not in flag["environments"]:
                result = {"enabled": False, "reason": "environment_mismatch", "flag_key": flag_key}
                if _depth == 0:
                    result["eval_count"] = eval_count
                return result

        # 4. Dependencies — fetch inside same transaction for consistency.
        # NOTE: dependency *evaluation* happens outside this transaction (each recursive
        # call opens its own BEGIN IMMEDIATE). This means a chain evaluation observes
        # multiple DB snapshots — a concurrent writer could flip a dependency flag between
        # recursive calls. Acceptable for this use case; strict snapshot would require
        # loading all flags first and evaluating in memory.
        dep_rows = conn.execute(
            "SELECT depends_on_key FROM flag_dependencies WHERE flag_key = ?", (flag_key,)
        ).fetchall()
        dep_keys = [r["depends_on_key"] for r in dep_rows]

    for dep_key in dep_keys:
        dep_result = evaluate_flag(dep_key, user_id, environment, db_path=db_path, _depth=_depth + 1)
        if not dep_result["enabled"]:
            result = {
                "enabled": False,
                "reason": "dependency_disabled",
                "flag_key": flag_key,
                "dependency": dep_key,
            }
            if _depth == 0:
                result["eval_count"] = eval_count
            return result

    # 5. Percentage rollout
    if flag["percentage"] is not None:
        bucket = _hash_bucket(flag_key, user_id)
        if bucket < flag["percentage"]:
            result = {"enabled": True, "reason": "percentage", "flag_key": flag_key}
        else:
            result = {"enabled": False, "reason": "percentage", "flag_key": flag_key}
        if _depth == 0:
            result["eval_count"] = eval_count
        return result

    # 6. Default
    result = {"enabled": flag["default_enabled"], "reason": "default", "flag_key": flag_key}
    if _depth == 0:
        result["eval_count"] = eval_count
    return result
