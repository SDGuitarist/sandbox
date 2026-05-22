import sqlite3


def _compute_bmi(weight_kg: float | None, height_cm: float | None) -> float | None:
    """Compute BMI from weight (kg) and height (cm).

    Formula: weight_kg / (height_cm / 100) ** 2
    Returns None if either value is missing or height is zero.
    """
    if weight_kg is None or height_cm is None or height_cm == 0:
        return None
    height_m = height_cm / 100
    return round(weight_kg / (height_m ** 2), 2)


def create_assessment(conn: sqlite3.Connection, member_id: int,
                      trainer_id: int | None, assessment_date: str,
                      weight_kg: float | None, height_cm: float | None,
                      body_fat_pct: float | None,
                      resting_heart_rate: int | None,
                      notes: str) -> int:
    """Create fitness assessment. Computes BMI automatically if weight and height provided.

    BMI = weight_kg / (height_cm / 100) ** 2
    Returns new assessment ID.

    Usage:
        assess_id = create_assessment(conn, 1, 2, '2026-05-21',
                                      80.0, 175.0, 15.5, 68, 'Good form')
        return redirect(url_for('assessments.detail', assessment_id=assess_id))

    Commits: yes (conn.commit())
    """
    bmi = _compute_bmi(weight_kg, height_cm)
    cursor = conn.execute(
        """INSERT INTO fitness_assessments
           (member_id, trainer_id, assessment_date, weight_kg, height_cm,
            body_fat_pct, bmi, resting_heart_rate, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (member_id, trainer_id, assessment_date, weight_kg, height_cm,
         body_fat_pct, bmi, resting_heart_rate, notes),
    )
    conn.commit()
    return cursor.lastrowid


def get_assessment(conn: sqlite3.Connection, assessment_id: int) -> sqlite3.Row | None:
    """Get assessment by ID with member_name and trainer_name joined.

    Returns Row with all fitness_assessments columns plus member_name and
    trainer_name (trainer_name may be NULL if no trainer assigned).
    Returns None if not found.
    """
    row = conn.execute(
        """SELECT fa.*, m.name AS member_name, t.name AS trainer_name
           FROM fitness_assessments fa
           JOIN members m ON fa.member_id = m.id
           LEFT JOIN trainers t ON fa.trainer_id = t.id
           WHERE fa.id = ?""",
        (assessment_id,),
    ).fetchone()
    return row


def get_assessments_by_member(conn: sqlite3.Connection,
                               member_id: int) -> list[sqlite3.Row]:
    """Get assessments for a member. Ordered by assessment_date DESC.

    Includes trainer_name (may be NULL).
    """
    rows = conn.execute(
        """SELECT fa.*, t.name AS trainer_name
           FROM fitness_assessments fa
           LEFT JOIN trainers t ON fa.trainer_id = t.id
           WHERE fa.member_id = ?
           ORDER BY fa.assessment_date DESC""",
        (member_id,),
    ).fetchall()
    return rows


def get_all_assessments(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all assessments with member_name and trainer_name. Ordered by date DESC."""
    rows = conn.execute(
        """SELECT fa.*, m.name AS member_name, t.name AS trainer_name
           FROM fitness_assessments fa
           JOIN members m ON fa.member_id = m.id
           LEFT JOIN trainers t ON fa.trainer_id = t.id
           ORDER BY fa.assessment_date DESC""",
    ).fetchall()
    return rows


def update_assessment(conn: sqlite3.Connection, assessment_id: int,
                      member_id: int, trainer_id: int | None,
                      assessment_date: str, weight_kg: float | None,
                      height_cm: float | None, body_fat_pct: float | None,
                      resting_heart_rate: int | None,
                      notes: str) -> None:
    """Update assessment. Recomputes BMI.

    Commits: yes (conn.commit())
    """
    bmi = _compute_bmi(weight_kg, height_cm)
    conn.execute(
        """UPDATE fitness_assessments
           SET member_id = ?, trainer_id = ?, assessment_date = ?,
               weight_kg = ?, height_cm = ?, body_fat_pct = ?, bmi = ?,
               resting_heart_rate = ?, notes = ?
           WHERE id = ?""",
        (member_id, trainer_id, assessment_date, weight_kg, height_cm,
         body_fat_pct, bmi, resting_heart_rate, notes, assessment_id),
    )
    conn.commit()


def delete_assessment(conn: sqlite3.Connection, assessment_id: int) -> None:
    """Delete assessment.

    Commits: yes (conn.commit())
    """
    conn.execute(
        "DELETE FROM fitness_assessments WHERE id = ?",
        (assessment_id,),
    )
    conn.commit()


def get_latest_assessment(conn: sqlite3.Connection,
                           member_id: int) -> sqlite3.Row | None:
    """Get most recent assessment for a member. Returns Row or None.

    Usage:
        latest = get_latest_assessment(conn, member_id)
        if latest is not None:
            weight = latest['weight_kg']
    """
    row = conn.execute(
        """SELECT * FROM fitness_assessments
           WHERE member_id = ?
           ORDER BY assessment_date DESC
           LIMIT 1""",
        (member_id,),
    ).fetchone()
    return row
