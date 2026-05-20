from flask import render_template, session

from ..db import get_db
from ..decorators import login_required
from . import bp


@bp.route('/')
@login_required
def index():
    """Musician home page with event summaries and quick stats."""
    user_id = session['user_id']
    with get_db() as db:
        # Active (non-archived) events sorted by date
        events = db.execute(
            "SELECT * FROM event WHERE user_id = ? AND is_archived = 0 "
            "ORDER BY event_date DESC",
            (user_id,),
        ).fetchall()

        active_count = len(events)

        # Total songs in the musician's repertoire
        row = db.execute(
            "SELECT COUNT(*) AS cnt FROM song WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        total_songs = row['cnt']

        # Recent client approvals (limit 5)
        recent_approvals = db.execute(
            "SELECT * FROM event WHERE user_id = ? AND client_approved = 1 "
            "ORDER BY approved_at DESC LIMIT 5",
            (user_id,),
        ).fetchall()

    return render_template(
        'dashboard/index.html',
        events=events,
        active_count=active_count,
        total_songs=total_songs,
        recent_approvals=recent_approvals,
    )
