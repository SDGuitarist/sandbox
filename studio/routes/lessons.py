"""Lessons blueprint — the 4-way FK seam (instructor + student + room + course).

Ownership-scoped list/view (role+own via the *_for getters); create/edit/status are
staff-only (admin,instructor). All model calls are qualified through the imported model
MODULES (shared function names with the views, so never import the functions bare).
"""

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from studio.auth import current_user, login_required, role_required
from studio.models import (
    audit_models,
    course_models,
    instructor_models,
    lesson_models,
    room_models,
    student_models,
)

bp = Blueprint("lessons", __name__, url_prefix="/lessons")

_STATUSES = ("scheduled", "completed", "cancelled", "no_show")

# Optional list filters read from request.args and forwarded to list_lessons_for.
_FILTER_KEYS = ("student_id", "instructor_id", "room_id", "date_from", "date_to", "status")


def _dropdowns():
    """FK dropdown option lists — active rows only (Coordinated Behaviors §4)."""
    return {
        "instructors": instructor_models.list_instructors(active_only=True),
        "students": student_models.list_students(active_only=True),
        "rooms": room_models.list_rooms(active_only=True),
        "courses": course_models.list_courses(active_only=True),
    }


def _collect_filters():
    """Pull optional list filters from the query string (blank values dropped)."""
    filters = {}
    for key in _FILTER_KEYS:
        value = request.args.get(key)
        if value is not None and value.strip() != "":
            filters[key] = value.strip()
    return filters


def _parse_lesson_form(form):
    """Validate + normalize a create/edit lesson submission.

    Returns (data, error). `data` is a dict of validated fields on success;
    `error` is a user-facing message string on failure (data is None then).
    FK existence is confirmed here via the model getters; the deeper FK guard also
    lives in create_lesson/update_lesson (raises ValueError) as a backstop.
    """
    def _opt_int(name):
        raw = (form.get(name) or "").strip()
        if raw == "":
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return "ERR"

    def _req_int(name):
        raw = (form.get(name) or "").strip()
        if raw == "":
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return "ERR"

    instructor_id = _req_int("instructor_id")
    student_id = _req_int("student_id")
    room_id = _opt_int("room_id")
    course_id = _opt_int("course_id")
    starts_at = (form.get("starts_at") or "").strip()
    ends_at = (form.get("ends_at") or "").strip()
    notes = (form.get("notes") or "").strip() or None

    if instructor_id in (None, "ERR"):
        return None, "Instructor is required."
    if student_id in (None, "ERR"):
        return None, "Student is required."
    if room_id == "ERR":
        return None, "Room selection is invalid."
    if course_id == "ERR":
        return None, "Course selection is invalid."
    if not starts_at or not ends_at:
        return None, "Both start and end times are required."
    # ISO-8601 comparison: stored as TEXT, lexicographic order == chronological order.
    if not (ends_at > starts_at):
        return None, "End time must be after start time."

    # FK existence checks (existence leak avoided — staff-only route).
    if instructor_models.get_instructor(instructor_id) is None:
        return None, "Selected instructor does not exist."
    if student_models.get_student(student_id) is None:
        return None, "Selected student does not exist."
    if room_id is not None and room_models.get_room(room_id) is None:
        return None, "Selected room does not exist."
    if course_id is not None and course_models.get_course(course_id) is None:
        return None, "Selected course does not exist."

    return (
        {
            "instructor_id": instructor_id,
            "student_id": student_id,
            "room_id": room_id,
            "course_id": course_id,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "notes": notes,
        },
        None,
    )


@bp.route("/")
@login_required
def list_lessons():
    """Ownership-scoped list (role+own): staff→all, student→own, instructor→own."""
    filters = _collect_filters()
    lessons = lesson_models.list_lessons_for(current_user(), **filters)
    return render_template("lessons/list.html", lessons=lessons, filters=filters)


@bp.route("/new", methods=("GET", "POST"))
@role_required("admin", "instructor")
def create_lesson():
    if request.method == "POST":
        data, error = _parse_lesson_form(request.form)
        if error is not None:
            flash(error, "error")
            return render_template("lessons/new.html", form=request.form, **_dropdowns()), 400
        try:
            lid = lesson_models.create_lesson(
                instructor_id=data["instructor_id"],
                student_id=data["student_id"],
                starts_at=data["starts_at"],
                ends_at=data["ends_at"],
                course_id=data["course_id"],
                room_id=data["room_id"],
                notes=data["notes"],
            )
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("lessons/new.html", form=request.form, **_dropdowns()), 400

        # Post-commit audit (exactly once per mutation — §4).
        audit_models.record(
            current_user()["id"], "create", "lesson", lid, detail=None
        )

        # Non-blocking conflict warning (does NOT prevent the save — §3).
        conflicts = lesson_models.check_conflicts(
            data["instructor_id"],
            data["room_id"],
            data["starts_at"],
            data["ends_at"],
            exclude_lesson_id=lid,
        )
        if conflicts:
            flash("Warning: this lesson overlaps an existing instructor/room booking.", "warning")

        flash("Lesson created.", "success")
        return redirect(url_for("lessons.view_lesson", lid=lid))

    return render_template("lessons/new.html", form={}, **_dropdowns())


@bp.route("/<int:lid>")
@login_required
def view_lesson(lid):
    """Ownership-scoped view (role+own): non-owner → 404, no existence leak."""
    lesson = lesson_models.get_lesson_for(lid, current_user()) or abort(404)
    return render_template("lessons/view.html", lesson=lesson, statuses=_STATUSES)


@bp.route("/<int:lid>/edit", methods=("GET", "POST"))
@role_required("admin", "instructor")
def edit_lesson(lid):
    # Staff-only route: use the unscoped getter, 404 if the lesson is absent.
    lesson = lesson_models.get_lesson(lid) or abort(404)

    if request.method == "POST":
        data, error = _parse_lesson_form(request.form)
        if error is not None:
            flash(error, "error")
            return (
                render_template("lessons/edit.html", lesson=lesson, form=request.form, **_dropdowns()),
                400,
            )
        try:
            lesson_models.update_lesson(
                lid,
                instructor_id=data["instructor_id"],
                student_id=data["student_id"],
                starts_at=data["starts_at"],
                ends_at=data["ends_at"],
                course_id=data["course_id"],
                room_id=data["room_id"],
                notes=data["notes"],
            )
        except ValueError as exc:
            flash(str(exc), "error")
            return (
                render_template("lessons/edit.html", lesson=lesson, form=request.form, **_dropdowns()),
                400,
            )

        audit_models.record(current_user()["id"], "update", "lesson", lid, detail=None)

        conflicts = lesson_models.check_conflicts(
            data["instructor_id"],
            data["room_id"],
            data["starts_at"],
            data["ends_at"],
            exclude_lesson_id=lid,
        )
        if conflicts:
            flash("Warning: this lesson overlaps an existing instructor/room booking.", "warning")

        flash("Lesson updated.", "success")
        return redirect(url_for("lessons.view_lesson", lid=lid))

    return render_template("lessons/edit.html", lesson=lesson, form=lesson, **_dropdowns())


@bp.route("/<int:lid>/status", methods=("POST",))
@role_required("admin", "instructor")
def set_status(lid):
    if lesson_models.get_lesson(lid) is None:
        abort(404)
    status = (request.form.get("status") or "").strip()
    if status not in _STATUSES:
        flash("Invalid status value.", "error")
        abort(400)
    lesson_models.set_lesson_status(lid, status)
    audit_models.record(current_user()["id"], "update", "lesson", lid, detail=f"status={status}")
    flash("Lesson status updated.", "success")
    return redirect(url_for("lessons.view_lesson", lid=lid))
