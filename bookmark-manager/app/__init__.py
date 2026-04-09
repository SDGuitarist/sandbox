import secrets
from flask import Flask, redirect, url_for, session, request, abort
from app.db import init_db

def create_app(db_path=None):
    app = Flask(__name__)
    app.config['SECRET_KEY'] = secrets.token_hex(24)
    if db_path:
        app.config['DB_PATH'] = db_path
    else:
        app.config['DB_PATH'] = 'bookmarks.db'

    with app.app_context():
        init_db(app)

    @app.before_request
    def csrf_protect():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(16)
        if request.method == 'POST':
            token = request.form.get('csrf_token', '')
            if token != session.get('csrf_token'):
                abort(403)

    @app.context_processor
    def inject_csrf():
        return {'csrf_token': session.get('csrf_token', '')}

    @app.route('/')
    def index():
        return redirect(url_for('bookmarks.index'))

    from app.blueprints.bookmarks import bookmarks_bp
    from app.blueprints.tags import tags_bp
    app.register_blueprint(bookmarks_bp, url_prefix='/bookmarks')
    app.register_blueprint(tags_bp, url_prefix='/tags')

    return app
