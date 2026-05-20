from flask import render_template, request, abort, g
from . import bp
from ..db import get_db
from ..decorators import require_portal_token
from ..models import get_songs_by_user, get_playlist_song_ids, get_song_for_portal, GENRES


@bp.route('/<token>')
@require_portal_token
def browse(token):
    search = request.args.get('search', '')
    genre_filter = request.args.get('genre', '')
    energy_filter = request.args.get('energy', '')
    with get_db() as db:
        songs = get_songs_by_user(
            db,
            g.portal_event['user_id'],
            genre=genre_filter or None,
            energy=energy_filter or None,
            search=search or None,
        )
        playlist_song_ids = get_playlist_song_ids(db, g.portal_event['id'])
    return render_template('portal_browse/browse.html',
        event=g.portal_event,
        songs=songs,
        genres=GENRES,
        search=search,
        genre_filter=genre_filter,
        energy_filter=energy_filter,
        playlist_song_ids=playlist_song_ids,
        is_approved=g.portal_is_approved)


@bp.route('/<token>/song/<int:song_id>')
@require_portal_token
def song_detail(token, song_id):
    with get_db() as db:
        song = get_song_for_portal(db, song_id, g.portal_event['user_id'])
        if song is None:
            abort(404)
        playlist_song_ids = get_playlist_song_ids(db, g.portal_event['id'])
    in_playlist = song_id in playlist_song_ids
    return render_template('portal_browse/song_detail.html',
        event=g.portal_event,
        song=song,
        in_playlist=in_playlist,
        is_approved=g.portal_is_approved)
