import io
import csv
from flask import render_template, session, Response
from app.db import get_db
from app.helpers import login_required
from . import bp


# ---------------------------------------------------------------------------
# Query helpers (FC17: extract shared boilerplate)
# ---------------------------------------------------------------------------

def _revenue_by_month_data(db, user_id):
    """Return list of (month, total_cents) rows."""
    rows = db.execute(
        """
        SELECT strftime('%%Y-%%m', p.payment_date) AS month,
               SUM(p.amount_cents) AS total_cents
          FROM payments p
         WHERE p.user_id = ?
         GROUP BY month
         ORDER BY month
        """,
        (user_id,),
    ).fetchall()
    return rows


def _revenue_by_client_data(db, user_id):
    """Return list of (client_name, total_cents) rows ordered by total DESC."""
    rows = db.execute(
        """
        SELECT c.name AS client_name,
               SUM(p.amount_cents) AS total_cents
          FROM payments p
          JOIN invoices i ON p.invoice_id = i.id
          JOIN clients c ON i.client_id = c.id
         WHERE p.user_id = ?
         GROUP BY c.id
         ORDER BY total_cents DESC
        """,
        (user_id,),
    ).fetchall()
    return rows


def _aging_data(db, user_id):
    """Return aging buckets: list of dicts with bucket, count, total_cents."""
    buckets = [
        ("Current (0-30 days)", "due_date >= date('now', '-30 days')"),
        ("31-60 days", "due_date BETWEEN date('now', '-60 days') AND date('now', '-31 days')"),
        ("61-90 days", "due_date BETWEEN date('now', '-90 days') AND date('now', '-61 days')"),
        ("90+ days", "due_date < date('now', '-90 days')"),
    ]
    results = []
    for label, condition in buckets:
        row = db.execute(
            f"""
            SELECT COUNT(*) AS cnt,
                   COALESCE(SUM(total_cents), 0) AS total_cents
              FROM invoices
             WHERE user_id = ?
               AND status IN ('sent', 'viewed', 'overdue')
               AND {condition}
            """,
            (user_id,),
        ).fetchone()
        results.append({
            "bucket": label,
            "count": row["cnt"],
            "total_cents": row["total_cents"],
        })
    return results


def _forecast_data(db, user_id):
    """Return list of (month, expected_cents) rows for open deals."""
    rows = db.execute(
        """
        SELECT strftime('%%Y-%%m', expected_close_date) AS month,
               SUM(value_cents * probability / 100) AS expected_cents
          FROM deals
         WHERE user_id = ?
           AND expected_close_date IS NOT NULL
         GROUP BY month
         ORDER BY month
        """,
        (user_id,),
    ).fetchall()
    return rows


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.route('/')
@login_required
def index():
    return render_template('reports/index.html')


@bp.route('/revenue-by-month')
@login_required
def revenue_by_month():
    with get_db() as db:
        rows = _revenue_by_month_data(db, session['user_id'])
    return render_template('reports/revenue_by_month.html', rows=rows)


@bp.route('/revenue-by-client')
@login_required
def revenue_by_client():
    with get_db() as db:
        rows = _revenue_by_client_data(db, session['user_id'])
    return render_template('reports/revenue_by_client.html', rows=rows)


@bp.route('/aging')
@login_required
def aging():
    with get_db() as db:
        buckets = _aging_data(db, session['user_id'])
    return render_template('reports/aging.html', buckets=buckets)


@bp.route('/forecast')
@login_required
def forecast():
    with get_db() as db:
        rows = _forecast_data(db, session['user_id'])
    return render_template('reports/forecast.html', rows=rows)


@bp.route('/export/<report_type>')
@login_required
def export_csv(report_type):
    user_id = session['user_id']
    output = io.StringIO()
    writer = csv.writer(output)

    with get_db() as db:
        if report_type == 'revenue_by_month':
            writer.writerow(['Month', 'Total'])
            for row in _revenue_by_month_data(db, user_id):
                writer.writerow([row['month'], f"{row['total_cents'] / 100:.2f}"])

        elif report_type == 'revenue_by_client':
            writer.writerow(['Client', 'Total'])
            for row in _revenue_by_client_data(db, user_id):
                writer.writerow([row['client_name'], f"{row['total_cents'] / 100:.2f}"])

        elif report_type == 'aging':
            writer.writerow(['Bucket', 'Count', 'Total'])
            for bucket in _aging_data(db, user_id):
                writer.writerow([
                    bucket['bucket'],
                    bucket['count'],
                    f"{bucket['total_cents'] / 100:.2f}",
                ])

        elif report_type == 'forecast':
            writer.writerow(['Month', 'Expected Revenue'])
            for row in _forecast_data(db, user_id):
                writer.writerow([row['month'], f"{row['expected_cents'] / 100:.2f}"])

        else:
            return "Invalid report type", 404

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={report_type}.csv'},
    )
