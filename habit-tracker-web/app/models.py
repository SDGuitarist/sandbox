import sqlite3
from datetime import date, timedelta


def create_habit(conn, name: str) -> int:
    """Insert new habit. Returns the new habit ID."""
    cursor = conn.execute("INSERT INTO habits (name) VALUES (?)", (name,))
    return cursor.lastrowid


def get_all_habits(conn) -> list[sqlite3.Row]:
    """Get all active (non-archived) habits, oldest first."""
    return conn.execute(
        "SELECT * FROM habits WHERE archived = 0 ORDER BY created_at ASC"
    ).fetchall()


def get_habit_by_id(conn, habit_id: int) -> sqlite3.Row | None:
    """Get single habit. Returns Row or None."""
    return conn.execute(
        "SELECT * FROM habits WHERE id = ?", (habit_id,)
    ).fetchone()


def update_habit(conn, habit_id: int, name: str) -> bool:
    """Update habit name. Returns True if row existed and was updated."""
    cursor = conn.execute(
        "UPDATE habits SET name = ? WHERE id = ?", (name, habit_id)
    )
    return cursor.rowcount > 0


def archive_habit(conn, habit_id: int) -> bool:
    """Soft-delete (archive) a habit. Returns True if row existed."""
    cursor = conn.execute(
        "UPDATE habits SET archived = 1 WHERE id = ? AND archived = 0",
        (habit_id,),
    )
    return cursor.rowcount > 0


def toggle_completion(conn, habit_id: int, target_date: str) -> bool:
    """Atomic toggle: INSERT if not exists, DELETE if exists.
    MUST be called inside get_db(immediate=True) context.
    Raises sqlite3.IntegrityError if habit_id FK is invalid.
    Returns True if completion was ADDED, False if REMOVED.
    """
    cursor = conn.execute(
        "INSERT INTO completions (habit_id, completed_date) VALUES (?, ?) "
        "ON CONFLICT(habit_id, completed_date) DO NOTHING",
        (habit_id, target_date),
    )
    if cursor.rowcount > 0:
        return True
    conn.execute(
        "DELETE FROM completions WHERE habit_id = ? AND completed_date = ?",
        (habit_id, target_date),
    )
    return False


def get_completions_for_week(
    conn, habit_id: int, week_start: str, week_end: str
) -> set[str]:
    """Get all completion dates for a habit within a date range."""
    rows = conn.execute(
        "SELECT completed_date FROM completions "
        "WHERE habit_id = ? AND completed_date BETWEEN ? AND ?",
        (habit_id, week_start, week_end),
    ).fetchall()
    return {row["completed_date"] for row in rows}


def get_all_completions(conn, habit_id: int) -> list[str]:
    """Get all completion dates for a habit (for streak computation)."""
    rows = conn.execute(
        "SELECT completed_date FROM completions WHERE habit_id = ? "
        "ORDER BY completed_date",
        (habit_id,),
    ).fetchall()
    return [row["completed_date"] for row in rows]


def compute_current_streak(completions: list[str]) -> int:
    """Compute current streak. Uses set deduplication before date math."""
    if not completions:
        return 0
    dates = sorted({date.fromisoformat(d) for d in completions}, reverse=True)
    today = date.today()
    if dates[0] != today and dates[0] != today - timedelta(days=1):
        return 0
    streak = 1
    for i in range(1, len(dates)):
        if dates[i - 1] - dates[i] == timedelta(days=1):
            streak += 1
        else:
            break
    return streak


def compute_longest_streak(completions: list[str]) -> int:
    """Compute longest streak. Uses set deduplication before date math."""
    if not completions:
        return 0
    dates = sorted({date.fromisoformat(d) for d in completions})
    longest = 1
    current = 1
    for i in range(1, len(dates)):
        if dates[i] - dates[i - 1] == timedelta(days=1):
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest
