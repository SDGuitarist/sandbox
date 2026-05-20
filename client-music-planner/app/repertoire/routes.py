from flask import render_template, request, redirect, url_for, flash, session, abort

from . import bp
from ..db import get_db
from ..decorators import login_required
from ..models import (
    GENRES,
    get_songs_by_user,
    get_song,
    create_song,
    update_song,
    delete_song,
)


@bp.route('/')
@login_required
def index():
    search = request.args.get('search', '')
    genre = request.args.get('genre', '')
    energy = request.args.get('energy', '')
    with get_db() as db:
        songs = get_songs_by_user(
            db,
            session['user_id'],
            genre=genre or None,
            energy=energy or None,
            search=search or None,
        )
    return render_template(
        'repertoire/index.html',
        songs=songs,
        search=search,
        genre=genre,
        energy=energy,
        genres=GENRES,
    )


@bp.route('/new', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        artist = request.form.get('artist', '').strip()
        genre = request.form.get('genre', 'other')
        musical_key = request.form.get('musical_key', '').strip()
        tempo = request.form.get('tempo', '').strip()
        energy = request.form.get('energy', '3')
        duration_seconds = request.form.get('duration_seconds', '').strip()
        notes = request.form.get('notes', '').strip()

        if not title:
            flash("Title is required.", "error")
            return render_template(
                'repertoire/form.html',
                song=None,
                genres=GENRES,
            )

        if genre not in GENRES:
            genre = 'other'

        try:
            energy_val = int(energy)
            if energy_val < 1 or energy_val > 5:
                energy_val = 3
        except (ValueError, TypeError):
            energy_val = 3

        tempo_val = None
        if tempo:
            try:
                tempo_val = int(tempo)
            except (ValueError, TypeError):
                flash("Tempo must be a number.", "error")
                return render_template(
                    'repertoire/form.html',
                    song=None,
                    genres=GENRES,
                )

        duration_val = None
        if duration_seconds:
            try:
                duration_val = int(duration_seconds)
            except (ValueError, TypeError):
                flash("Duration must be a number in seconds.", "error")
                return render_template(
                    'repertoire/form.html',
                    song=None,
                    genres=GENRES,
                )

        with get_db(immediate=True) as db:
            create_song(
                db,
                session['user_id'],
                title,
                artist,
                genre,
                musical_key,
                tempo_val,
                energy_val,
                duration_val,
                notes,
            )
            db.commit()

        flash("Song created successfully.", "success")
        return redirect(url_for('repertoire.index'))

    return render_template(
        'repertoire/form.html',
        song=None,
        genres=GENRES,
    )


@bp.route('/<int:song_id>')
@login_required
def detail(song_id):
    with get_db() as db:
        song = get_song(db, song_id, session['user_id'])
    if song is None:
        abort(404)
    return render_template('repertoire/detail.html', song=song)


@bp.route('/<int:song_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(song_id):
    with get_db() as db:
        song = get_song(db, song_id, session['user_id'])
    if song is None:
        abort(404)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        artist = request.form.get('artist', '').strip()
        genre = request.form.get('genre', 'other')
        musical_key = request.form.get('musical_key', '').strip()
        tempo = request.form.get('tempo', '').strip()
        energy = request.form.get('energy', '3')
        duration_seconds = request.form.get('duration_seconds', '').strip()
        notes = request.form.get('notes', '').strip()

        if not title:
            flash("Title is required.", "error")
            return render_template(
                'repertoire/form.html',
                song=song,
                genres=GENRES,
            )

        if genre not in GENRES:
            genre = 'other'

        try:
            energy_val = int(energy)
            if energy_val < 1 or energy_val > 5:
                energy_val = 3
        except (ValueError, TypeError):
            energy_val = 3

        tempo_val = None
        if tempo:
            try:
                tempo_val = int(tempo)
            except (ValueError, TypeError):
                flash("Tempo must be a number.", "error")
                return render_template(
                    'repertoire/form.html',
                    song=song,
                    genres=GENRES,
                )

        duration_val = None
        if duration_seconds:
            try:
                duration_val = int(duration_seconds)
            except (ValueError, TypeError):
                flash("Duration must be a number in seconds.", "error")
                return render_template(
                    'repertoire/form.html',
                    song=song,
                    genres=GENRES,
                )

        with get_db(immediate=True) as db:
            update_song(
                db,
                song_id,
                session['user_id'],
                title,
                artist,
                genre,
                musical_key,
                tempo_val,
                energy_val,
                duration_val,
                notes,
            )
            db.commit()

        flash("Song updated successfully.", "success")
        return redirect(url_for('repertoire.detail', song_id=song_id))

    return render_template(
        'repertoire/form.html',
        song=song,
        genres=GENRES,
    )


@bp.route('/<int:song_id>/delete', methods=['POST'])
@login_required
def delete(song_id):
    with get_db(immediate=True) as db:
        song = get_song(db, song_id, session['user_id'])
        if song is None:
            abort(404)
        delete_song(db, song_id, session['user_id'])
        db.commit()

    flash("Song deleted.", "success")
    return redirect(url_for('repertoire.index'))
