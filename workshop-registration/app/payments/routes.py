import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.db import get_db
from app.email import send_email
from app.models import get_registrant, update_status
from app.supabase_sync import sync_registrant
from app.waitlist.routes import try_promote_next
from app.webhooks import verify_square_signature

logger = logging.getLogger(__name__)

payments_bp = Blueprint("payments", __name__, url_prefix="/api")


@payments_bp.route("/webhooks/square", methods=["POST"])
def square_webhook():
    body = request.get_data(as_text=True)
    signature = request.headers.get("x-square-hmacsha256-signature", "")

    if not verify_square_signature(body, signature):
        return jsonify({"error": "Forbidden", "code": "INVALID_SIGNATURE"}), 403

    try:
        event = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return "", 200

    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO webhook_events (square_event_id, event_type, payload) VALUES (?, ?, ?)",
                (event["event_id"], event["type"], json.dumps(event)),
            )
        except sqlite3.IntegrityError:
            return "", 200

        try:
            if event["type"] == "payment.updated":
                _handle_payment_updated(conn, event)
            elif event["type"] == "refund.created":
                _handle_refund_created(conn, event)
        except Exception:
            logger.exception("Error processing webhook event %s", event.get("event_id"))

    return "", 200


def _handle_payment_updated(conn, event):
    payment = event["data"]["object"]["payment"]
    status = payment["status"]

    if status == "COMPLETED":
        expected = int(os.environ.get("WORKSHOP_PRICE_CENTS", 17500))
        actual = payment["amount_money"]["amount"]
        if actual != expected:
            logger.warning(
                "Amount mismatch: expected %d, got %d for payment %s",
                expected,
                actual,
                payment["id"],
            )
            return

        registrant = get_registrant(conn, square_order_id=payment["order_id"])
        if registrant is None:
            logger.warning(
                "No registrant found for order_id %s", payment["order_id"]
            )
            return

        registrant_id = registrant["id"]
        update_status(
            conn,
            registrant_id,
            "paid",
            square_payment_id=payment["id"],
            paid_at=datetime.now(timezone.utc).isoformat(),
        )
        sync_registrant(registrant_id)
        threading.Thread(
            target=send_email, args=(registrant_id, "confirmation"), daemon=True
        ).start()

    elif status == "FAILED":
        registrant = get_registrant(conn, square_order_id=payment["order_id"])
        if registrant is None:
            logger.warning(
                "No registrant found for order_id %s", payment["order_id"]
            )
            return

        registrant_id = registrant["id"]
        update_status(conn, registrant_id, "payment_failed")
        sync_registrant(registrant_id)
        threading.Thread(
            target=send_email, args=(registrant_id, "payment_failed"), daemon=True
        ).start()


def _handle_refund_created(conn, event):
    refund = event["data"]["object"]["refund"]
    registrant = get_registrant(conn, square_order_id=refund["order_id"])
    if registrant is None:
        logger.warning("No registrant found for order_id %s", refund["order_id"])
        return

    registrant_id = registrant["id"]
    update_status(
        conn,
        registrant_id,
        "cancelled",
        cancelled_at=datetime.now(timezone.utc).isoformat(),
    )
    sync_registrant(registrant_id)
    try_promote_next(conn)
