import json
import re
import sqlite3


# ---------------------------------------------------------------------------
# Variable System
# ---------------------------------------------------------------------------

def extract_variables(text: str) -> list[str]:
    """Extract {{variable_name}} placeholders from text.
    Returns unique variable names, preserving first-occurrence order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for match in re.finditer(r'\{\{(\w+)\}\}', text):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def substitute_variables(text: str, variables: dict[str, str]) -> str:
    """Replace {{variable_name}} with values from variables dict."""
    for name, value in variables.items():
        text = text.replace('{{' + name + '}}', value)
    return text


# ---------------------------------------------------------------------------
# FTS5 Search Sanitization (FC36)
# ---------------------------------------------------------------------------

def sanitize_fts_query(query: str) -> str | None:
    """Sanitize user input for FTS5 MATCH to prevent operator injection.
    Strips * " ( ) : ^ \\ characters, collapses whitespace, wraps in quotes.
    Returns None if query is empty after sanitization (caller skips MATCH).
    """
    cleaned = re.sub(r'[*"():^\\]', '', query).strip()
    if not cleaned:
        return None
    return f'"{cleaned}"'


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

def get_all_tags(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all tags, ordered by name."""
    return conn.execute('SELECT id, name FROM tags ORDER BY name').fetchall()


def set_prompt_tags(conn: sqlite3.Connection, prompt_id: int,
                    tag_names: list[str]) -> None:
    """Replace all tags for a prompt. Creates new tags as needed.
    Does NOT commit — called within create_prompt/update_prompt transaction.
    """
    # Delete existing tags for this prompt
    conn.execute('DELETE FROM prompt_tags WHERE prompt_id = ?', (prompt_id,))

    for tag_name in tag_names:
        tag_name = tag_name.strip()
        if not tag_name:
            continue

        # Get or create the tag
        row = conn.execute(
            'SELECT id FROM tags WHERE name = ?', (tag_name,)
        ).fetchone()

        if row is None:
            cursor = conn.execute(
                'INSERT INTO tags (name) VALUES (?)', (tag_name,)
            )
            tag_id = cursor.lastrowid
        else:
            tag_id = row['id']

        conn.execute(
            'INSERT OR IGNORE INTO prompt_tags (prompt_id, tag_id) VALUES (?, ?)',
            (prompt_id, tag_id),
        )


def get_prompt_tags(conn: sqlite3.Connection,
                    prompt_id: int) -> list[sqlite3.Row]:
    """Get tags for a prompt."""
    return conn.execute(
        'SELECT t.id, t.name '
        'FROM tags t '
        'JOIN prompt_tags pt ON pt.tag_id = t.id '
        'WHERE pt.prompt_id = ? '
        'ORDER BY t.name',
        (prompt_id,),
    ).fetchall()


# ---------------------------------------------------------------------------
# Prompt CRUD
# ---------------------------------------------------------------------------

def create_prompt(conn: sqlite3.Connection, name: str, description: str,
                  system_prompt: str, user_prompt: str,
                  tag_names: list[str]) -> int:
    """Create a prompt and its initial version. Sets tags.
    Calls extract_variables() internally.
    Returns the new prompt's ID.
    Commits internally (BEGIN IMMEDIATE).
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        variables = json.dumps(
            extract_variables(system_prompt + ' ' + user_prompt)
        )
        cursor = conn.execute(
            'INSERT INTO prompts (name, description, system_prompt, '
            'user_prompt, variables, version_count) '
            'VALUES (?, ?, ?, ?, ?, 1)',
            (name, description, system_prompt, user_prompt, variables),
        )
        prompt_id = cursor.lastrowid
        conn.execute(
            'INSERT INTO prompt_versions '
            '(prompt_id, version_number, system_prompt, user_prompt, variables) '
            'VALUES (?, 1, ?, ?, ?)',
            (prompt_id, system_prompt, user_prompt, variables),
        )
        set_prompt_tags(conn, prompt_id, tag_names)
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
    return prompt_id


def get_prompt(conn: sqlite3.Connection, prompt_id: int) -> sqlite3.Row | None:
    """Get a single prompt by ID."""
    return conn.execute(
        'SELECT * FROM prompts WHERE id = ?', (prompt_id,)
    ).fetchone()


def get_all_prompts(conn: sqlite3.Connection,
                    search_query: str | None = None,
                    tag_name: str | None = None) -> list[sqlite3.Row]:
    """List all prompts, optionally filtered by FTS5 search and/or tag.
    Uses sanitize_fts_query() internally. FTS5 MATCH uses parameterized
    binding (MATCH ?) — never string interpolation.
    """
    conditions: list[str] = []
    params: list[str | int] = []

    # FTS5 search filter
    fts_join = ''
    if search_query:
        safe_query = sanitize_fts_query(search_query)
        if safe_query is not None:
            fts_join = 'JOIN prompts_fts ON prompts_fts.rowid = p.id'
            conditions.append('prompts_fts MATCH ?')
            params.append(safe_query)

    # Tag filter
    tag_join = ''
    if tag_name:
        tag_join = (
            'JOIN prompt_tags pt ON pt.prompt_id = p.id '
            'JOIN tags t ON t.id = pt.tag_id'
        )
        conditions.append('t.name = ?')
        params.append(tag_name)

    where_clause = ''
    if conditions:
        where_clause = 'WHERE ' + ' AND '.join(conditions)

    sql = (
        f'SELECT p.* FROM prompts p '
        f'{fts_join} {tag_join} {where_clause} '
        f'ORDER BY p.updated_at DESC'
    )
    return conn.execute(sql, params).fetchall()


def update_prompt(conn: sqlite3.Connection, prompt_id: int, name: str,
                  description: str, system_prompt: str, user_prompt: str,
                  tag_names: list[str]) -> int:
    """Update prompt and create a new version. Returns new version_id.
    Calls extract_variables() internally.
    Commits internally (BEGIN IMMEDIATE).
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        variables = json.dumps(
            extract_variables(system_prompt + ' ' + user_prompt)
        )

        # Get current version_count to compute the next version number
        row = conn.execute(
            'SELECT version_count FROM prompts WHERE id = ?', (prompt_id,)
        ).fetchone()
        new_version_number = row['version_count'] + 1

        # Update the prompt row
        conn.execute(
            'UPDATE prompts SET name = ?, description = ?, system_prompt = ?, '
            'user_prompt = ?, variables = ?, version_count = ?, '
            "updated_at = datetime('now') "
            'WHERE id = ?',
            (name, description, system_prompt, user_prompt, variables,
             new_version_number, prompt_id),
        )

        # Insert the new version
        cursor = conn.execute(
            'INSERT INTO prompt_versions '
            '(prompt_id, version_number, system_prompt, user_prompt, variables) '
            'VALUES (?, ?, ?, ?, ?)',
            (prompt_id, new_version_number, system_prompt, user_prompt,
             variables),
        )
        version_id = cursor.lastrowid

        set_prompt_tags(conn, prompt_id, tag_names)
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
    return version_id


def delete_prompt(conn: sqlite3.Connection, prompt_id: int) -> None:
    """Delete a prompt and all its versions, tags, and test runs (CASCADE).
    Commits internally.
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('DELETE FROM prompts WHERE id = ?', (prompt_id,))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise


# ---------------------------------------------------------------------------
# Version History
# ---------------------------------------------------------------------------

def get_prompt_versions(conn: sqlite3.Connection,
                        prompt_id: int) -> list[sqlite3.Row]:
    """Get all versions for a prompt, newest first."""
    return conn.execute(
        'SELECT * FROM prompt_versions '
        'WHERE prompt_id = ? '
        'ORDER BY version_number DESC',
        (prompt_id,),
    ).fetchall()


def get_prompt_version(conn: sqlite3.Connection,
                       version_id: int) -> sqlite3.Row | None:
    """Get a specific version by its primary key ID."""
    return conn.execute(
        'SELECT * FROM prompt_versions WHERE id = ?', (version_id,)
    ).fetchone()


# ---------------------------------------------------------------------------
# Test Runs
# ---------------------------------------------------------------------------

def create_test_run(conn: sqlite3.Connection, prompt_version_id: int,
                    model_name: str, variables_used: dict,
                    response_text: str | None, input_tokens: int | None,
                    output_tokens: int | None, duration_ms: int | None,
                    error: str | None = None) -> int:
    """Create a test run record. Updates prompt.last_tested_at.
    Commits internally.
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.execute(
            'INSERT INTO test_runs '
            '(prompt_version_id, model_name, variables_used, response_text, '
            'input_tokens, output_tokens, duration_ms, error) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (prompt_version_id, model_name, json.dumps(variables_used),
             response_text, input_tokens, output_tokens, duration_ms, error),
        )
        run_id = cursor.lastrowid

        # Update the parent prompt's last_tested_at via the version's prompt_id
        conn.execute(
            "UPDATE prompts SET last_tested_at = datetime('now') "
            'WHERE id = ('
            '  SELECT prompt_id FROM prompt_versions WHERE id = ?'
            ')',
            (prompt_version_id,),
        )
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
    return run_id


def get_test_run(conn: sqlite3.Connection,
                 run_id: int) -> sqlite3.Row | None:
    """Get a test run by ID."""
    return conn.execute(
        'SELECT * FROM test_runs WHERE id = ?', (run_id,)
    ).fetchone()


def get_test_runs_for_prompt(conn: sqlite3.Connection,
                             prompt_id: int,
                             limit: int = 50) -> list[sqlite3.Row]:
    """Get test runs for a prompt (across all versions), newest first.
    LIMIT is pushed into SQL — never fetch all + slice in Python.
    """
    return conn.execute(
        'SELECT tr.* FROM test_runs tr '
        'JOIN prompt_versions pv ON pv.id = tr.prompt_version_id '
        'WHERE pv.prompt_id = ? '
        'ORDER BY tr.created_at DESC '
        'LIMIT ?',
        (prompt_id, limit),
    ).fetchall()


# ---------------------------------------------------------------------------
# Dashboard Stats
# ---------------------------------------------------------------------------

def get_dashboard_stats(conn: sqlite3.Connection) -> dict:
    """Get dashboard summary stats."""
    total_prompts = conn.execute(
        'SELECT COUNT(*) FROM prompts'
    ).fetchone()[0]
    total_versions = conn.execute(
        'SELECT COUNT(*) FROM prompt_versions'
    ).fetchone()[0]
    total_tests = conn.execute(
        'SELECT COUNT(*) FROM test_runs'
    ).fetchone()[0]
    return {
        'total_prompts': total_prompts,
        'total_versions': total_versions,
        'total_tests': total_tests,
    }
