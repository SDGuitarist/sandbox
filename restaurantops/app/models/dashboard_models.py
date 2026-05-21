"""Dashboard read-only queries for the main dashboard page."""

import sqlite3


def get_dashboard_stats(conn: sqlite3.Connection) -> dict:
    """Return summary statistics for the dashboard.

    Returns a plain dict (not a Row) with these keys:
        active_orders      -- int: orders not closed/cancelled today
        low_stock_count    -- int: ingredients below their threshold
        todays_reservations -- int: non-cancelled reservations for today
        todays_revenue_cents -- int: sum of total_cents for closed orders today
        staff_on_shift     -- int: shifts scheduled for today

    All date comparisons use date('now') so the DB clock decides "today".
    Read-only -- does NOT commit.
    """
    # Active orders: any order whose status is still in-progress
    row = conn.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM orders
        WHERE status NOT IN ('closed', 'cancelled')
        """
    ).fetchone()
    active_orders = row["cnt"] if row else 0

    # Low stock: ingredients whose current_stock is below their threshold
    row = conn.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM inventory
        JOIN ingredients ON ingredients.id = inventory.ingredient_id
        WHERE inventory.current_stock < ingredients.low_stock_threshold
        """
    ).fetchone()
    low_stock_count = row["cnt"] if row else 0

    # Today's reservations (exclude cancelled / no-show)
    row = conn.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM reservations
        WHERE reservation_date = date('now')
          AND status NOT IN ('cancelled', 'no_show')
        """
    ).fetchone()
    todays_reservations = row["cnt"] if row else 0

    # Today's revenue: sum of closed orders created today
    row = conn.execute(
        """
        SELECT COALESCE(SUM(total_cents), 0) AS total
        FROM orders
        WHERE status = 'closed'
          AND date(created_at) = date('now')
        """
    ).fetchone()
    todays_revenue_cents = row["total"] if row else 0

    # Staff on shift today
    row = conn.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM shifts
        WHERE shift_date = date('now')
        """
    ).fetchone()
    staff_on_shift = row["cnt"] if row else 0

    return {
        "active_orders": active_orders,
        "low_stock_count": low_stock_count,
        "todays_reservations": todays_reservations,
        "todays_revenue_cents": todays_revenue_cents,
        "staff_on_shift": staff_on_shift,
    }


def get_todays_specials(conn: sqlite3.Connection) -> list:
    """Return today's active specials.

    A special is active when:
        - is_active = 1
        - start_date <= date('now')
        - end_date   >= date('now')

    Returns a list of sqlite3.Row objects.
    Read-only -- does NOT commit.
    """
    rows = conn.execute(
        """
        SELECT *
        FROM specials
        WHERE is_active = 1
          AND start_date <= date('now')
          AND end_date   >= date('now')
        ORDER BY name
        """
    ).fetchall()
    return rows
