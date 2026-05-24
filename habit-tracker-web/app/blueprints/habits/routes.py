import sqlite3
from datetime import date, timedelta

from flask import abort, flash, redirect, render_template, request, url_for

from app.blueprints.habits import habits_bp
from app.db import get_db
from app.models import (
    archive_habit,
    compute_current_streak,
    create_habit,
    get_all_completions,
    get_all_habits,
    get_completions_for_week,
    get_habit_by_id,
    toggle_completion,
    update_habit,
)


@habits_bp.route("/")
def dashboard():
    with get_db() as conn:
        habits = get_all_habits(conn)
        today_str = date.today().isoformat()
        habit_data = []
        for habit in habits:
            completions = get_all_completions(conn, habit["id"])
            today_dates = get_completions_for_week(
                conn, habit["id"], today_str, today_str
            )
            habit_data.append(
                {
                    "id": habit["id"],
                    "name": habit["name"],
                    "streak": compute_current_streak(completions),
                    "done_today": today_str in today_dates,
                }
            )
    return render_template("dashboard.html", habits=habit_data)


@habits_bp.route("/habits/new")
def new_habit():
    return render_template("habits/form.html", habit=None, action_url=url_for("habits.create_habit"))


@habits_bp.route("/habits", methods=["POST"])
def create_habit_route():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Habit name is required")
        return redirect(url_for("habits.new_habit"))
    if len(name) > 100:
        flash("Habit name too long (max 100 characters)")
        return redirect(url_for("habits.new_habit"))
    with get_db(immediate=True) as conn:
        create_habit(conn, name)
    return redirect(url_for("habits.dashboard"))


@habits_bp.route("/habits/<int:habit_id>/edit")
def edit_habit(habit_id):
    with get_db() as conn:
        habit = get_habit_by_id(conn, habit_id)
    if habit is None:
        abort(404)
    return render_template(
        "habits/form.html",
        habit=habit,
        action_url=url_for("habits.update_habit_route", habit_id=habit_id),
    )


@habits_bp.route("/habits/<int:habit_id>/edit", methods=["POST"])
def update_habit_route(habit_id):
    name = request.form.get("name", "").strip()
    if not name:
        flash("Habit name is required")
        return redirect(url_for("habits.edit_habit", habit_id=habit_id))
    if len(name) > 100:
        flash("Habit name too long (max 100 characters)")
        return redirect(url_for("habits.edit_habit", habit_id=habit_id))
    with get_db(immediate=True) as conn:
        if not update_habit(conn, habit_id, name):
            abort(404)
    return redirect(url_for("habits.dashboard"))


@habits_bp.route("/habits/<int:habit_id>/archive", methods=["POST"])
def archive_habit_route(habit_id):
    with get_db(immediate=True) as conn:
        if not archive_habit(conn, habit_id):
            abort(404)
    return redirect(url_for("habits.dashboard"))


@habits_bp.route("/habits/<int:habit_id>/toggle", methods=["POST"])
def toggle_today(habit_id):
    today_str = date.today().isoformat()
    try:
        with get_db(immediate=True) as conn:
            habit = get_habit_by_id(conn, habit_id)
            if habit is None or habit["archived"]:
                abort(404)
            toggle_completion(conn, habit_id, today_str)
    except sqlite3.IntegrityError:
        abort(404)
    return redirect(url_for("habits.dashboard"))


@habits_bp.route("/habits/<int:habit_id>/toggle/<target_date>", methods=["POST"])
def toggle_date(habit_id, target_date):
    # Validate date format
    try:
        parsed = date.fromisoformat(target_date)
    except ValueError:
        abort(400)

    today = date.today()
    if parsed > today:
        abort(400)

    # Must be within 7 days of today
    if (today - parsed).days > 7:
        abort(400)

    try:
        with get_db(immediate=True) as conn:
            toggle_completion(conn, habit_id, target_date)
    except sqlite3.IntegrityError:
        abort(404)

    week_start = request.args.get("week", (today - timedelta(days=today.weekday())).isoformat())
    return redirect(url_for("habits.calendar", week=week_start) + f"#habit-{habit_id}")


@habits_bp.route("/calendar")
def calendar():
    today = date.today()
    week_param = request.args.get("week")
    if week_param:
        try:
            week_start = date.fromisoformat(week_param)
        except ValueError:
            week_start = today - timedelta(days=today.weekday())
    else:
        week_start = today - timedelta(days=today.weekday())

    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    week_end = week_dates[-1]

    with get_db() as conn:
        habits = get_all_habits(conn)
        completions = {}
        for habit in habits:
            completions[habit["id"]] = get_completions_for_week(
                conn, habit["id"], week_start.isoformat(), week_end.isoformat()
            )

    prev_week = (week_start - timedelta(days=7)).isoformat()
    next_week = (week_start + timedelta(days=7)).isoformat()

    return render_template(
        "calendar.html",
        habits=habits,
        week_dates=week_dates,
        completions=completions,
        current_week_start=week_start,
        prev_week=prev_week,
        next_week=next_week,
        today=today,
    )
