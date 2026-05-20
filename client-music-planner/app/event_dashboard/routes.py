from flask import abort, render_template, session

from ..db import get_db
from ..decorators import login_required
from ..models import get_event, get_playlist_items, get_song_requests, get_playlist_stats
from . import bp


@bp.route('/<int:event_id>/dashboard')
@login_required
def dashboard(event_id):
    with get_db() as db:
        event = get_event(db, event_id, session['user_id'])
        if event is None:
            abort(404)
        playlist_items = get_playlist_items(db, event_id)
        song_requests = get_song_requests(db, event_id)
        stats = get_playlist_stats(db, event_id)
    return render_template('event_dashboard/dashboard.html',
        event=event, playlist_items=playlist_items,
        song_requests=song_requests, stats=stats)
