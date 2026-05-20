from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, g
from app.db import get_db
from app.decorators import login_required
from app.notifications import (get_notifications, get_unread_count,
                                mark_notification_read,
                                mark_all_read as _mark_all_read)

notification_views_bp = Blueprint('notification_views', __name__)


@notification_views_bp.route('/')
@login_required
def list():
    conn = get_db()
    notifications = get_notifications(conn, g.user['id'])
    return render_template('notifications/list.html', notifications=notifications)


@notification_views_bp.route('/<int:id>/read', methods=['POST'])
@login_required
def mark_read(id):
    conn = get_db()
    notification = conn.execute(
        'SELECT user_id FROM notifications WHERE id = ?', (id,)
    ).fetchone()
    if notification is None or notification['user_id'] != g.user['id']:
        flash('Notification not found.', 'error')
        return redirect(url_for('notification_views.list'))
    mark_notification_read(conn, id)
    conn.commit()
    flash('Notification marked as read.', 'success')
    return redirect(url_for('notification_views.list'))


@notification_views_bp.route('/read-all', methods=['POST'])
@login_required
def mark_all_read():
    conn = get_db()
    _mark_all_read(conn, g.user['id'])
    conn.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('notification_views.list'))


@notification_views_bp.route('/unread-count')
@login_required
def unread_count():
    conn = get_db()
    count = get_unread_count(conn, g.user['id'])
    return jsonify(count=count)
