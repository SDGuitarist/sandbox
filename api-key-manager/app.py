import os
import uuid
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from database import get_db, close_db, init_db
from keys import (
    generate_key, generate_salt, hash_key, verify_key,
    display_prefix, lookup_prefix
)

app = Flask(__name__)

WINDOW_SECONDS = 60   # Rate limit window: 1 minute
MAX_NAME_LEN = 255


@app.teardown_appcontext
def teardown_db(e=None):
    close_db(e)


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'error': 'Method not allowed'}), 405


def key_to_dict(row):
    """Serialize a key row — never includes the raw key value or salt."""
    return {
        'id': row['id'],
        'prefix': row['prefix'],
        'name': row['name'],
        'is_active': bool(row['is_active']),
        'rate_limit_rpm': row['rate_limit_rpm'],
        'total_requests': row['total_requests'],
        'last_used_at': row['last_used_at'],
        'created_at': row['created_at'],
        'expires_at': row['expires_at'],
    }


def _normalize_expires_at(raw):
    """Parse and normalize expires_at to SQLite-compatible 'YYYY-MM-DD HH:MM:SS'.
    Returns (normalized_str, error_msg). error_msg is None on success."""
    if raw is None:
        return None, None
    try:
        dt = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S'), None
    except (ValueError, TypeError):
        return None, 'expires_at must be a valid ISO8601 datetime string'


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------

@app.post('/keys')
def create_key():
    data = request.get_json(silent=True) or {}

    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    if len(name) > MAX_NAME_LEN:
        return jsonify({'error': f'name must be {MAX_NAME_LEN} characters or fewer'}), 400

    try:
        rate_limit_rpm = int(data.get('rate_limit_rpm', 60))
    except (ValueError, TypeError):
        return jsonify({'error': 'rate_limit_rpm must be an integer'}), 400
    if rate_limit_rpm < 0:
        return jsonify({'error': 'rate_limit_rpm must be >= 0 (0 = unlimited)'}), 400

    expires_at, err = _normalize_expires_at(data.get('expires_at'))
    if err:
        return jsonify({'error': err}), 400

    # Warn if expires_at is already in the past (UX: key would be immediately invalid)
    if expires_at:
        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        if expires_at <= now_str:
            return jsonify({'error': 'expires_at must be in the future'}), 400

    key = generate_key()
    salt = generate_salt()
    key_id = str(uuid.uuid4())

    db = get_db()
    db.execute(
        '''INSERT INTO api_keys (id, key_hash, key_salt, prefix, name, rate_limit_rpm, expires_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (key_id, hash_key(key, salt), salt, lookup_prefix(key), name, rate_limit_rpm, expires_at)
    )
    db.commit()

    row = db.execute('SELECT * FROM api_keys WHERE id=?', (key_id,)).fetchone()
    result = key_to_dict(row)
    result['key'] = key           # Raw key returned ONLY at creation
    result['prefix'] = display_prefix(key)  # Show 8-char display prefix in response
    return jsonify(result), 201


@app.get('/keys')
def list_keys():
    db = get_db()
    rows = db.execute('SELECT * FROM api_keys ORDER BY created_at DESC').fetchall()
    return jsonify([key_to_dict(r) for r in rows]), 200


@app.get('/keys/<key_id>')
def get_key(key_id):
    db = get_db()
    row = db.execute('SELECT * FROM api_keys WHERE id=?', (key_id,)).fetchone()
    if row is None:
        return jsonify({'error': 'Key not found'}), 404
    return jsonify(key_to_dict(row)), 200


@app.delete('/keys/<key_id>')
def revoke_key(key_id):
    db = get_db()
    row = db.execute('SELECT id FROM api_keys WHERE id=?', (key_id,)).fetchone()
    if row is None:
        return jsonify({'error': 'Key not found'}), 404
    db.execute('UPDATE api_keys SET is_active=0 WHERE id=?', (key_id,))
    db.commit()
    return jsonify({'id': key_id, 'is_active': False}), 200


# ---------------------------------------------------------------------------
# Key validation
# ---------------------------------------------------------------------------

@app.post('/keys/validate')
def validate_key():
    data = request.get_json(silent=True) or {}
    provided_key = (data.get('key') or '').strip()

    if not provided_key:
        return jsonify({'valid': False, 'error': 'key is required'}), 400

    if not provided_key.startswith('ak_') or len(provided_key) < 35:
        return jsonify({'valid': False, 'error': 'invalid key'}), 401

    db = get_db()

    # Lookup by 16-char prefix index, then constant-time verify
    lp = lookup_prefix(provided_key)
    candidates = db.execute(
        'SELECT * FROM api_keys WHERE prefix=?', (lp,)
    ).fetchall()

    row = None
    for candidate in candidates:
        if verify_key(provided_key, candidate['key_salt'], candidate['key_hash']):
            row = candidate
            break

    if row is None:
        return jsonify({'valid': False, 'error': 'invalid key'}), 401

    if not row['is_active']:
        return jsonify({'valid': False, 'error': 'key revoked'}), 401

    # Check expiry (expires_at stored as 'YYYY-MM-DD HH:MM:SS' — SQLite-compatible)
    if row['expires_at']:
        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        if row['expires_at'] <= now_str:
            return jsonify({'valid': False, 'error': 'key expired'}), 401

    key_id = row['id']

    if row['rate_limit_rpm'] > 0:
        # BEGIN IMMEDIATE acquires the write lock upfront — makes both steps atomic
        db.execute('BEGIN IMMEDIATE')

        # Step 1: Reset expired window (idempotent)
        db.execute(
            '''UPDATE api_keys
               SET window_count=0, window_start=CURRENT_TIMESTAMP
               WHERE id=?
                 AND (window_start IS NULL
                      OR CAST((julianday('now') - julianday(window_start)) * 86400 AS INTEGER) >= ?)''',
            (key_id, WINDOW_SECONDS)
        )

        # Step 2: Atomically check-and-increment within the same transaction
        cursor = db.execute(
            '''UPDATE api_keys
               SET window_count=window_count+1,
                   total_requests=total_requests+1,
                   last_used_at=CURRENT_TIMESTAMP
               WHERE id=? AND window_count < rate_limit_rpm''',
            (key_id,)
        )
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({'valid': False, 'error': 'rate limit exceeded'}), 429

    else:
        # Unlimited — track usage only
        db.execute(
            '''UPDATE api_keys
               SET total_requests=total_requests+1,
                   last_used_at=CURRENT_TIMESTAMP,
                   window_count=window_count+1,
                   window_start=COALESCE(window_start, CURRENT_TIMESTAMP)
               WHERE id=?''',
            (key_id,)
        )
        db.commit()

    row = db.execute('SELECT * FROM api_keys WHERE id=?', (key_id,)).fetchone()
    return jsonify({
        'valid': True,
        'key_id': row['id'],
        'name': row['name'],
        'rate_limit_rpm': row['rate_limit_rpm'],
        'window_count': row['window_count'],
        'total_requests': row['total_requests'],
    }), 200


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@app.get('/keys/<key_id>/stats')
def key_stats(key_id):
    db = get_db()
    row = db.execute('SELECT * FROM api_keys WHERE id=?', (key_id,)).fetchone()
    if row is None:
        return jsonify({'error': 'Key not found'}), 404
    return jsonify({
        'id': row['id'],
        'name': row['name'],
        'total_requests': row['total_requests'],
        'last_used_at': row['last_used_at'],
        'window_count': row['window_count'],
        'window_start': row['window_start'],
        'rate_limit_rpm': row['rate_limit_rpm'],
        'rate_limited': row['rate_limit_rpm'] > 0,
    }), 200


if __name__ == '__main__':
    init_db(app)
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug)
