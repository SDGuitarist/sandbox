import threading

from flask import Blueprint

from app.email import send_email
from app.registration.routes import create_checkout_link
from app.supabase_sync import sync_registrant

waitlist_bp = Blueprint('waitlist', __name__, url_prefix="/api")


def try_promote_next(conn):
    """Promote next waitlisted registrant. Handles checkout link + email internally."""
    cursor = conn.execute(
        "UPDATE registrants SET status = 'pending_payment', queue_position = NULL "
        "WHERE id = (SELECT id FROM registrants WHERE status = 'waitlisted' "
        "ORDER BY queue_position ASC LIMIT 1) AND status = 'waitlisted'"
    )
    if cursor.rowcount == 0:
        return

    promoted = conn.execute(
        "SELECT id, email FROM registrants WHERE status = 'pending_payment' "
        "AND queue_position IS NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if promoted is None:
        return

    conn.commit()

    checkout_url, order_id = create_checkout_link(promoted["id"], promoted["email"])
    conn.execute(
        "UPDATE registrants SET square_order_id = ? WHERE id = ?",
        (order_id, promoted["id"])
    )
    conn.commit()

    sync_registrant(promoted["id"])
    threading.Thread(
        target=send_email,
        args=(promoted["id"], "waitlist_promotion"),
        daemon=True
    ).start()
