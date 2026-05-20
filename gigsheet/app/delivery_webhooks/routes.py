"""Delivery webhooks blueprint -- receives SendGrid event webhooks."""

import json
import logging

from flask import Blueprint, request, jsonify

from app import csrf, limiter
from app.db import get_db
from app.models import (
    record_email_event,
    update_recipient_status,
    increment_campaign_counter,
    create_notification,
)

logger = logging.getLogger(__name__)

delivery_webhooks_bp = Blueprint('delivery_webhooks', __name__)

# CSRF MUST be exempted -- SendGrid cannot provide CSRF tokens
csrf.exempt(delivery_webhooks_bp)

# Map SendGrid event names to our internal event types.
# Keys are SendGrid's webhook event strings; values are what we store.
EVENT_TYPE_MAP = {
    'delivered': 'delivered',
    'open': 'opened',
    'click': 'clicked',
    'bounce': 'bounced',
    'dropped': 'dropped',
    'unsubscribe': 'unsubscribed',
}

# Map our internal event types to campaign counter column names.
COUNTER_MAP = {
    'delivered': 'delivered_count',
    'opened': 'opened_count',
    'clicked': 'clicked_count',
    'bounced': 'bounced_count',
}


@delivery_webhooks_bp.route('/sendgrid', methods=['POST'])
@limiter.limit('100/minute')
def handle():
    """Process a batch of SendGrid webhook events.

    SendGrid posts a JSON array of event objects.  Each object contains at
    minimum: ``event`` (type), ``email``, ``sg_message_id``, ``timestamp``.
    We normalise the event type, look up the matching campaign_recipient by
    message_id, then record the event, update recipient status, and bump the
    campaign counter.  A single commit covers the whole batch.
    """
    events = request.get_json(silent=True)
    if not isinstance(events, list):
        return jsonify(status='error', message='Expected JSON array'), 400

    db = get_db()
    processed = 0

    for event in events:
        sg_event = event.get('event')
        if not sg_event:
            continue

        # Only handle events we recognise
        internal_type = EVENT_TYPE_MAP.get(sg_event)
        if internal_type is None:
            continue

        # sg_message_id may include angle-bracket filter suffix (e.g.
        # "abc123.filter0001...").  Strip the ".filter" part if present.
        raw_message_id = event.get('sg_message_id', '')
        message_id = raw_message_id.split('.filter')[0] if raw_message_id else ''
        if not message_id:
            continue

        # Look up recipient by message_id
        recipient = db.execute(
            'SELECT id, campaign_id FROM campaign_recipients WHERE message_id = ?',
            (message_id,),
        ).fetchone()
        if recipient is None:
            logger.warning(
                'Webhook event %s for unknown message_id %s',
                sg_event,
                message_id,
            )
            continue

        recipient_id = recipient['id']
        campaign_id = recipient['campaign_id']

        # Build optional metadata from the raw event
        metadata = json.dumps({
            k: event[k]
            for k in ('email', 'timestamp', 'url', 'reason', 'status', 'type')
            if k in event
        })

        # Record the email event (does NOT commit)
        record_email_event(db, campaign_id, recipient_id, message_id, internal_type, metadata)

        # Update recipient status (does NOT commit)
        update_recipient_status(db, recipient_id, internal_type)

        # Increment campaign counter if this event type has one (does NOT commit)
        counter_name = COUNTER_MAP.get(internal_type)
        if counter_name:
            increment_campaign_counter(db, campaign_id, counter_name)

        # For bounces/drops create a notification so the workspace owner knows
        if internal_type in ('bounced', 'dropped'):
            # Look up the campaign's workspace to notify the owner
            campaign = db.execute(
                'SELECT workspace_id, created_by_user_id, name FROM campaigns WHERE id = ?',
                (campaign_id,),
            ).fetchone()
            if campaign:
                email_addr = event.get('email', 'unknown')
                create_notification(
                    db,
                    campaign['workspace_id'],
                    campaign['created_by_user_id'],
                    f"Email {internal_type}: {email_addr} in campaign \"{campaign['name']}\"",
                    link=f"/delivery/{campaign_id}",
                )

        processed += 1

    # Single commit for the whole batch
    db.commit()

    logger.info('Processed %d webhook events', processed)
    return jsonify(status='ok'), 200
