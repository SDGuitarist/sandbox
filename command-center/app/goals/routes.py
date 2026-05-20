from datetime import date

from flask import render_template, request, redirect, url_for, flash

from ..db import get_db
from ..decorators import setup_required
from . import bp


@bp.route('/')
@setup_required
def index():
    """Show current month goals with progress bars."""
    current_month = date.today().strftime('%Y-%m')

    with get_db() as db:
        # Get goal row for this month (may not exist yet)
        goal = db.execute(
            "SELECT * FROM goal WHERE month = ?", (current_month,)
        ).fetchone()

        # Get business profile defaults for fallback targets
        profile = db.execute(
            "SELECT monthly_revenue_target, weekly_hours_target, quarterly_revenue_target "
            "FROM business_profile LIMIT 1"
        ).fetchone()

        if goal:
            revenue_target = goal['revenue_target']
            hours_target = goal['hours_target']
        elif profile:
            revenue_target = profile['monthly_revenue_target']
            hours_target = profile['weekly_hours_target'] * 4
        else:
            revenue_target = 0
            hours_target = 0

        # revenue_actual: sum of income for current month (cents)
        row = db.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM income "
            "WHERE strftime('%%Y-%%m', date) = ?",
            (current_month,)
        ).fetchone()
        revenue_actual = row['total'] if row else 0

        # hours_actual: sum of time_entry.minutes for current month
        row = db.execute(
            "SELECT COALESCE(SUM(minutes), 0) AS total FROM time_entry "
            "WHERE strftime('%%Y-%%m', date) = ?",
            (current_month,)
        ).fetchone()
        hours_actual = row['total'] if row else 0

        # quarterly_target: from profile, or monthly * 3 if 0
        if profile and profile['quarterly_revenue_target']:
            quarterly_target = profile['quarterly_revenue_target']
        else:
            quarterly_target = revenue_target * 3

    return render_template(
        'goals/index.html',
        current_month=current_month,
        revenue_target=revenue_target,
        revenue_actual=revenue_actual,
        hours_target=hours_target,
        hours_actual=hours_actual,
        quarterly_target=quarterly_target,
    )


@bp.route('/update', methods=['POST'])
@setup_required
def update():
    """Save monthly revenue target and hours target to goal table."""
    current_month = date.today().strftime('%Y-%m')

    # Money input: form dollars -> integer cents
    revenue_target_str = request.form.get('revenue_target', '0')
    try:
        revenue_target = int(float(revenue_target_str) * 100)
    except (ValueError, TypeError):
        revenue_target = 0

    # Hours target: plain integer hours
    hours_target_str = request.form.get('hours_target', '0')
    try:
        hours_target = int(float(hours_target_str))
    except (ValueError, TypeError):
        hours_target = 0

    with get_db(immediate=True) as db:
        # INSERT OR REPLACE on goal(month) -- month has UNIQUE constraint
        db.execute(
            "INSERT OR REPLACE INTO goal (month, revenue_target, hours_target, revenue_actual, hours_actual) "
            "VALUES (?, ?, ?, "
            "COALESCE((SELECT revenue_actual FROM goal WHERE month = ?), 0), "
            "COALESCE((SELECT hours_actual FROM goal WHERE month = ?), 0))",
            (current_month, revenue_target, hours_target, current_month, current_month),
        )

        # Get the goal id for activity log
        goal_row = db.execute(
            "SELECT id FROM goal WHERE month = ?", (current_month,)
        ).fetchone()
        goal_id = goal_row['id'] if goal_row else 0

        # Activity log entry
        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
            ('updated', 'goal', goal_id, f"Updated goals for {current_month}"),
        )

    flash("Goals updated successfully.", "success")
    return redirect(url_for('goals.index'))


@bp.route('/history')
@setup_required
def history():
    """Show all past goals with live actual values from income/time_entry."""
    with get_db() as db:
        goals = db.execute(
            "SELECT * FROM goal ORDER BY month DESC"
        ).fetchall()

        enriched = []
        for g in goals:
            month = g['month']
            month_end = month + '-32'  # SQLite date comparison trick: any day > 31 works as upper bound
            revenue_actual = db.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM income WHERE strftime('%%Y-%%m', date) = ?",
                (month,)
            ).fetchone()[0]
            hours_actual = db.execute(
                "SELECT COALESCE(SUM(minutes), 0) / 60.0 FROM time_entry WHERE strftime('%%Y-%%m', date) = ?",
                (month,)
            ).fetchone()[0]
            enriched.append({
                'month': month,
                'revenue_target': g['revenue_target'],
                'revenue_actual': revenue_actual,
                'hours_target': g['hours_target'],
                'hours_actual': hours_actual,
            })

    return render_template('goals/history.html', goals=enriched)
