import html
import os
import time
import logging

import resend

from app.db import get_db
from app.models import get_registrant

logger = logging.getLogger(__name__)

resend.api_key = os.environ.get("RESEND_API_KEY", "")

FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "Amplify AI <noreply@amplifyai.to>")

TEMPLATES = {
    "confirmation": {
        "subject": "You're registered! Amplify AI Workshop - May 30",
        "html": (
            '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">'
            "<h2>Welcome, {name}!</h2>"
            "<p>You're officially registered for the <strong>Amplify AI Workshop</strong>.</p>"
            '<table style="margin:20px 0;border-collapse:collapse;">'
            '<tr><td style="padding:8px 16px 8px 0;font-weight:bold;">Date:</td><td style="padding:8px 0;">{workshop_date}</td></tr>'
            '<tr><td style="padding:8px 16px 8px 0;font-weight:bold;">Time:</td><td style="padding:8px 0;">{time}</td></tr>'
            '<tr><td style="padding:8px 16px 8px 0;font-weight:bold;">Location:</td><td style="padding:8px 0;">{location}</td></tr>'
            "</table>"
            "<p>We look forward to seeing you there!</p>"
            "</div>"
        ),
    },
    "reminder_7d": {
        "subject": "One week until the Amplify AI Workshop",
        "html": (
            '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">'
            "<h2>Hi {name},</h2>"
            "<p>Just a reminder — the <strong>Amplify AI Workshop</strong> is one week away!</p>"
            '<table style="margin:20px 0;border-collapse:collapse;">'
            '<tr><td style="padding:8px 16px 8px 0;font-weight:bold;">Date:</td><td style="padding:8px 0;">{workshop_date}</td></tr>'
            '<tr><td style="padding:8px 16px 8px 0;font-weight:bold;">Time:</td><td style="padding:8px 0;">{time}</td></tr>'
            '<tr><td style="padding:8px 16px 8px 0;font-weight:bold;">Location:</td><td style="padding:8px 0;">{location}</td></tr>'
            "</table>"
            "<p>See you soon!</p>"
            "</div>"
        ),
    },
    "reminder_1d": {
        "subject": "Tomorrow! Amplify AI Workshop",
        "html": (
            '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">'
            "<h2>Hi {name},</h2>"
            "<p>The <strong>Amplify AI Workshop</strong> is <strong>tomorrow</strong>!</p>"
            '<table style="margin:20px 0;border-collapse:collapse;">'
            '<tr><td style="padding:8px 16px 8px 0;font-weight:bold;">Date:</td><td style="padding:8px 0;">{workshop_date}</td></tr>'
            '<tr><td style="padding:8px 16px 8px 0;font-weight:bold;">Time:</td><td style="padding:8px 0;">{time}</td></tr>'
            '<tr><td style="padding:8px 16px 8px 0;font-weight:bold;">Location:</td><td style="padding:8px 0;">{location}</td></tr>'
            "</table>"
            "<p>We can't wait to see you!</p>"
            "</div>"
        ),
    },
    "post_workshop": {
        "subject": "Thank you for attending!",
        "html": (
            '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">'
            "<h2>Thank you, {name}!</h2>"
            "<p>We appreciate you attending the <strong>Amplify AI Workshop</strong>. "
            "We hope you found it valuable.</p>"
            "<p>Stay tuned for future events!</p>"
            "</div>"
        ),
    },
    "waitlist_confirmation": {
        "subject": "You're on the waitlist (#{queue_position})",
        "html": (
            '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">'
            "<h2>Hi {name},</h2>"
            "<p>You've been added to the waitlist for the <strong>Amplify AI Workshop</strong>. "
            "Your current position is <strong>#{queue_position}</strong>.</p>"
            "<p>We'll notify you as soon as a spot opens up.</p>"
            "</div>"
        ),
    },
    "waitlist_promotion": {
        "subject": "A spot opened up! Complete your registration",
        "html": (
            '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">'
            "<h2>Great news, {name}!</h2>"
            "<p>A spot has opened up for the <strong>Amplify AI Workshop</strong>.</p>"
            "<p>Complete your registration now:</p>"
            '<p><a href="{checkout_url}" style="display:inline-block;padding:12px 24px;'
            "background-color:#4F46E5;color:#ffffff;text-decoration:none;"
            'border-radius:6px;font-weight:bold;">Complete Registration</a></p>'
            "</div>"
        ),
    },
    "payment_failed": {
        "subject": "Payment issue with your registration",
        "html": (
            '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">'
            "<h2>Hi {name},</h2>"
            "<p>There was an issue processing your payment for the "
            "<strong>Amplify AI Workshop</strong>.</p>"
            "<p>Please try again:</p>"
            '<p><a href="{checkout_url}" style="display:inline-block;padding:12px 24px;'
            "background-color:#4F46E5;color:#ffffff;text-decoration:none;"
            'border-radius:6px;font-weight:bold;">Retry Payment</a></p>'
            "</div>"
        ),
    },
}

WORKSHOP_DATE = "May 30, 2026"
WORKSHOP_TIME = "10:00 AM PDT"
WORKSHOP_LOCATION = "Amplify AI Studio, Los Angeles"


def _build_checkout_url(registrant):
    base = os.environ.get("SQUARE_REDIRECT_BASE", "http://localhost:3000")
    return f"{base}/register"


def send_email(registrant_id: int, template_type: str) -> bool:
    if template_type not in TEMPLATES:
        logger.error("Unknown template_type: %s", template_type)
        return False

    # --- Phase 1: Read DB, build email content, then close connection ---
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM email_log WHERE registrant_id = ? AND template_type = ? "
            "AND sent_at > datetime('now', '-24 hours') AND status = 'sent'",
            (registrant_id, template_type),
        ).fetchone()
        if row:
            return True

        reg = get_registrant(conn, registrant_id)
        if reg is None:
            logger.error("Registrant %d not found", registrant_id)
            return False

        # Copy registrant data we need so we don't depend on the connection
        email_to = reg["email"]

        template = TEMPLATES[template_type]
        variables = {
            "name": html.escape(reg["name"]),
            "workshop_date": WORKSHOP_DATE,
            "time": WORKSHOP_TIME,
            "location": WORKSHOP_LOCATION,
        }

        if template_type == "waitlist_confirmation":
            variables["queue_position"] = str(reg["queue_position"])

        if template_type in ("waitlist_promotion", "payment_failed"):
            variables["checkout_url"] = _build_checkout_url(reg)

        subject = template["subject"].format(**variables)
        html = template["html"].format(**variables)
    # Connection is now closed -- safe to do network I/O

    # --- Phase 2: Send email via Resend API (no DB connection held) ---
    backoff = [1, 2, 4]
    last_error = None
    message_id = ""
    send_succeeded = False

    for attempt, delay in enumerate(backoff):
        try:
            result = resend.Emails.send(
                {
                    "from": FROM_EMAIL,
                    "to": email_to,
                    "subject": subject,
                    "html": html,
                }
            )
            message_id = result.get("id", "") if isinstance(result, dict) else getattr(result, "id", "")
            send_succeeded = True
            break
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Email send attempt %d failed for registrant %d: %s",
                attempt + 1,
                registrant_id,
                exc,
            )
            if attempt < len(backoff) - 1:
                time.sleep(delay)

    # --- Phase 3: Log result to DB with a new connection ---
    with get_db() as conn:
        if send_succeeded:
            conn.execute(
                "INSERT INTO email_log (registrant_id, template_type, resend_message_id, status, sent_at) "
                "VALUES (?, ?, ?, 'sent', datetime('now'))",
                (registrant_id, template_type, message_id),
            )
            conn.commit()
            return True
        else:
            conn.execute(
                "INSERT INTO email_log (registrant_id, template_type, resend_message_id, status, sent_at) "
                "VALUES (?, ?, '', 'failed', datetime('now'))",
                (registrant_id, template_type),
            )
            conn.commit()
            logger.error(
                "All retries exhausted for registrant %d, template %s: %s",
                registrant_id,
                template_type,
                last_error,
            )
            return False
