import secrets
from flask import Blueprint, render_template, request, redirect, url_for, session, abort
from app import get_db
from models import (
    get_all_contacts,
    get_contact,
    search_contacts,
    create_contact,
    update_contact,
    delete_contact,
)

bp = Blueprint('contacts', __name__)


def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


def validate_csrf_token():
    token = session.get('_csrf_token')
    if not token or token != request.form.get('_csrf_token'):
        abort(403)


@bp.app_context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf_token)


@bp.route('/')
def index():
    db = get_db()
    query = request.args.get('q', '').strip()
    if query:
        contacts = search_contacts(db, query)
    else:
        contacts = get_all_contacts(db)
    return render_template('index.html', contacts=contacts, query=query)


@bp.route('/add', methods=['GET'])
def add_form():
    return render_template('add.html')


@bp.route('/add', methods=['POST'])
def add_contact():
    validate_csrf_token()
    db = get_db()
    create_contact(
        db,
        request.form.get('name', ''),
        request.form.get('email', ''),
        request.form.get('phone', ''),
        request.form.get('notes', ''),
    )
    return redirect(url_for('contacts.index'))


@bp.route('/edit/<int:id>', methods=['GET'])
def edit_form(id):
    db = get_db()
    contact = get_contact(db, id)
    if contact is None:
        abort(404)
    return render_template('edit.html', contact=contact)


@bp.route('/edit/<int:id>', methods=['POST'])
def edit_contact(id):
    validate_csrf_token()
    db = get_db()
    contact = get_contact(db, id)
    if contact is None:
        abort(404)
    update_contact(
        db,
        id,
        request.form.get('name', ''),
        request.form.get('email', ''),
        request.form.get('phone', ''),
        request.form.get('notes', ''),
    )
    return redirect(url_for('contacts.index'))


@bp.route('/delete/<int:id>', methods=['POST'])
def delete_contact_route(id):
    validate_csrf_token()
    db = get_db()
    delete_contact(db, id)
    return redirect(url_for('contacts.index'))
