import threading

from flask import Blueprint

from app.email import send_email
from app.models import get_next_waitlisted
from app.registration.routes import create_checkout_link
from app.supabase_sync import sync_registrant

waitlist_bp = Blueprint('waitlist', __name__, url_prefix="/api")


def try_promote_next(conn):
    """Promote next waitlisted registrant. Handles checkout link + email internally."""
    next_candidate = get_next_waitlisted(conn)
    if next_candidate is None:
        return

    cursor = conn.execute(
        "UPDATE registrants SET status = 'pending_payment', queue_position = NULL "
        "WHERE id = ? AND status = 'waitlisted'",
        (next_candidate["id"],),
    )
    if cursor.rowcount == 0:
        return  # Another promotion claimed it

    promoted = conn.execute(
        "SELECT id, email FROM registrants WHERE id = ?", (next_candidate["id"],)
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
