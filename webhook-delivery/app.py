import json
import os
import uuid
from flask import Flask, request, jsonify
from database import get_db, close_db, init_db

app = Flask(__name__)

# Hard timeout (seconds) before a 'delivering' worker is considered stale
WORKER_TIMEOUT_SECONDS = 300
BASE_BACKOFF_SECONDS = 10


@app.teardown_appcontext
def teardown_db(e=None):
    close_db(e)


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'error': 'Method not allowed'}), 405


def webhook_to_dict(row):
    return {
        'id': row['id'],
        'url': row['url'],
        'events': json.loads(row['events']),
        'max_attempts': row['max_attempts'],
        'is_active': bool(row['is_active']),
        'created_at': row['created_at'],
        # secret intentionally omitted from dict — only returned at registration
    }


def delivery_to_dict(row):
    return {
        'id': row['id'],
        'webhook_id': row['webhook_id'],
        'event_type': row['event_type'],
        'payload': json.loads(row['payload']),
        'status': row['status'],
        'attempt_count': row['attempt_count'],
        'max_attempts': row['max_attempts'],
        'next_attempt_at': row['next_attempt_at'],
        'last_error': row['last_error'],
        'worker_id': row['worker_id'],
        'claimed_at': row['claimed_at'],
        'created_at': row['created_at'],
        'completed_at': row['completed_at'],
    }


# ---------------------------------------------------------------------------
# Webhook registration
# ---------------------------------------------------------------------------

@app.post('/webhooks')
def register_webhook():
    data = request.get_json(silent=True) or {}

    url = (data.get('url') or '').strip()
    if not url or not (url.startswith('http://') or url.startswith('https://')):
        return jsonify({'error': 'url must be a valid http:// or https:// URL'}), 400

    secret = (data.get('secret') or '').strip()
    if not secret:
        return jsonify({'error': 'secret is required'}), 400

    events = data.get('events')
    if not events or not isinstance(events, list) or not all(isinstance(e, str) for e in events):
        return jsonify({'error': 'events must be a non-empty list of strings'}), 400

    try:
        max_attempts = int(data.get('max_attempts', 5))
    except (ValueError, TypeError):
        return jsonify({'error': 'max_attempts must be an integer'}), 400
    if max_attempts <= 0:
        return jsonify({'error': 'max_attempts must be > 0'}), 400

    webhook_id = str(uuid.uuid4())
    db = get_db()
    db.execute(
        'INSERT INTO webhooks (id, url, secret, events, max_attempts) VALUES (?, ?, ?, ?, ?)',
        (webhook_id, url, secret, json.dumps(events), max_attempts)
    )
    db.commit()

    row = db.execute('SELECT * FROM webhooks WHERE id=?', (webhook_id,)).fetchone()
    # Return secret once at creation time only
    result = webhook_to_dict(row)
    result['secret'] = row['secret']
    return jsonify(result), 201


@app.get('/webhooks/<webhook_id>')
def get_webhook(webhook_id):
    db = get_db()
    row = db.execute('SELECT * FROM webhooks WHERE id=?', (webhook_id,)).fetchone()
    if row is None:
        return jsonify({'error': 'Webhook not found'}), 404
    # Secret redacted after initial registration
    return jsonify(webhook_to_dict(row)), 200


@app.delete('/webhooks/<webhook_id>')
def delete_webhook(webhook_id):
    db = get_db()
    row = db.execute('SELECT id FROM webhooks WHERE id=?', (webhook_id,)).fetchone()
    if row is None:
        return jsonify({'error': 'Webhook not found'}), 404
    db.execute('UPDATE webhooks SET is_active=0 WHERE id=?', (webhook_id,))
    db.commit()
    return jsonify({'id': webhook_id, 'is_active': False}), 200


# ---------------------------------------------------------------------------
# Event dispatch
# ---------------------------------------------------------------------------

@app.post('/events')
def dispatch_event():
    data = request.get_json(silent=True) or {}

    event_type = (data.get('event_type') or '').strip()
    if not event_type:
        return jsonify({'error': 'event_type is required'}), 400
    if 'payload' not in data:
        return jsonify({'error': 'payload is required'}), 400

    payload_str = json.dumps(data['payload'])
    db = get_db()

    # Find all active webhooks subscribed to this event type
    webhooks = db.execute('SELECT * FROM webhooks WHERE is_active=1').fetchall()
    matching = [w for w in webhooks if event_type in json.loads(w['events'])]

    delivery_ids = []
    for webhook in matching:
        delivery_id = str(uuid.uuid4())
        db.execute(
            '''INSERT INTO deliveries (id, webhook_id, event_type, payload, max_attempts)
               VALUES (?, ?, ?, ?, ?)''',
            (delivery_id, webhook['id'], event_type, payload_str, webhook['max_attempts'])
        )
        delivery_ids.append(delivery_id)

    db.commit()

    return jsonify({
        'event_type': event_type,
        'deliveries_created': len(delivery_ids),
        'delivery_ids': delivery_ids,
    }), 200


# ---------------------------------------------------------------------------
# Delivery worker endpoints
# ---------------------------------------------------------------------------

@app.post('/deliveries/claim')
def claim_delivery():
    data = request.get_json(silent=True) or {}
    worker_id = data.get('worker_id') or str(uuid.uuid4())

    db = get_db()

    # Step 1: Expire stale 'delivering' rows — use claimed_at as the timeout anchor.
    # Retry only if attempt_count+1 < max_attempts (same boundary as fail_delivery).
    db.execute(
        '''UPDATE deliveries SET
               status = CASE WHEN attempt_count + 1 < max_attempts THEN 'pending' ELSE 'failed' END,
               attempt_count = attempt_count + 1,
               next_attempt_at = CASE WHEN attempt_count + 1 < max_attempts
                   THEN datetime('now', '+' || CAST(10 * (1 << attempt_count) AS TEXT) || ' seconds')
                   ELSE next_attempt_at END,
               worker_id = NULL,
               claimed_at = NULL
           WHERE status = 'delivering'
             AND claimed_at IS NOT NULL
             AND CAST((julianday('now') - julianday(claimed_at)) * 86400 AS INTEGER) >= 300'''
    )
    db.commit()

    # Step 2a: Find oldest due pending delivery
    pending = db.execute(
        "SELECT id FROM deliveries WHERE status='pending' AND next_attempt_at <= datetime('now') "
        "ORDER BY next_attempt_at ASC LIMIT 1"
    ).fetchone()

    if pending is None:
        return '', 204

    delivery_id = pending['id']

    # Step 2b: Atomically claim it — rowcount 0 means another worker got it first
    cursor = db.execute(
        "UPDATE deliveries SET status='delivering', worker_id=?, claimed_at=CURRENT_TIMESTAMP "
        "WHERE id=? AND status='pending'",
        (worker_id, delivery_id)
    )
    db.commit()

    if cursor.rowcount == 0:
        return '', 204

    row = db.execute('SELECT * FROM deliveries WHERE id=?', (delivery_id,)).fetchone()
    return jsonify(delivery_to_dict(row)), 200


@app.post('/deliveries/<delivery_id>/complete')
def complete_delivery(delivery_id):
    data = request.get_json(silent=True) or {}
    worker_id = data.get('worker_id')

    db = get_db()
    row = db.execute('SELECT * FROM deliveries WHERE id=?', (delivery_id,)).fetchone()
    if row is None:
        return jsonify({'error': 'Delivery not found'}), 404
    if row['status'] != 'delivering':
        return jsonify({'error': f"Delivery is '{row['status']}', not 'delivering'"}), 409
    if worker_id and row['worker_id'] and worker_id != row['worker_id']:
        return jsonify({'error': 'worker_id does not match the claiming worker'}), 403

    db.execute(
        "UPDATE deliveries SET status='delivered', completed_at=CURRENT_TIMESTAMP WHERE id=?",
        (delivery_id,)
    )
    db.commit()

    row = db.execute('SELECT * FROM deliveries WHERE id=?', (delivery_id,)).fetchone()
    return jsonify(delivery_to_dict(row)), 200


@app.post('/deliveries/<delivery_id>/fail')
def fail_delivery(delivery_id):
    data = request.get_json(silent=True) or {}
    error_msg = data.get('error', '')
    worker_id = data.get('worker_id')

    db = get_db()
    row = db.execute('SELECT * FROM deliveries WHERE id=?', (delivery_id,)).fetchone()
    if row is None:
        return jsonify({'error': 'Delivery not found'}), 404
    if row['status'] != 'delivering':
        return jsonify({'error': f"Delivery is '{row['status']}', not 'delivering'"}), 409
    if worker_id and row['worker_id'] and worker_id != row['worker_id']:
        return jsonify({'error': 'worker_id does not match the claiming worker'}), 403

    attempt_count = row['attempt_count']
    max_attempts = row['max_attempts']

    # attempt_count is 0-indexed; max_attempts is the total number of delivery attempts.
    # After this failure, attempt_count will become attempt_count+1.
    # Retry only if there will still be attempts left (attempt_count+1 < max_attempts).
    if attempt_count + 1 < max_attempts:
        delay = BASE_BACKOFF_SECONDS * (2 ** attempt_count)
        db.execute(
            '''UPDATE deliveries SET
                   status='pending',
                   attempt_count=attempt_count+1,
                   next_attempt_at=datetime('now', ? || ' seconds'),
                   last_error=?,
                   worker_id=NULL,
                   claimed_at=NULL
               WHERE id=?''',
            (f'+{delay}', error_msg, delivery_id)
        )
    else:
        db.execute(
            '''UPDATE deliveries SET status='failed', last_error=?,
               attempt_count=attempt_count+1,
               completed_at=CURRENT_TIMESTAMP, worker_id=NULL, claimed_at=NULL WHERE id=?''',
            (error_msg, delivery_id)
        )
    db.commit()

    row = db.execute('SELECT * FROM deliveries WHERE id=?', (delivery_id,)).fetchone()
    return jsonify(delivery_to_dict(row)), 200


@app.get('/webhooks/<webhook_id>/deliveries')
def list_deliveries(webhook_id):
    db = get_db()
    row = db.execute('SELECT id FROM webhooks WHERE id=?', (webhook_id,)).fetchone()
    if row is None:
        return jsonify({'error': 'Webhook not found'}), 404

    rows = db.execute(
        'SELECT * FROM deliveries WHERE webhook_id=? ORDER BY created_at DESC',
        (webhook_id,)
    ).fetchall()
    return jsonify([delivery_to_dict(r) for r in rows]), 200


if __name__ == '__main__':
    init_db(app)
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug)
