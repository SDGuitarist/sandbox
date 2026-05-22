import json
import time
from flask import Blueprint, Response, stream_with_context
from app.db import get_db
from app.decorators import login_required, require_workspace
from app.models import get_campaign, get_campaign_progress

sse_bp = Blueprint('sse', __name__)

@sse_bp.route('/campaign/<int:campaign_id>')
@login_required
@require_workspace
def campaign_progress(campaign_id):
    from flask import g
    conn = get_db()
    campaign = get_campaign(conn, campaign_id)
    if campaign is None or campaign['workspace_id'] != g.workspace['id']:
        return Response('Not found', status=404)

    def generate():
        import sqlite3
        from flask import current_app
        db_path = current_app.config['DATABASE']
        poll_conn = sqlite3.connect(db_path, timeout=5.0)
        poll_conn.row_factory = sqlite3.Row
        poll_conn.execute("PRAGMA journal_mode=WAL")
        poll_conn.execute("PRAGMA busy_timeout=5000")
        max_polls = 300  # 5-minute timeout (300 * 1s)
        poll_count = 0
        try:
            while poll_count < max_polls:
                progress = poll_conn.execute(
                    'SELECT * FROM campaign_progress WHERE campaign_id = ?',
                    (campaign_id,)
                ).fetchone()

                if progress:
                    data = json.dumps({
                        'total': progress['total'],
                        'sent': progress['sent'],
                        'delivered': progress['delivered'],
                        'failed': progress['failed'],
                        'status': progress['status'],
                    })
                    yield f'event: progress\ndata: {data}\n\n'
                    if progress['status'] == 'completed':
                        yield f'event: done\ndata: {{}}\n\n'
                        break
                else:
                    yield f'event: waiting\ndata: {{}}\n\n'

                poll_count += 1
                if poll_count % 15 == 0:
                    yield ': ping\n\n'  # heartbeat every 15s
                time.sleep(1)

            if poll_count >= max_polls:
                yield f'event: timeout\ndata: {{"message":"SSE timeout after 5 minutes"}}\n\n'
        except GeneratorExit:
            pass  # client disconnected
        finally:
            poll_conn.close()

    return stream_with_context(generate()), {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive',
    }
