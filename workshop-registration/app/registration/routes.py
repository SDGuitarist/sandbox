import os
import re
import threading
import uuid
from flask import Blueprint, jsonify, request
from square import Square
from square.environment import SquareEnvironment
from app import limiter
from app.db import get_db
from app.models import (
    register_attendee,
    get_registrant,
    get_registrant_by_email,
    update_status,
    get_paid_count,
)
from app.supabase_sync import sync_registrant
from app.email import send_email

registration_bp = Blueprint("registration", __name__, url_prefix="/api")

VALID_ROLES = {"Writer", "Director", "Composer", "Post-Production", "Student", "Other"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

square_client = Square(
    token=os.environ.get("SQUARE_ACCESS_TOKEN"),
    environment=SquareEnvironment.SANDBOX,
)


def create_checkout_link(registrant_id: int, email: str) -> tuple[str, str]:
    """Create a Square Payment Link. Returns (checkout_url, order_id)."""
    response = square_client.checkout.payment_links.create(
        idempotency_key=str(uuid.uuid4()),
        quick_pay={
            "name": "Amplify AI Workshop - May 30, 2026",
            "price_money": {
                "amount": int(os.environ.get("WORKSHOP_PRICE_CENTS", 17500)),
                "currency": "USD",
            },
            "location_id": os.environ.get("SQUARE_LOCATION_ID"),
        },
        checkout_options={
            "redirect_url": f"{os.environ.get('SQUARE_REDIRECT_BASE', 'http://localhost:3000')}/register/success?registrant_id={registrant_id}",
        },
        pre_populated_data={"buyer_email": email},
        payment_note=f"registrant:{registrant_id}",
    )
    return response.payment_link.url, response.payment_link.order_id


@registration_bp.route("/register", methods=["POST"])
@limiter.limit("5 per minute")
def register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON", "code": "VALIDATION_FAILED"}), 400

    name = data.get("name", "")
    email = data.get("email", "")
    role = data.get("role", "")

    if not isinstance(name, str):
        return jsonify({"error": "name must be a string", "code": "VALIDATION_FAILED"}), 400
    name = name.strip()
    if not name or len(name) > 100:
        return jsonify({"error": "name is required and must be 1-100 characters", "code": "VALIDATION_FAILED"}), 400

    if not isinstance(email, str):
        return jsonify({"error": "email must be a string", "code": "VALIDATION_FAILED"}), 400
    email = email.strip().lower()
    if not email or not EMAIL_RE.match(email):
        return jsonify({"error": "A valid email is required", "code": "VALIDATION_FAILED"}), 400

    if not isinstance(role, str):
        return jsonify({"error": "role must be a string", "code": "VALIDATION_FAILED"}), 400
    if role not in VALID_ROLES:
        return jsonify({"error": f"role must be one of: {', '.join(sorted(VALID_ROLES))}", "code": "VALIDATION_FAILED"}), 400

    capacity = int(os.environ.get("WORKSHOP_CAPACITY", 35))

    with get_db() as conn:
        existing = get_registrant_by_email(conn, email)

        if existing:
            status = existing["status"]

            if status == "paid":
                return jsonify({"error": "Already registered", "code": "DUPLICATE_EMAIL"}), 409

            if status == "pending_payment":
                checkout_url, _ = create_checkout_link(existing["id"], email)
                return jsonify({
                    "error": "Registration pending payment",
                    "code": "DUPLICATE_EMAIL",
                    "checkout_url": checkout_url,
                }), 409

            if status == "waitlisted":
                return jsonify({
                    "error": "Already on waitlist",
                    "code": "DUPLICATE_EMAIL",
                    "queue_position": existing["queue_position"],
                }), 409

            registrant_id = existing["id"]
            paid_count = get_paid_count(conn)

            if paid_count < capacity:
                update_status(conn, registrant_id, "pending_payment")
                checkout_url, order_id = create_checkout_link(registrant_id, email)
                conn.execute(
                    "UPDATE registrants SET name=?, role=?, square_order_id=? WHERE id=?",
                    (name, role, order_id, registrant_id),
                )
                conn.commit()
                sync_registrant(registrant_id)
                return jsonify({
                    "registrant_id": registrant_id,
                    "status": "pending_payment",
                    "checkout_url": checkout_url,
                    "queue_position": None,
                }), 201
            else:
                update_status(conn, registrant_id, "waitlisted")
                conn.execute(
                    "UPDATE registrants SET name=?, role=? WHERE id=?",
                    (name, role, registrant_id),
                )
                conn.commit()
                updated = get_registrant(conn, registrant_id)
                threading.Thread(
                    target=send_email,
                    args=(registrant_id, "waitlist_confirmation"),
                    daemon=True,
                ).start()
                sync_registrant(registrant_id)
                return jsonify({
                    "registrant_id": registrant_id,
                    "status": "waitlisted",
                    "checkout_url": None,
                    "queue_position": updated["queue_position"],
                }), 201

        paid_count = get_paid_count(conn)
        rid = register_attendee(conn, name, email, role)

        if paid_count < capacity:
            update_status(conn, rid, "pending_payment")
            checkout_url, order_id = create_checkout_link(rid, email)
            conn.execute(
                "UPDATE registrants SET square_order_id=? WHERE id=?",
                (order_id, rid),
            )
            conn.commit()
            sync_registrant(rid)
            return jsonify({
                "registrant_id": rid,
                "status": "pending_payment",
                "checkout_url": checkout_url,
                "queue_position": None,
            }), 201
        else:
            update_status(conn, rid, "waitlisted")
            registrant = get_registrant(conn, rid)
            threading.Thread(
                target=send_email,
                args=(rid, "waitlist_confirmation"),
                daemon=True,
            ).start()
            sync_registrant(rid)
            return jsonify({
                "registrant_id": rid,
                "status": "waitlisted",
                "checkout_url": None,
                "queue_position": registrant["queue_position"],
            }), 201
