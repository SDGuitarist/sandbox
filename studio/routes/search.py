"""Cross-entity search blueprint (search agent).

GET /search?q=<term> -- role-filtered keyword search over students, instructors,
and courses. Any logged-in user may search (auth); results are role-filtered by
search_all (a student sees only self + the public active-course catalog).
"""

from flask import Blueprint, render_template, request

from studio.auth import login_required, current_user, current_student_id
from studio.models.search_models import search_all

bp = Blueprint("search", __name__, url_prefix="/search")


@bp.route("/", methods=["GET"])
@login_required
def search():
    q = request.args.get("q", "")
    results = search_all(
        q,
        current_user()["role"],
        actor_student_id=current_student_id(),
    )
    return render_template("search/results.html", q=q, results=results)
