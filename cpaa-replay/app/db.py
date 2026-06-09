"""Database connection layer (shadow RW + live RO).

`get_db` is the sole opener for shadow.db (read/write). `open_live_ro` is the
sole opener for live.db (immutable read-only). `row_factory = sqlite3.Row` is
set ONLY here (both openers); no other module sets it.
"""

import sqlite3
from contextlib import contextmanager

from flask import current_app


@contextmanager
def get_db(immediate: bool = False):
    """Yield a shadow.db connection with WAL + foreign_keys enforced.

    PRAGMAs are applied on every connection (per-connection, not once). When
    ``immediate`` is True, opens an explicit ``BEGIN IMMEDIATE`` transaction;
    commits on clean exit and rolls back on exception. When False, the caller
    owns any transaction.
    """
    conn = sqlite3.connect(
        current_app.config["SHADOW_DB"],
        isolation_level="",
        detect_types=0,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        if immediate:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        if immediate:
            conn.commit()
    except BaseException:
        if immediate:
            conn.rollback()
        raise
    finally:
        conn.close()


def open_live_ro(path: str) -> sqlite3.Connection:
    """Open live.db immutable read-only. Any write raises OperationalError.

    No write PRAGMA is set on this connection.
    """
    conn = sqlite3.connect(
        f"file:{path}?mode=ro&immutable=1",
        uri=True,
        isolation_level="",
        detect_types=0,
    )
    conn.row_factory = sqlite3.Row
    return conn
