"""Dashboard aggregates — cross-entity, READ-only role summaries.

This module is the FIVE-import aggregate seam (Feed-Forward risk). Per the shared
interface spec (§Model Functions dashboard_models, §1b, §1d, §2), it imports EXACTLY
five model modules for the per-actor relational aggregates:

    lesson_models        -> upcoming lessons
    invoice_models       -> balances
    enrollment_models    -> my enrollments
    attendance_models    -> attendance rate
    practice_log_models  -> practice minutes

Plain admin counts (students, instructors, active courses, lessons this week,
outstanding invoice cents, instruments out) are computed via DIRECT get_db() COUNT/SUM
SQL — NOT via student/instructor/course/instrument/room model imports — to keep the
cross-boundary surface to exactly the five relational imports above.

All functions are READ-only: no writes, no transactions, no commits.
All functions return plain dicts (never sqlite3.Row).
"""

from datetime import datetime, timedelta, timezone

from studio.database import get_db

from studio.models import lesson_models
from studio.models import invoice_models
from studio.models import enrollment_models
from studio.models import attendance_models
from studio.models import practice_log_models


def _now_iso() -> str:
    """Current UTC time as ISO-8601 TEXT (matches schema timestamp storage)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _week_start_iso() -> str:
    """Start (Monday 00:00 UTC) of the current week as ISO-8601 TEXT.

    Used to scope 'this week' aggregates (lessons_this_week, practice minutes).
    """
    now = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    week_start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    return week_start.strftime("%Y-%m-%d %H:%M:%S")


def admin_summary() -> dict:
    """Studio-wide counts for the admin dashboard.

    Direct get_db() COUNT/SUM SQL only (no entity-model imports). Keys:
        students, instructors, active_courses, lessons_this_week,
        outstanding_invoice_cents, instruments_out.

    outstanding_invoice_cents = SUM of invoice_items.amount_cents over invoices whose
    status is neither 'paid' nor 'void' (i.e. draft + sent) — the studio's open
    receivable. (See SPEC_ISSUES: the spec says "SUM of items on non-paid non-void
    invoices"; taken here as status IN ('draft','sent').)
    """
    db = get_db()

    students = db.execute("SELECT COUNT(*) AS c FROM students").fetchone()["c"]
    instructors = db.execute("SELECT COUNT(*) AS c FROM instructors").fetchone()["c"]
    active_courses = db.execute(
        "SELECT COUNT(*) AS c FROM courses WHERE active = 1"
    ).fetchone()["c"]

    week_start = _week_start_iso()
    week_end = (
        datetime.strptime(week_start, "%Y-%m-%d %H:%M:%S") + timedelta(days=7)
    ).strftime("%Y-%m-%d %H:%M:%S")
    lessons_this_week = db.execute(
        "SELECT COUNT(*) AS c FROM lessons WHERE starts_at >= ? AND starts_at < ?",
        (week_start, week_end),
    ).fetchone()["c"]

    outstanding_invoice_cents = db.execute(
        """
        SELECT COALESCE(SUM(ii.amount_cents), 0) AS c
          FROM invoice_items ii
          JOIN invoices i ON i.id = ii.invoice_id
         WHERE i.status NOT IN ('paid', 'void')
        """
    ).fetchone()["c"]

    instruments_out = db.execute(
        "SELECT COUNT(*) AS c FROM instruments WHERE status = 'checked_out'"
    ).fetchone()["c"]

    return {
        "students": students,
        "instructors": instructors,
        "active_courses": active_courses,
        "lessons_this_week": lessons_this_week,
        "outstanding_invoice_cents": outstanding_invoice_cents,
        "instruments_out": instruments_out,
    }


def instructor_summary(instructor_id) -> dict:
    """Per-instructor dashboard aggregate.

    Keys:
        upcoming_lessons  -> list[dict] of this instructor's scheduled future lessons
                             (via lesson_models.list_lessons — the relational seam).
        courses           -> list[dict] of courses this instructor owns (direct SQL).
        students_count    -> distinct students this instructor teaches, derived from
                             lessons (direct SQL). (See SPEC_ISSUES: "my students" is
                             not an explicit table; taken as distinct lesson.student_id.)
    """
    db = get_db()
    now = _now_iso()

    upcoming_lessons = lesson_models.list_lessons(
        instructor_id=instructor_id, date_from=now, status="scheduled"
    )

    courses = [
        dict(row)
        for row in db.execute(
            "SELECT * FROM courses WHERE instructor_id = ? ORDER BY name",
            (instructor_id,),
        ).fetchall()
    ]

    students_count = db.execute(
        "SELECT COUNT(DISTINCT student_id) AS c FROM lessons WHERE instructor_id = ?",
        (instructor_id,),
    ).fetchone()["c"]

    return {
        "upcoming_lessons": upcoming_lessons,
        "courses": courses,
        "students_count": students_count,
    }


def student_summary(student_id) -> dict:
    """Per-student dashboard aggregate.

    Keys:
        upcoming_lessons          -> list[dict] of this student's scheduled future
                                     lessons (lesson_models.list_lessons).
        enrollments               -> list[dict] (enrollment_models.list_enrollments).
        balance_cents             -> total owed = SUM of total_cents over the student's
                                     non-paid, non-void invoices (invoice_models reads).
        practice_minutes_this_week-> int (practice_log_models.total_minutes since Monday).
        attendance_rate           -> float (attendance_models.attendance_rate).
    """
    now = _now_iso()

    upcoming_lessons = lesson_models.list_lessons(
        student_id=student_id, date_from=now, status="scheduled"
    )

    enrollments = enrollment_models.list_enrollments(student_id=student_id)

    # Balance: sum computed totals over this student's open (non-paid, non-void) invoices.
    # Each invoice dict carries total_cents = SUM(items) per the invoice contract.
    invoices = invoice_models.list_invoices(student_id=student_id)
    balance_cents = sum(
        inv.get("total_cents", 0) or 0
        for inv in invoices
        if inv.get("status") not in ("paid", "void")
    )

    practice_minutes_this_week = practice_log_models.total_minutes(
        student_id, since=_week_start_iso()
    )

    attendance_rate = attendance_models.attendance_rate(student_id)

    return {
        "upcoming_lessons": upcoming_lessons,
        "enrollments": enrollments,
        "balance_cents": balance_cents,
        "practice_minutes_this_week": practice_minutes_this_week,
        "attendance_rate": attendance_rate,
    }
