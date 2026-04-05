import os
import sqlite3
from flask import Flask, request, jsonify, redirect, g
from database import get_db, close_db, init_db
from shortener import generate_code, MAX_RETRIES

app = Flask(__name__)

MAX_URL_LENGTH = 2048


@app.teardown_appcontext
def teardown_db(e=None):
    close_db(e)


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'error': 'Method not allowed'}), 405


@app.post('/shorten')
def shorten():
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()

    if (
        not url
        or len(url) > MAX_URL_LENGTH
        or not (url.startswith('http://') or url.startswith('https://'))
    ):
        return jsonify({
            'error': f'A valid http:// or https:// URL is required (max {MAX_URL_LENGTH} chars)'
        }), 400

    db = get_db()

    for _ in range(MAX_RETRIES):
        code = generate_code()
        try:
            db.execute(
                'INSERT INTO links (original_url, short_code) VALUES (?, ?)',
                (url, code)
            )
            db.commit()
            short_url = request.host_url.rstrip('/') + '/' + code
            return jsonify({'short_code': code, 'short_url': short_url}), 201
        except sqlite3.IntegrityError:
            continue

    return jsonify({'error': 'Could not generate a unique short code. Try again.'}), 500


@app.get('/<code>')
def redirect_to_url(code):
    db = get_db()
    row = db.execute(
        'SELECT original_url FROM links WHERE short_code = ?', (code,)
    ).fetchone()

    if row is None:
        return jsonify({'error': 'Short code not found'}), 404

    db.execute(
        'UPDATE links SET click_count = click_count + 1 WHERE short_code = ?',
        (code,)
    )
    db.commit()

    return redirect(row['original_url'], code=302)


@app.get('/stats/<code>')
def stats(code):
    db = get_db()
    row = db.execute(
        'SELECT short_code, original_url, click_count, created_at FROM links WHERE short_code = ?',
        (code,)
    ).fetchone()

    if row is None:
        return jsonify({'error': 'Short code not found'}), 404

    return jsonify({
        'short_code': row['short_code'],
        'original_url': row['original_url'],
        'click_count': row['click_count'],
        'created_at': row['created_at'],
    }), 200


if __name__ == '__main__':
    init_db(app)
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug)
