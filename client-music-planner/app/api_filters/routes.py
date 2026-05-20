from flask import request, jsonify

from . import bp
from ..db import get_db
from ..models import get_event_by_token, get_songs_by_user, get_playlist_song_ids


@bp.route('/songs')
def filter_songs():
    token = request.args.get('token', '')
    genre = request.args.get('genre', '')
    energy = request.args.get('energy', '')
    search = request.args.get('search', '')

    with get_db() as db:
        event = get_event_by_token(db, token)
        if event is None or event['is_archived']:
            return jsonify(error="Invalid portal"), 404
        songs = get_songs_by_user(db, event['user_id'], genre=genre or None,
                                   energy=energy or None, search=search or None)
        playlist_ids = set(get_playlist_song_ids(db, event['id']))

    result = [{'id': s['id'], 'title': s['title'], 'artist': s['artist'],
               'genre': s['genre'], 'energy': s['energy'],
               'duration_seconds': s['duration_seconds'],
               'in_playlist': s['id'] in playlist_ids} for s in songs]
    return jsonify(songs=result)
