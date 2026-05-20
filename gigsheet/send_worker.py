"""
Email queue worker -- run separately from Flask app.
Usage: .venv/bin/python send_worker.py

Polls job_queue table every 2 seconds, claims pending jobs, sends via sendgrid_client.
"""
import os
import sys
import time
import uuid
import signal
import sqlite3

os.environ.setdefault('SECRET_KEY', 'worker-key')

WORKER_ID = f'worker-{uuid.uuid4().hex[:8]}'
POLL_INTERVAL = 2  # seconds
DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'gigsheet.db')

shutdown = False

def handle_signal(sig, frame):
    global shutdown
    shutdown = True

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

# Create Flask app ONCE at module level (not per-job -- P1 fix)
from app import create_app
app = create_app()

def get_worker_db():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    return conn

def process_one_job(conn):
    """Claim and process one job. Returns True if a job was processed."""
    # Atomic claim using CTE+RETURNING (single statement)
    conn.execute('BEGIN IMMEDIATE')
    claimed = conn.execute('''
        WITH candidate AS (
            SELECT id FROM job_queue
            WHERE status = 'pending' AND scheduled_at <= datetime('now')
            ORDER BY created_at LIMIT 1
        )
        UPDATE job_queue SET status = 'running', worker_id = ?, claimed_at = datetime('now')
        WHERE id = (SELECT id FROM candidate) AND status = 'pending'
        RETURNING id
    ''', (WORKER_ID,)).fetchone()
    if claimed is None:
        conn.rollback()
        return False
    conn.commit()

    # Fetch full job + recipient + lead + template
    job_row = conn.execute('SELECT * FROM job_queue WHERE id = ?', (claimed['id'],)).fetchone()
    recipient = conn.execute('''
        SELECT cr.*, l.email, l.contact_name, l.venue_name, l.capacity,
               l.location, l.genre_tags, l.phone, l.website
        FROM campaign_recipients cr
        JOIN leads l ON l.id = cr.lead_id
        WHERE cr.id = ?
    ''', (job_row['recipient_id'],)).fetchone()

    campaign = conn.execute('SELECT * FROM campaigns WHERE id = ?', (job_row['campaign_id'],)).fetchone()
    template = conn.execute('SELECT * FROM templates WHERE id = ?', (campaign['template_id'],)).fetchone()

    # Render template
    from app.models import render_template_with_lead
    subject, body = render_template_with_lead(template, recipient)

    # Send via SendGrid client (uses module-level app for context)
    with app.app_context():
        from app.sendgrid_client import send_email
        from_email = app.config['SENDGRID_FROM_EMAIL']
        result = send_email(recipient['email'], from_email, subject, body, str(job_row['id']))

    # Update all state in a SINGLE commit (fix: no partial commit window)
    success = result['status'] == 'accepted'
    error_msg = result.get('error', '')
    message_id = result.get('message_id', '')

    with app.app_context():
        from app.models import (update_recipient_status, increment_campaign_counter,
                                update_campaign_progress)
        from app.db import get_db
        db = get_db()

        # Update recipient + campaign counters FIRST (before job completion)
        if success:
            update_recipient_status(db, recipient['id'], 'sent', message_id)
            increment_campaign_counter(db, job_row['campaign_id'], 'sent_count')
        else:
            update_recipient_status(db, recipient['id'], 'failed')
            increment_campaign_counter(db, job_row['campaign_id'], 'failed_count')

        # Update job status (does NOT commit here -- we batch all writes)
        job_status = 'completed' if success else 'failed'
        db.execute('''
            UPDATE job_queue SET status = ?, completed_at = datetime('now'), error_message = ?
            WHERE id = ?
        ''', (job_status, error_msg, job_row['id']))

        # Single commit for recipient + counters + job status
        db.commit()

        # Update campaign progress (COMMITS independently for SSE)
        sent_delta = 1 if success else 0
        failed_delta = 0 if success else 1
        delivered_delta = 1 if success else 0  # Fix: pass delivered_delta
        update_campaign_progress(db, job_row['campaign_id'],
                                 sent_delta=sent_delta,
                                 delivered_delta=delivered_delta,
                                 failed_delta=failed_delta)
    return True

def reclaim_timed_out_jobs(conn):
    """Reclaim jobs stuck in 'running' for > 5 minutes."""
    conn.execute('''
        UPDATE job_queue SET status = 'pending', claimed_at = NULL, worker_id = '',
            attempt_count = attempt_count + 1
        WHERE status = 'running' AND claimed_at < datetime('now', '-5 minutes')
            AND attempt_count + 1 < max_attempts
    ''')
    conn.execute('''
        UPDATE job_queue SET status = 'failed', error_message = 'max attempts exceeded',
            completed_at = datetime('now')
        WHERE status = 'running' AND claimed_at < datetime('now', '-5 minutes')
            AND attempt_count + 1 >= max_attempts
    ''')
    conn.commit()

if __name__ == '__main__':
    print(f'[{WORKER_ID}] Starting email queue worker...')
    conn = get_worker_db()
    cycle = 0
    while not shutdown:
        try:
            processed = process_one_job(conn)
            if not processed:
                time.sleep(POLL_INTERVAL)
            cycle += 1
            if cycle % 30 == 0:  # Every ~60 seconds
                reclaim_timed_out_jobs(conn)
            if cycle % 150 == 0:  # Every ~5 minutes
                conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        except sqlite3.Error as e:
            print(f'[{WORKER_ID}] SQLite error (retrying): {e}')
            time.sleep(POLL_INTERVAL)
        except Exception as e:
            print(f'[{WORKER_ID}] Unexpected error: {e}')
            time.sleep(POLL_INTERVAL)
    print(f'[{WORKER_ID}] Shutting down gracefully.')
    conn.close()
