import secrets

from flask import (
    flash, redirect, render_template, request, session, url_for, abort
)

from app.db import get_db
from app.decorators import login_required
from app.models import (
    EVENT_TYPES, create_event, delete_event, get_event, get_events_by_user,
    update_event, archive_event, regenerate_token as model_regenerate_token,
    get_playlist_stats, get_song_request_count,
)
from . import bp


@bp.route('/')
@login_required
def index():
    show_archived = request.args.get('show_archived', '0') == '1'
    with get_db() as db:
        events = get_events_by_user(
            db, session['user_id'], include_archived=show_archived
        )
    return render_template(
        'events/index.html',
        events=events,
        show_archived=show_archived,
    )


@bp.route('/new', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        event_date = request.form.get('event_date', '').strip()
        event_type = request.form.get('event_type', '').strip()
        venue = request.form.get('venue', '').strip()
        client_name = request.form.get('client_name', '').strip()
        client_email = request.form.get('client_email', '').strip()
        notes = request.form.get('notes', '').strip()

        if not name:
            flash("Event name is required.", "error")
            return render_template(
                'events/form.html', event=None, event_types=EVENT_TYPES
            )
        if not event_date:
            flash("Event date is required.", "error")
            return render_template(
                'events/form.html', event=None, event_types=EVENT_TYPES
            )
        if not client_name:
            flash("Client name is required.", "error")
            return render_template(
                'events/form.html', event=None, event_types=EVENT_TYPES
            )
        if event_type not in EVENT_TYPES:
            event_type = 'wedding'

        portal_token = secrets.token_urlsafe(32)

        with get_db(immediate=True) as db:
            create_event(
                db, session['user_id'], name, event_date, event_type,
                venue, client_name, client_email, portal_token, notes
            )
            db.commit()

        flash("Event created successfully.", "success")
        return redirect(url_for('events.index'))

    return render_template(
        'events/form.html', event=None, event_types=EVENT_TYPES
    )


@bp.route('/<int:event_id>')
@login_required
def detail(event_id):
    with get_db() as db:
        event = get_event(db, event_id, session['user_id'])
        if event is None:
            abort(404)
        playlist_count = get_playlist_stats(db, event_id)['total']
        request_count = get_song_request_count(db, event_id)
    portal_url = (
        request.host_url.rstrip('/')
        + url_for('portal_browse.browse', token=event['portal_token'])
    )
    return render_template(
        'events/detail.html',
        event=event,
        portal_url=portal_url,
        playlist_count=playlist_count,
        request_count=request_count,
    )


@bp.route('/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(event_id):
    with get_db() as db:
        event = get_event(db, event_id, session['user_id'])
    if event is None:
        abort(404)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        event_date = request.form.get('event_date', '').strip()
        event_type = request.form.get('event_type', '').strip()
        venue = request.form.get('venue', '').strip()
        client_name = request.form.get('client_name', '').strip()
        client_email = request.form.get('client_email', '').strip()
        notes = request.form.get('notes', '').strip()

        if not name:
            flash("Event name is required.", "error")
            return render_template(
                'events/form.html', event=event, event_types=EVENT_TYPES
            )
        if not event_date:
            flash("Event date is required.", "error")
            return render_template(
                'events/form.html', event=event, event_types=EVENT_TYPES
            )
        if not client_name:
            flash("Client name is required.", "error")
            return render_template(
                'events/form.html', event=event, event_types=EVENT_TYPES
            )
        if event_type not in EVENT_TYPES:
            event_type = 'wedding'

        with get_db(immediate=True) as db:
            update_event(
                db, event_id, session['user_id'], name, event_date,
                event_type, venue, client_name, client_email, notes
            )
            db.commit()

        flash("Event updated successfully.", "success")
        return redirect(url_for('events.detail', event_id=event_id))

    return render_template(
        'events/form.html', event=event, event_types=EVENT_TYPES
    )


@bp.route('/<int:event_id>/delete', methods=['POST'])
@login_required
def delete(event_id):
    with get_db(immediate=True) as db:
        event = get_event(db, event_id, session['user_id'])
        if event is None:
            abort(404)
        delete_event(db, event_id, session['user_id'])
        db.commit()

    flash("Event deleted.", "success")
    return redirect(url_for('events.index'))


@bp.route('/<int:event_id>/regenerate-token', methods=['POST'])
@login_required
def regenerate_token(event_id):
    new_token = secrets.token_urlsafe(32)
    with get_db(immediate=True) as db:
        event = get_event(db, event_id, session['user_id'])
        if event is None:
            abort(404)
        model_regenerate_token(db, event_id, session['user_id'], new_token)
        db.commit()

    flash("Portal link regenerated. The old link no longer works.", "success")
    return redirect(url_for('events.detail', event_id=event_id))


@bp.route('/<int:event_id>/archive', methods=['POST'])
@login_required
def toggle_archive(event_id):
    with get_db(immediate=True) as db:
        event = get_event(db, event_id, session['user_id'])
        if event is None:
            abort(404)
        archive_event(db, event_id, session['user_id'])
        db.commit()

    if event['is_archived']:
        flash("Event unarchived.", "success")
    else:
        flash("Event archived.", "success")
    return redirect(url_for('events.index'))
