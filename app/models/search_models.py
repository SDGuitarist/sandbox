"""Full-text search model functions backed by an FTS5 virtual table.

The ``search_index`` table (declared by the database agent in schema.sql) is a
*contentless* FTS5 table::

    CREATE VIRTUAL TABLE search_index USING fts5(
        entity_type UNINDEXED, entity_id UNINDEXED, title, body,
        content='', contentless_delete=1
    );

Because ``content=''`` is set, FTS5 stores **only the inverted index** -- none of
the column values (not even the ``UNINDEXED`` ones) can be read back with a
``SELECT``. A matching row therefore yields nothing but its ``rowid`` and a
relevance ``rank``. To recover which entity a match belongs to we encode the
entity identity *into* the rowid (:func:`_encode_rowid` / :func:`_decode_rowid`)
and re-read the display ``title``/``snippet`` from the owning source table.

This module is the **single writer** for the FTS5 index. The scenes, cast, crew
and locations route agents call :func:`index_entity` and :func:`remove_entity`
explicitly -- there are deliberately no FTS sync triggers (single-writer = explicit
calls only). Keep the public signatures of those two functions exactly as
declared in the spec; four other agents depend on them.
"""

import re

# Stable mapping between an entity type and the high-order portion of its FTS
# rowid. These codes are part of the on-disk contract: changing a value would
# orphan every previously indexed row, so they must never be reassigned.
_ENTITY_TYPE_CODES = {
    "scene": 1,
    "cast": 2,
    "crew": 3,
    "location": 4,
}
_CODE_TO_ENTITY_TYPE = {code: name for name, code in _ENTITY_TYPE_CODES.items()}

# entity_id occupies the low-order digits; the type code occupies everything
# above it. 100M ids per type is far beyond any realistic project size.
_ROWID_MULTIPLIER = 100_000_000

# Source-table metadata used to rebuild the display title and snippet for a
# match. Each entry is (table, title_column, snippet_column). The snippet column
# is the secondary text shown under the title in the results list.
_ENTITY_SOURCES = {
    "scene": ("scenes", "scene_number", "description"),
    "cast": ("cast_members", "name", "character_name"),
    "crew": ("crew_members", "name", "role_title"),
    "location": ("locations", "name", "address"),
}

# Human-readable label for each entity type, surfaced in the results template.
ENTITY_TYPE_LABELS = {
    "scene": "Scene",
    "cast": "Cast",
    "crew": "Crew",
    "location": "Location",
}

# FTS5 query syntax characters. If any of these reach the MATCH expression
# unescaped they are interpreted as operators (phrase, prefix, column filter,
# NEAR, boolean grouping) rather than literal search text -- and malformed
# combinations raise OperationalError, surfacing as a 500. Parameter binding
# does NOT neutralise them, so they must be stripped before the query is built.
_FTS5_SPECIAL_CHARS = re.compile(r'[*"():^{}\[\]~+\-]')
_WHITESPACE = re.compile(r"\s+")


def _encode_rowid(entity_type, entity_id):
    """Pack an (entity_type, entity_id) pair into a single FTS rowid."""
    return _ENTITY_TYPE_CODES[entity_type] * _ROWID_MULTIPLIER + int(entity_id)


def _decode_rowid(rowid):
    """Unpack an FTS rowid back into (entity_type, entity_id).

    Returns ``(None, None)`` for an unrecognised type code so a stale index row
    can never crash the search page.
    """
    code, entity_id = divmod(int(rowid), _ROWID_MULTIPLIER)
    return _CODE_TO_ENTITY_TYPE.get(code), entity_id


def _sanitize_query(query):
    """Turn arbitrary user input into a safe FTS5 phrase match expression.

    Strips every FTS5 operator character, collapses runs of whitespace, and
    wraps the remaining tokens in double quotes so the whole thing is treated as
    a single literal phrase. Returns an empty string when nothing usable
    remains, which the caller treats as "no results".
    """
    if not query:
        return ""
    cleaned = _FTS5_SPECIAL_CHARS.sub(" ", query)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    if not cleaned:
        return ""
    # Wrap as a quoted phrase. The interior is already free of double quotes
    # (stripped above), so the surrounding quotes cannot be broken out of.
    return '"' + cleaned + '"'


def search(conn, query, project_id):
    """Search indexed entities within a single project.

    Returns a list of dicts with keys ``entity_type``, ``entity_id``, ``title``
    and ``snippet``, ordered by FTS5 relevance. An empty/whitespace/operator-only
    query returns ``[]`` without touching the database.
    """
    match_expr = _sanitize_query(query)
    if not match_expr:
        return []

    rows = conn.execute(
        "SELECT rowid FROM search_index WHERE search_index MATCH ? ORDER BY rank",
        (match_expr,),
    ).fetchall()

    results = []
    for row in rows:
        entity_type, entity_id = _decode_rowid(row["rowid"])
        if entity_type is None:
            continue
        table, title_col, snippet_col = _ENTITY_SOURCES[entity_type]
        source = conn.execute(
            "SELECT %s AS title, %s AS snippet FROM %s "
            "WHERE id = ? AND project_id = ?" % (title_col, snippet_col, table),
            (entity_id, project_id),
        ).fetchone()
        # Drop matches that belong to another project or whose source row was
        # deleted without the index being updated -- the search page must never
        # leak cross-project data or crash on a dangling match.
        if source is None:
            continue
        results.append(
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "title": source["title"],
                "snippet": source["snippet"] or "",
            }
        )
    return results


def index_entity(conn, entity_type, entity_id, title, body):
    """Insert or replace an entity's searchable text in the FTS5 index.

    Single-writer entry point called by the scenes/cast/crew/locations route
    agents after a create or update. Does NOT commit -- the caller owns the
    transaction (see the Transaction Contracts table). Re-indexing is idempotent:
    the prior row for this entity is deleted first so the index never accumulates
    duplicates.
    """
    rowid = _encode_rowid(entity_type, entity_id)
    # contentless_delete=1 tables are deleted via an ordinary DELETE on rowid;
    # the FTS5 'delete' special-insert command is rejected for such tables.
    conn.execute("DELETE FROM search_index WHERE rowid = ?", (rowid,))
    conn.execute(
        "INSERT INTO search_index (rowid, entity_type, entity_id, title, body) "
        "VALUES (?, ?, ?, ?, ?)",
        (rowid, entity_type, entity_id, title, body),
    )


def remove_entity(conn, entity_type, entity_id):
    """Remove an entity from the FTS5 index.

    Single-writer entry point called by the route agents after a delete. Does
    NOT commit -- the caller owns the transaction. Safe to call when the entity
    was never indexed (the DELETE simply affects zero rows).
    """
    rowid = _encode_rowid(entity_type, entity_id)
    conn.execute("DELETE FROM search_index WHERE rowid = ?", (rowid,))
