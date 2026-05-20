import csv
import io
from flask import render_template, session, abort, make_response
from ..db import get_db
from ..decorators import login_required
from ..models import get_event, get_playlist_items, get_song_requests
from . import bp


@bp.route('/<int:event_id>/export')
@login_required
def export_preview(event_id):
    """Preview setlist for print."""
    with get_db() as db:
        event = get_event(db, event_id, session['user_id'])
        if event is None:
            abort(404)
        playlist_items = get_playlist_items(db, event_id)
        song_requests = get_song_requests(db, event_id)
    return render_template('event_export/preview.html',
                           event=event,
                           playlist_items=playlist_items,
                           song_requests=song_requests)


@bp.route('/<int:event_id>/export/csv')
@login_required
def export_csv(event_id):
    """Download setlist as CSV file."""
    with get_db() as db:
        event = get_event(db, event_id, session['user_id'])
        if event is None:
            abort(404)
        playlist_items = get_playlist_items(db, event_id)
        song_requests = get_song_requests(db, event_id)

    output = io.StringIO()
    writer = csv.writer(output)

    # Playlist section
    writer.writerow(['#', 'Title', 'Artist', 'Genre', 'Key', 'Tempo',
                     'Energy', 'Duration', 'Must Play', 'Do Not Play', 'Client Note'])
    for i, item in enumerate(playlist_items, start=1):
        duration = ''
        if item['duration_seconds']:
            minutes = item['duration_seconds'] // 60
            secs = item['duration_seconds'] % 60
            duration = f"{minutes}:{secs:02d}"
        writer.writerow([
            i,
            item['title'],
            item['artist'],
            item['genre'],
            item['musical_key'],
            item['tempo'] or '',
            item['energy'],
            duration,
            'Yes' if item['is_must_play'] else '',
            'Yes' if item['is_do_not_play'] else '',
            item['client_note'],
        ])

    # Blank row separator
    writer.writerow([])

    # Song requests section
    writer.writerow(['Song Requests'])
    writer.writerow(['Title', 'Artist', 'Notes', 'Submitted'])
    for req in song_requests:
        writer.writerow([
            req['title'],
            req['artist'],
            req['notes'],
            req['created_at'],
        ])

    csv_content = output.getvalue()
    output.close()

    # Build safe filename from event name
    safe_name = ''.join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in event['name'])
    safe_name = safe_name.strip().replace(' ', '_') or 'setlist'
    filename = f"{safe_name}_setlist.csv"

    response = make_response(csv_content)
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
