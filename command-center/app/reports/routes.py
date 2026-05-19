import csv
import io

from flask import render_template, request, Response

from ..db import get_db
from ..decorators import setup_required
from . import bp


# ---------------------------------------------------------------------------
# Allowed modules for CSV export.  Keys = URL parameter, values = SQL table.
# ---------------------------------------------------------------------------
EXPORT_MODULES = {
    'contacts': 'contact',
    'companies': 'company',
    'deals': 'deal',
    'projects': 'project',
    'tasks': 'task',
    'time_entries': 'time_entry',
    'income': 'income',
    'expenses': 'expense',
    'notes': 'note',
    'journal': 'journal_entry',
}


# ---------------------------------------------------------------------------
# Reports index — links to every report
# ---------------------------------------------------------------------------
@bp.route('/')
@setup_required
def index():
    return render_template('reports/index.html')


# ---------------------------------------------------------------------------
# Revenue report — monthly revenue grouped from income table
# ---------------------------------------------------------------------------
@bp.route('/revenue')
@setup_required
def revenue_report():
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    client_filter = request.args.get('client', '')

    with get_db() as db:
        # Build the WHERE clause dynamically
        conditions = []
        params = []

        if start_date:
            conditions.append("i.date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("i.date <= ?")
            params.append(end_date)
        if client_filter:
            conditions.append("i.contact_id = ?")
            params.append(int(client_filter))

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        sql = f"""
            SELECT strftime('%Y-%m', i.date) AS month,
                   SUM(i.amount) AS total
            FROM income i
            {where}
            GROUP BY strftime('%Y-%m', i.date)
            ORDER BY month DESC
        """
        rows = db.execute(sql, params).fetchall()

        months = [{'month': r['month'], 'total': r['total']} for r in rows]

        contacts = db.execute(
            "SELECT id, name FROM contact ORDER BY name"
        ).fetchall()

    return render_template(
        'reports/revenue.html',
        months=months,
        start_date=start_date,
        end_date=end_date,
        client_filter=client_filter,
        contacts=contacts,
    )


# ---------------------------------------------------------------------------
# Client report — revenue per client via LEFT JOIN income on contact_id
# ---------------------------------------------------------------------------
@bp.route('/client')
@setup_required
def client_report():
    with get_db() as db:
        rows = db.execute("""
            SELECT c.id, c.name AS contact_name,
                   COALESCE(SUM(i.amount), 0) AS revenue,
                   COUNT(DISTINCT p.id) AS projects,
                   CASE WHEN COUNT(i.id) > 0
                        THEN COALESCE(SUM(i.amount), 0) / COUNT(i.id)
                        ELSE 0 END AS avg_value,
                   MAX(intr.date) AS last_interaction
            FROM contact c
            LEFT JOIN income i ON i.contact_id = c.id
            LEFT JOIN project p ON p.contact_id = c.id
            LEFT JOIN interaction intr ON intr.contact_id = c.id
            GROUP BY c.id
            ORDER BY revenue DESC
        """).fetchall()

        clients = [
            {
                'contact': r['contact_name'],
                'revenue': r['revenue'],
                'projects': r['projects'],
                'avg_value': r['avg_value'],
                'last_interaction': r['last_interaction'],
            }
            for r in rows
        ]

    return render_template('reports/client.html', clients=clients)


# ---------------------------------------------------------------------------
# Time report — by project and by week
# ---------------------------------------------------------------------------
@bp.route('/time')
@setup_required
def time_report():
    with get_db() as db:
        # Time by project
        project_rows = db.execute("""
            SELECT p.name AS project_name,
                   SUM(CASE WHEN te.billable = 1 THEN te.minutes ELSE 0 END) AS billable,
                   SUM(CASE WHEN te.billable = 0 THEN te.minutes ELSE 0 END) AS non_billable,
                   SUM(te.minutes) AS total
            FROM time_entry te
            JOIN project p ON p.id = te.project_id
            GROUP BY te.project_id
            ORDER BY total DESC
        """).fetchall()

        by_project = [
            {
                'project': r['project_name'],
                'billable': r['billable'] or 0,
                'non_billable': r['non_billable'] or 0,
                'total': r['total'] or 0,
            }
            for r in project_rows
        ]

        # Time by week
        week_rows = db.execute("""
            SELECT strftime('%Y-W%W', te.date) AS week,
                   SUM(CASE WHEN te.billable = 1 THEN te.minutes ELSE 0 END) AS billable,
                   SUM(CASE WHEN te.billable = 0 THEN te.minutes ELSE 0 END) AS non_billable,
                   SUM(te.minutes) AS total
            FROM time_entry te
            GROUP BY strftime('%Y-W%W', te.date)
            ORDER BY week DESC
        """).fetchall()

        by_week = [
            {
                'week': r['week'],
                'billable': r['billable'] or 0,
                'non_billable': r['non_billable'] or 0,
                'total': r['total'] or 0,
            }
            for r in week_rows
        ]

        # Totals
        totals = db.execute("""
            SELECT COALESCE(SUM(CASE WHEN billable = 1 THEN minutes ELSE 0 END), 0) AS billable_total,
                   COALESCE(SUM(CASE WHEN billable = 0 THEN minutes ELSE 0 END), 0) AS non_billable_total
            FROM time_entry
        """).fetchone()

        billable_total = totals['billable_total']
        non_billable_total = totals['non_billable_total']

    return render_template(
        'reports/time.html',
        by_project=by_project,
        by_week=by_week,
        billable_total=billable_total,
        non_billable_total=non_billable_total,
    )


# ---------------------------------------------------------------------------
# Pipeline report — win rate, avg deal size, avg days to close, forecast
# ---------------------------------------------------------------------------
@bp.route('/pipeline')
@setup_required
def pipeline_report():
    with get_db() as db:
        # Win rate = COUNT(won) / COUNT(won + lost) * 100
        rate_row = db.execute("""
            SELECT COUNT(CASE WHEN stage = 'won' THEN 1 END) AS won,
                   COUNT(CASE WHEN stage IN ('won', 'lost') THEN 1 END) AS closed
            FROM deal
        """).fetchone()

        won_count = rate_row['won'] or 0
        closed_count = rate_row['closed'] or 0
        win_rate = (won_count / closed_count * 100) if closed_count > 0 else 0.0

        # Average deal size from won deals
        avg_row = db.execute("""
            SELECT COALESCE(AVG(value), 0) AS avg_deal
            FROM deal
            WHERE stage = 'won'
        """).fetchone()
        avg_deal_size = int(avg_row['avg_deal'])

        # Average days to close (won deals only)
        days_row = db.execute("""
            SELECT AVG(
                CAST(julianday(updated_at) - julianday(created_at) AS INTEGER)
            ) AS avg_days
            FROM deal
            WHERE stage = 'won'
        """).fetchone()
        avg_days_to_close = int(days_row['avg_days']) if days_row['avg_days'] else 0

        # Forecast — weighted pipeline value by expected close month
        forecast_rows = db.execute("""
            SELECT strftime('%Y-%m', expected_close_date) AS month,
                   SUM(value * probability_pct / 100) AS weighted_value
            FROM deal
            WHERE stage NOT IN ('won', 'lost')
              AND expected_close_date IS NOT NULL
            GROUP BY strftime('%Y-%m', expected_close_date)
            ORDER BY month
        """).fetchall()

        forecast = [
            {'month': r['month'], 'weighted_value': r['weighted_value'] or 0}
            for r in forecast_rows
        ]

    return render_template(
        'reports/pipeline.html',
        win_rate=win_rate,
        avg_deal_size=avg_deal_size,
        avg_days_to_close=avg_days_to_close,
        forecast=forecast,
    )


# ---------------------------------------------------------------------------
# Utilization report — billable hours / total hours per week
# ---------------------------------------------------------------------------
@bp.route('/utilization')
@setup_required
def utilization_report():
    with get_db() as db:
        # Get the weekly hours target from business_profile
        profile = db.execute(
            "SELECT weekly_hours_target FROM business_profile LIMIT 1"
        ).fetchone()
        weekly_target = profile['weekly_hours_target'] if profile else 40

        rows = db.execute("""
            SELECT strftime('%Y-W%W', date) AS week_start,
                   SUM(CASE WHEN billable = 1 THEN minutes ELSE 0 END) AS billable,
                   SUM(minutes) AS total
            FROM time_entry
            GROUP BY strftime('%Y-W%W', date)
            ORDER BY week_start DESC
        """).fetchall()

        weeks = []
        total_rate = 0.0
        for r in rows:
            billable = r['billable'] or 0
            total = r['total'] or 0
            rate = (billable / total * 100) if total > 0 else 0.0
            total_rate += rate
            weeks.append({
                'week_start': r['week_start'],
                'billable': billable,
                'total': total,
                'rate': round(rate, 1),
                'target': weekly_target * 60,  # convert hours to minutes
            })

        avg_rate = round(total_rate / len(weeks), 1) if weeks else 0.0

    return render_template(
        'reports/utilization.html',
        weeks=weeks,
        avg_rate=avg_rate,
    )


# ---------------------------------------------------------------------------
# Expense report — by category and by month
# ---------------------------------------------------------------------------
@bp.route('/expense')
@setup_required
def expense_report():
    with get_db() as db:
        # By category
        cat_rows = db.execute("""
            SELECT category,
                   SUM(amount) AS total,
                   COUNT(*) AS count
            FROM expense
            GROUP BY category
            ORDER BY total DESC
        """).fetchall()

        by_category = [
            {'category': r['category'], 'total': r['total'] or 0, 'count': r['count']}
            for r in cat_rows
        ]

        # By month
        month_rows = db.execute("""
            SELECT strftime('%Y-%m', date) AS month,
                   SUM(amount) AS total,
                   COUNT(*) AS count
            FROM expense
            GROUP BY strftime('%Y-%m', date)
            ORDER BY month DESC
        """).fetchall()

        by_month = [
            {'month': r['month'], 'total': r['total'] or 0, 'count': r['count']}
            for r in month_rows
        ]

        # Tax-deductible total
        tax_row = db.execute("""
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM expense
            WHERE tax_deductible = 1
        """).fetchone()
        tax_deductible_total = tax_row['total']

    return render_template(
        'reports/expense.html',
        by_category=by_category,
        by_month=by_month,
        tax_deductible_total=tax_deductible_total,
    )


# ---------------------------------------------------------------------------
# CSV export — generic export for any module
# ---------------------------------------------------------------------------
@bp.route('/export/<module>')
@setup_required
def export_csv(module):
    if module not in EXPORT_MODULES:
        return Response("Invalid module", status=400)

    table = EXPORT_MODULES[module]

    with get_db() as db:
        rows = db.execute(f"SELECT * FROM {table}").fetchall()

        output = io.StringIO()
        writer = csv.writer(output)

        if rows:
            # Write header from column names
            writer.writerow(rows[0].keys())
            # Write data rows
            for row in rows:
                writer.writerow(list(row))
        else:
            writer.writerow(["No data"])

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename="{module}.csv"'
        },
    )
