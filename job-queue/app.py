import json
import os
import uuid
from flask import Flask, request, jsonify
from database import get_db, close_db, init_db

app = Flask(__name__)


@app.teardown_appcontext
def teardown_db(e=None):
    close_db(e)


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'error': 'Method not allowed'}), 405


def row_to_dict(row):
    return {
        'id': row['id'],
        'payload': json.loads(row['payload']),
        'status': row['status'],
        'result': json.loads(row['result']) if row['result'] and row['result'] != 'null' else None,
        'error': row['error'],
        'retry_count': row['retry_count'],
        'max_retries': row['max_retries'],
        'timeout_seconds': row['timeout_seconds'],
        'created_at': row['created_at'],
        'started_at': row['started_at'],
        'completed_at': row['completed_at'],
        'worker_id': row['worker_id'],
    }


@app.post('/jobs')
def submit_job():
    data = request.get_json(silent=True) or {}

    if 'payload' not in data:
        return jsonify({'error': 'payload is required'}), 400

    try:
        max_retries = int(data.get('max_retries', 3))
        timeout_seconds = int(data.get('timeout_seconds', 30))
    except (ValueError, TypeError):
        return jsonify({'error': 'max_retries and timeout_seconds must be integers'}), 400

    if max_retries < 0:
        return jsonify({'error': 'max_retries must be >= 0'}), 400
    if timeout_seconds <= 0:
        return jsonify({'error': 'timeout_seconds must be > 0'}), 400

    job_id = str(uuid.uuid4())
    payload = json.dumps(data['payload'])

    db = get_db()
    db.execute(
        '''INSERT INTO jobs (id, payload, max_retries, timeout_seconds)
           VALUES (?, ?, ?, ?)''',
        (job_id, payload, max_retries, timeout_seconds)
    )
    db.commit()

    row = db.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    return jsonify(row_to_dict(row)), 201


@app.get('/jobs/<job_id>')
def get_job(job_id):
    db = get_db()
    row = db.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    if row is None:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(row_to_dict(row)), 200


@app.post('/jobs/claim')
def claim_job():
    data = request.get_json(silent=True) or {}
    # Generate a worker_id if not provided so fetch-by-id is always unambiguous
    worker_id = data.get('worker_id') or str(uuid.uuid4())

    db = get_db()

    # Step 1: Expire timed-out running jobs — reset to pending or fail permanently
    db.execute(
        '''UPDATE jobs SET
               status = CASE WHEN retry_count < max_retries THEN 'pending' ELSE 'failed' END,
               retry_count = CASE WHEN retry_count < max_retries THEN retry_count + 1 ELSE retry_count END,
               started_at = NULL,
               completed_at = NULL,
               worker_id = NULL,
               error = CASE WHEN retry_count < max_retries THEN 'job timed out' ELSE error END
           WHERE status = 'running'
             AND started_at IS NOT NULL
             AND CAST((julianday('now') - julianday(started_at)) * 86400 AS INTEGER) >= timeout_seconds'''
    )
    db.commit()

    # Step 2a: Find the oldest pending job ID first
    pending = db.execute(
        "SELECT id FROM jobs WHERE status='pending' ORDER BY created_at ASC LIMIT 1"
    ).fetchone()

    if pending is None:
        return '', 204

    job_id_to_claim = pending['id']

    # Step 2b: Atomically claim it — if another worker got here first, rowcount will be 0
    cursor = db.execute(
        '''UPDATE jobs SET status='running', started_at=CURRENT_TIMESTAMP, worker_id=?
           WHERE id=? AND status='pending' ''',
        (worker_id, job_id_to_claim)
    )
    db.commit()

    if cursor.rowcount == 0:
        return '', 204

    row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id_to_claim,)).fetchone()
    return jsonify(row_to_dict(row)), 200


@app.post('/jobs/<job_id>/complete')
def complete_job(job_id):
    data = request.get_json(silent=True) or {}

    if 'result' not in data:
        return jsonify({'error': 'result is required'}), 400

    db = get_db()
    row = db.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    if row is None:
        return jsonify({'error': 'Job not found'}), 404
    if row['status'] != 'running':
        return jsonify({'error': f"Job is '{row['status']}', not 'running'"}), 409

    result = json.dumps(data['result'])
    db.execute(
        '''UPDATE jobs SET status='completed', result=?, completed_at=CURRENT_TIMESTAMP
           WHERE id=?''',
        (result, job_id)
    )
    db.commit()

    row = db.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    return jsonify(row_to_dict(row)), 200


@app.post('/jobs/<job_id>/fail')
def fail_job(job_id):
    data = request.get_json(silent=True) or {}
    error_msg = data.get('error', '')

    db = get_db()
    row = db.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    if row is None:
        return jsonify({'error': 'Job not found'}), 404
    if row['status'] != 'running':
        return jsonify({'error': f"Job is '{row['status']}', not 'running'"}), 409

    if row['retry_count'] < row['max_retries']:
        db.execute(
            '''UPDATE jobs SET status='pending', retry_count=retry_count+1,
                              started_at=NULL, worker_id=NULL, error=?
               WHERE id=?''',
            (error_msg, job_id)
        )
    else:
        db.execute(
            '''UPDATE jobs SET status='failed', error=?, completed_at=CURRENT_TIMESTAMP
               WHERE id=?''',
            (error_msg, job_id)
        )
    db.commit()

    row = db.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    return jsonify(row_to_dict(row)), 200


if __name__ == '__main__':
    init_db(app)
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug)
