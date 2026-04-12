"""Dashboard route blueprint for the project tracker."""

from flask import Blueprint, render_template
from app import get_db
from models.tasks import count_tasks_by_status, count_tasks_by_category, get_overdue_tasks
from models.activity import get_recent_activity

bp = Blueprint('dashboard', __name__)


@bp.route('/')
def index():
    db = get_db()
    return render_template('dashboard/index.html',
        status_counts=count_tasks_by_status(db),
        category_counts=count_tasks_by_category(db),
        overdue_tasks=get_overdue_tasks(db),
        recent_activity=get_recent_activity(db)
    )
