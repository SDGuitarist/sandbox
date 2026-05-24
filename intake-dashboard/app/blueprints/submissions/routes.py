from flask import Blueprint, render_template, request
from app.db import get_db
from app.auth import login_required
from app.models.submissions import list_submissions, VALID_STATUSES

submissions_bp = Blueprint('submissions', __name__)


@submissions_bp.route('/')
@login_required
def list_view():
    status_filter = request.args.get('status')
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    conn = get_db()
    rows = list_submissions(conn, status_filter=status_filter, page=page)
    from app.models.submissions import PER_PAGE
    has_next = len(rows) > PER_PAGE
    submissions = rows[:PER_PAGE]
    return render_template('submissions/list.html',
        submissions=submissions,
        status_filter=status_filter,
        statuses=VALID_STATUSES,
        page=page,
        has_next=has_next
    )
