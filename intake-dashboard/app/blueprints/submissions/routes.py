from flask import Blueprint, render_template, request
from app.db import get_db
from app.auth import login_required
from app.models.submissions import list_submissions, VALID_STATUSES

submissions_bp = Blueprint('submissions', __name__)


@submissions_bp.route('/')
@login_required
def list_view():
    status_filter = request.args.get('status')
    conn = get_db()
    submissions = list_submissions(conn, status_filter=status_filter)
    return render_template('submissions/list.html',
        submissions=submissions,
        status_filter=status_filter,
        statuses=VALID_STATUSES
    )
