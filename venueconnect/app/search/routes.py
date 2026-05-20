from flask import Blueprint, render_template, request

from app.db import get_db
from app.decorators import login_required
from app.models import search_venues

search_bp = Blueprint('search', __name__, template_folder='../templates')


@search_bp.route('/')
@login_required
def index():
    query = request.args.get('q', '').strip()
    conn = get_db()
    results = search_venues(conn, query)
    return render_template('search/results.html', results=results, query=query)
