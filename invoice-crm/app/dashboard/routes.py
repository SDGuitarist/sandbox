from flask import render_template, session, flash
from app.db import get_db
from app.helpers import login_required
from app.recurring.routes import generate_due_invoices
from . import bp


@bp.route('/')
@login_required
def index():
    with get_db() as db:
        user_id = session['user_id']

        # 1. Generate recurring invoices
        generated = generate_due_invoices(db, user_id)
        if generated > 0:
            db.commit()
            flash(f'{generated} recurring invoice(s) generated.', 'info')

        # 2. Update overdue invoices
        db.execute("""
            UPDATE invoices SET status = 'overdue', updated_at = datetime('now')
            WHERE user_id = ? AND status IN ('sent', 'viewed') AND due_date < date('now')
        """, (user_id,))
        db.commit()

        # 3. Query dashboard data

        # Revenue this month
        revenue_this_month = db.execute("""
            SELECT COALESCE(SUM(amount_cents), 0)
            FROM payments
            WHERE user_id = ? AND strftime('%Y-%m', payment_date) = strftime('%Y-%m', 'now')
        """, (user_id,)).fetchone()[0]

        # Revenue last month
        revenue_last_month = db.execute("""
            SELECT COALESCE(SUM(amount_cents), 0)
            FROM payments
            WHERE user_id = ? AND strftime('%Y-%m', payment_date) = strftime('%Y-%m', 'now', '-1 month')
        """, (user_id,)).fetchone()[0]

        # Revenue YTD
        revenue_ytd = db.execute("""
            SELECT COALESCE(SUM(amount_cents), 0)
            FROM payments
            WHERE user_id = ? AND strftime('%Y', payment_date) = strftime('%Y', 'now')
        """, (user_id,)).fetchone()[0]

        # Outstanding (sent + viewed)
        outstanding = db.execute("""
            SELECT COALESCE(SUM(total_cents), 0)
            FROM invoices
            WHERE user_id = ? AND status IN ('sent', 'viewed')
        """, (user_id,)).fetchone()[0]

        # Overdue total
        overdue_total = db.execute("""
            SELECT COALESCE(SUM(total_cents), 0)
            FROM invoices
            WHERE user_id = ? AND status = 'overdue'
        """, (user_id,)).fetchone()[0]

        # Recent invoices (last 10)
        recent_invoices = db.execute("""
            SELECT i.*, c.name AS client_name
            FROM invoices i
            LEFT JOIN clients c ON i.client_id = c.id
            WHERE i.user_id = ?
            ORDER BY i.created_at DESC
            LIMIT 10
        """, (user_id,)).fetchall()

        # Overdue invoices
        overdue_invoices = db.execute("""
            SELECT i.*, c.name AS client_name
            FROM invoices i
            LEFT JOIN clients c ON i.client_id = c.id
            WHERE i.user_id = ? AND i.status = 'overdue'
            ORDER BY i.due_date ASC
        """, (user_id,)).fetchall()

        # Pipeline value by stage
        pipeline_stages = db.execute("""
            SELECT stage, COUNT(*) AS deal_count, COALESCE(SUM(value_cents), 0) AS total_value
            FROM deals
            WHERE user_id = ?
            GROUP BY stage
            ORDER BY CASE stage
                WHEN 'lead' THEN 1
                WHEN 'qualified' THEN 2
                WHEN 'proposal' THEN 3
                WHEN 'negotiation' THEN 4
                WHEN 'won' THEN 5
                WHEN 'lost' THEN 6
            END
        """, (user_id,)).fetchall()

        # Upcoming recurring invoices (next 7 days)
        upcoming_recurring = db.execute("""
            SELECT i.*, c.name AS client_name
            FROM invoices i
            LEFT JOIN clients c ON i.client_id = c.id
            WHERE i.user_id = ? AND i.is_recurring = 1
              AND i.next_recurrence_date BETWEEN date('now') AND date('now', '+7 days')
            ORDER BY i.next_recurrence_date ASC
        """, (user_id,)).fetchall()

        # Top 5 clients by revenue
        top_clients = db.execute("""
            SELECT c.id, c.name, COALESCE(SUM(p.amount_cents), 0) AS total_revenue
            FROM payments p
            JOIN invoices i ON p.invoice_id = i.id
            JOIN clients c ON i.client_id = c.id
            WHERE p.user_id = ?
            GROUP BY c.id, c.name
            ORDER BY total_revenue DESC
            LIMIT 5
        """, (user_id,)).fetchall()

    return render_template('dashboard/index.html',
                           revenue_this_month=revenue_this_month,
                           revenue_last_month=revenue_last_month,
                           revenue_ytd=revenue_ytd,
                           outstanding=outstanding,
                           overdue_total=overdue_total,
                           recent_invoices=recent_invoices,
                           overdue_invoices=overdue_invoices,
                           pipeline_stages=pipeline_stages,
                           upcoming_recurring=upcoming_recurring,
                           top_clients=top_clients)
