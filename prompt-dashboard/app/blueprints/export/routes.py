from flask import Blueprint, Response, g

from app.auth_helpers import login_required
from app.database import get_db
from app.models.export_models import export_user_prompts_csv

bp = Blueprint('export', __name__)


@bp.route('/my-prompts')
@login_required
def my_prompts():
    """Export current user's prompts as a CSV file download."""
    conn = get_db()
    csv_data = export_user_prompts_csv(conn, g.user['id'])
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=my-prompts-{g.user["username"]}.csv'
        }
    )
