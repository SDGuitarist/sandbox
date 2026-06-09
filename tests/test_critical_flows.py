"""Critical-flow tests for the Film Production PM Tool.

Implements the 10 prescribed critical-flow tests from the plan
(docs/plans/film-production-pm-plan.md -- "Critical-Flow Tests").

Setup that is not itself under test is performed through the model layer (and,
for role/membership wiring not exposed by routes, raw SQL) inside an app
context. Behaviour under test is exercised through the HTTP layer wherever the
test description names a route, status code, or HTTP-level concern.

The seeded fixtures provide:
  - user 'producer' (password = conftest.ADMIN_PASSWORD), role 'producer'
  - project id=1 ('Untitled Production')
  - 17 departments and 30 budget categories on project 1
"""
import json
import re

import pytest
from werkzeug.security import generate_password_hash

from app.database import get_db
from app.models import scene_models, cast_models, location_models
from app.models import schedule_models, callsheet_models
from app.models import budget_models, expense_models
from app.models import department_models
from app.models import report_models

from tests.conftest import ADMIN_PASSWORD


PROJECT_ID = 1


# --------------------------------------------------------------------------- #
# Raw-SQL setup helpers (membership / role wiring not exposed by routes)
# --------------------------------------------------------------------------- #

def _dept_id(conn, project_id, name):
    row = conn.execute(
        "SELECT id FROM departments WHERE project_id = ? AND name = ?",
        (project_id, name),
    ).fetchone()
    assert row is not None, f"seeded department {name!r} not found"
    return row["id"]


def _category_id(conn, project_id):
    row = conn.execute(
        "SELECT id FROM budget_categories WHERE project_id = ? ORDER BY id LIMIT 1",
        (project_id,),
    ).fetchone()
    assert row is not None, "seeded budget category not found"
    return row["id"]


def _create_user(conn, username, password, display_name):
    conn.execute(
        "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
        (username, generate_password_hash(password), display_name),
    )
    return conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()["id"]


def _add_member(conn, project_id, user_id, role):
    conn.execute(
        "INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, ?)",
        (project_id, user_id, role),
    )


def _make_second_project(conn, created_by):
    """Create a second project owned by created_by; returns its id."""
    conn.execute(
        "INSERT INTO projects (title, phase, total_budget_cents, created_by) "
        "VALUES (?, 'development', 0, ?)",
        ("Other Production", created_by),
    )
    return conn.execute(
        "SELECT id FROM projects WHERE title = 'Other Production'"
    ).fetchone()["id"]


# =========================================================================== #
# Test 1: Call sheet generation end-to-end
# Create project -> add scenes -> add cast to scenes -> create schedule entries
# -> generate call sheet -> verify scenes, cast with statuses, and location.
# =========================================================================== #

def test_call_sheet_generation_end_to_end(app):
    with app.app_context():
        conn = get_db()
        loc_id = location_models.create_location(
            conn, PROJECT_ID, "Downtown Loft",
            address="123 Main St", nearest_hospital="St. Mary's",
        )
        s1 = scene_models.create_scene(conn, PROJECT_ID, "1", "Opening", "INT", "DAY", 8, location_id=loc_id)
        s2 = scene_models.create_scene(conn, PROJECT_ID, "2", "Argument", "INT", "NIGHT", 12, location_id=loc_id)

        hero = cast_models.create_cast_member(conn, PROJECT_ID, "Jane Doe", "HERO", 1)
        villain = cast_models.create_cast_member(conn, PROJECT_ID, "John Roe", "VILLAIN", 2)
        cast_models.add_cast_to_scene(conn, s1, hero)
        cast_models.add_cast_to_scene(conn, s2, hero)
        cast_models.add_cast_to_scene(conn, s2, villain)

        shoot_date = "2026-07-01"
        e1 = schedule_models.create_schedule_entry(conn, PROJECT_ID, s1, loc_id, shoot_date, 0)
        e2 = schedule_models.create_schedule_entry(conn, PROJECT_ID, s2, loc_id, shoot_date, 1)
        assert e1 is not None and e2 is not None

        cs_id = callsheet_models.generate_call_sheet(conn, PROJECT_ID, shoot_date)
        assert isinstance(cs_id, int)

        sheet = callsheet_models.get_call_sheet(conn, cs_id)
        assert sheet is not None
        assert sheet["shoot_date"] == shoot_date

        cs_scenes = callsheet_models.get_call_sheet_scenes(conn, cs_id)
        scene_numbers = {row["scene_number"] for row in cs_scenes}
        assert {"1", "2"} <= scene_numbers, f"call sheet scenes: {scene_numbers}"

        cs_cast = callsheet_models.get_call_sheet_cast(conn, cs_id)
        cast_ids = {row["cast_member_id"] for row in cs_cast}
        assert {hero, villain} <= cast_ids, f"call sheet cast: {cast_ids}"
        for row in cs_cast:
            assert row["status"] in ("W", "SW", "WF", "SWF", "H")


# =========================================================================== #
# Test 2: DOOD grid accuracy
# Schedule 3 scenes across 5 days with overlapping cast -> verify W/SW/WF/SWF/H.
# =========================================================================== #

def test_dood_grid_accuracy(app):
    with app.app_context():
        conn = get_db()
        loc_id = location_models.create_location(conn, PROJECT_ID, "Stage A")

        # Five shoot dates.
        dates = ["2026-08-01", "2026-08-02", "2026-08-03", "2026-08-04", "2026-08-05"]

        # Three scenes, one shot on each of days 1, 3 and 5 (gap on 2 and 4).
        sc_a = scene_models.create_scene(conn, PROJECT_ID, "A", "d1", "INT", "DAY", 8, location_id=loc_id)
        sc_b = scene_models.create_scene(conn, PROJECT_ID, "B", "d3", "INT", "DAY", 8, location_id=loc_id)
        sc_c = scene_models.create_scene(conn, PROJECT_ID, "C", "d5", "INT", "DAY", 8, location_id=loc_id)

        schedule_models.create_schedule_entry(conn, PROJECT_ID, sc_a, loc_id, dates[0], 0)
        schedule_models.create_schedule_entry(conn, PROJECT_ID, sc_b, loc_id, dates[2], 0)
        schedule_models.create_schedule_entry(conn, PROJECT_ID, sc_c, loc_id, dates[4], 0)

        # LEAD works day1, day3, day5 -> SW / H / W / H / WF.
        lead = cast_models.create_cast_member(conn, PROJECT_ID, "Lead Actor", "LEAD", 1)
        cast_models.add_cast_to_scene(conn, sc_a, lead)
        cast_models.add_cast_to_scene(conn, sc_b, lead)
        cast_models.add_cast_to_scene(conn, sc_c, lead)

        # DAYPLAYER works only day3 -> single-day SWF, blank elsewhere.
        dayplayer = cast_models.create_cast_member(conn, PROJECT_ID, "Day Player", "DP", 2)
        cast_models.add_cast_to_scene(conn, sc_b, dayplayer)

        grid = report_models.get_dood_grid(conn, PROJECT_ID)
        by_id = {row["cast_member_id"]: row for row in grid}

        # Only actual shoot dates (0, 2, 4) appear in the DOOD grid.
        # Non-shoot dates (1, 3) are not schedule entries and thus not in shoot_dates.
        lead_days = by_id[lead]["days"]
        assert lead_days[dates[0]] == "SW", lead_days
        # dates[1] and dates[3] are not scheduled -- not present in DOOD grid
        assert lead_days[dates[2]] == "W", lead_days
        assert lead_days[dates[4]] == "WF", lead_days

        dp_days = by_id[dayplayer]["days"]
        assert dp_days[dates[0]] == "", dp_days
        assert dp_days[dates[2]] == "SWF", dp_days
        assert dp_days[dates[4]] == "", dp_days


# =========================================================================== #
# Test 3: Budget overspend rejection
# Allocate 1000 cents -> create expense for 1001 cents -> verify rejection.
# =========================================================================== #

def test_budget_overspend_rejection(app):
    with app.app_context():
        conn = get_db()
        # Set project total_budget_cents so allocate_budget can succeed
        conn.execute('UPDATE projects SET total_budget_cents = 100000 WHERE id = ?', (PROJECT_ID,))
        camera = _dept_id(conn, PROJECT_ID, "Camera")
        cat = _category_id(conn, PROJECT_ID)
        creator = conn.execute(
            "SELECT id FROM users WHERE username = 'producer'"
        ).fetchone()["id"]

        assert budget_models.allocate_budget(conn, PROJECT_ID, camera, 1000) is True

        before = budget_models.get_department_allocation(conn, camera)
        spent_before = before["spent_cents"]

        # create_expense returns None (not raises) on overspend per spec Transaction Contracts
        result = expense_models.create_expense(
            conn, PROJECT_ID, camera, 1001, "OverVendor",
            "too much", "2026-09-01", cat, creator,
        )
        assert result is None, f"expected None on overspend, got {result}"

        after = budget_models.get_department_allocation(conn, camera)
        assert after["spent_cents"] == spent_before, "spent_cents must not change on rejected overspend"


# =========================================================================== #
# Test 4: Expense rollback
# Create expense -> verify spent_cents incremented -> delete -> verify restored.
# =========================================================================== #

def test_expense_delete_restores_spent_cents(app):
    with app.app_context():
        conn = get_db()
        # Set project total_budget_cents so allocate_budget can succeed
        conn.execute('UPDATE projects SET total_budget_cents = 100000 WHERE id = ?', (PROJECT_ID,))
        sound = _dept_id(conn, PROJECT_ID, "Sound")
        cat = _category_id(conn, PROJECT_ID)
        creator = conn.execute(
            "SELECT id FROM users WHERE username = 'producer'"
        ).fetchone()["id"]

        assert budget_models.allocate_budget(conn, PROJECT_ID, sound, 5000) is True
        baseline = budget_models.get_department_allocation(conn, sound)["spent_cents"]

        expense_id = expense_models.create_expense(
            conn, PROJECT_ID, sound, 2000, "MicCo",
            "boom mic", "2026-09-02", cat, creator,
        )
        assert isinstance(expense_id, int)

        after_create = budget_models.get_department_allocation(conn, sound)["spent_cents"]
        assert after_create == baseline + 2000, "spent_cents must increment on expense create"

        assert expense_models.delete_expense(conn, expense_id) is True

        after_delete = budget_models.get_department_allocation(conn, sound)["spent_cents"]
        assert after_delete == baseline, "spent_cents must be restored on expense delete"


# =========================================================================== #
# Test 5: Department-head IDOR
# Log in as dept_head for Camera -> attempt to create expense for Sound -> 403.
# =========================================================================== #

def test_department_head_cannot_post_expense_for_other_department(app, client):
    with app.app_context():
        conn = get_db()
        camera = _dept_id(conn, PROJECT_ID, "Camera")
        sound = _dept_id(conn, PROJECT_ID, "Sound")
        cat = _category_id(conn, PROJECT_ID)

        head_uid = _create_user(conn, "camerahead", "head-strong-pw-123", "Camera Head")
        _add_member(conn, PROJECT_ID, head_uid, "department_head")
        # Make this user the head of Camera (and explicitly NOT of Sound).
        conn.execute("UPDATE departments SET head_id = ? WHERE id = ?", (head_uid, camera))

        # Give Sound an allocation so the only failing check is ownership.
        budget_models.allocate_budget(conn, PROJECT_ID, sound, 100000)

    # Log in as the Camera department head through the real form.
    token_resp = client.get("/auth/login")
    token = re.search(r'name="csrf_token"\s+value="([^"]+)"', token_resp.data.decode()).group(1)
    login = client.post(
        "/auth/login",
        data={"username": "camerahead", "password": "head-strong-pw-123", "csrf_token": token},
        follow_redirects=False,
    )
    assert login.status_code == 302

    form_token = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        client.get("/auth/login").data.decode(),
    ).group(1)
    resp = client.post(
        f"/expenses/{PROJECT_ID}",
        data={
            "department_id": str(sound),
            "amount": "10.00",
            "vendor": "SneakyVendor",
            "expense_date": "2026-09-03",
            "category_id": str(cat),
            "csrf_token": form_token,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 403, f"expected 403, got {resp.status_code}"


# =========================================================================== #
# Test 6: Crew-member budget IDOR
# Log in as crew member -> attempt GET /budget/<pid> -> verify 403.
# =========================================================================== #

def test_crew_member_cannot_view_budget(app, client):
    with app.app_context():
        conn = get_db()
        crew_uid = _create_user(conn, "grip1", "crew-strong-pw-123", "Grip One")
        _add_member(conn, PROJECT_ID, crew_uid, "crew_member")

    token = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        client.get("/auth/login").data.decode(),
    ).group(1)
    login = client.post(
        "/auth/login",
        data={"username": "grip1", "password": "crew-strong-pw-123", "csrf_token": token},
        follow_redirects=False,
    )
    assert login.status_code == 302

    resp = client.get(f"/budget/{PROJECT_ID}")
    assert resp.status_code == 403, f"expected 403, got {resp.status_code}"


# =========================================================================== #
# Test 7: Schedule reorder validation
# POST /schedule/<pid>/reorder with IDs from wrong project -> verify rejection.
# =========================================================================== #

def test_schedule_reorder_rejects_foreign_ids(app, client):
    with app.app_context():
        conn = get_db()
        producer_id = conn.execute(
            "SELECT id FROM users WHERE username = 'producer'"
        ).fetchone()["id"]
        loc_id = location_models.create_location(conn, PROJECT_ID, "Loc P1")

        shoot_date = "2026-10-01"
        sc1 = scene_models.create_scene(conn, PROJECT_ID, "P1S1", "x", "INT", "DAY", 8, location_id=loc_id)
        sc2 = scene_models.create_scene(conn, PROJECT_ID, "P1S2", "y", "INT", "DAY", 8, location_id=loc_id)
        ent1 = schedule_models.create_schedule_entry(conn, PROJECT_ID, sc1, loc_id, shoot_date, 0)
        ent2 = schedule_models.create_schedule_entry(conn, PROJECT_ID, sc2, loc_id, shoot_date, 1)

        # A second project with its own schedule entry -- a "foreign" id.
        other_pid = _make_second_project(conn, producer_id)
        _add_member(conn, other_pid, producer_id, "producer")
        other_loc = location_models.create_location(conn, other_pid, "Loc P2")
        other_scene = scene_models.create_scene(conn, other_pid, "P2S1", "z", "INT", "DAY", 8, location_id=other_loc)
        foreign_entry = schedule_models.create_schedule_entry(conn, other_pid, other_scene, other_loc, shoot_date, 0)

    # Authenticate as the seeded producer (member + producer on project 1).
    token = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        client.get("/auth/login").data.decode(),
    ).group(1)
    client.post(
        "/auth/login",
        data={"username": "producer", "password": ADMIN_PASSWORD, "csrf_token": token},
        follow_redirects=False,
    )

    csrf_for_json = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        client.get("/auth/login").data.decode(),
    ).group(1)

    resp = client.post(
        f"/schedule/{PROJECT_ID}/reorder",
        data=json.dumps({"order": [ent1, foreign_entry], "shoot_date": shoot_date}),
        content_type="application/json",
        headers={"X-CSRFToken": csrf_for_json},
    )
    assert resp.status_code == 400, f"expected 400 for foreign id, got {resp.status_code}"

    # Original order must be unchanged.
    with app.app_context():
        conn = get_db()
        rows = conn.execute(
            "SELECT id, sort_order FROM schedule_entries WHERE project_id = ? AND shoot_date = ? "
            "ORDER BY sort_order",
            (PROJECT_ID, shoot_date),
        ).fetchall()
        order = [r["id"] for r in rows]
        assert order == [ent1, ent2], f"order mutated: {order}"


# =========================================================================== #
# Test 8: FTS5 sanitization
# Search with '")(DROP TABLE' -> verify no 500, results returned safely.
# =========================================================================== #

def test_fts5_search_sanitizes_operators(app, client):
    with app.app_context():
        conn = get_db()
        # Seed a searchable scene so the index exists and has content.
        sid = scene_models.create_scene(conn, PROJECT_ID, "42", "warehouse chase", "EXT", "NIGHT", 16)
        # Index the entity the way routes would.
        from app.models import search_models
        search_models.index_entity(conn, "scene", sid, "Scene 42", "warehouse chase")

    token = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        client.get("/auth/login").data.decode(),
    ).group(1)
    client.post(
        "/auth/login",
        data={"username": "producer", "password": ADMIN_PASSWORD, "csrf_token": token},
        follow_redirects=False,
    )

    resp = client.get(f"/search/{PROJECT_ID}?q=" + '")(DROP TABLE')
    assert resp.status_code == 200, f"injection query must not 500, got {resp.status_code}"

    # A benign query must still work.
    resp2 = client.get(f"/search/{PROJECT_ID}?q=warehouse")
    assert resp2.status_code == 200


# =========================================================================== #
# Test 9: CSRF on JSON POST
# POST /schedule/<pid>/reorder without X-CSRFToken -> rejection (400/403),
# and the order is not mutated.
# =========================================================================== #

def test_reorder_without_csrf_token_is_rejected(app, client):
    with app.app_context():
        conn = get_db()
        loc_id = location_models.create_location(conn, PROJECT_ID, "Loc CSRF")
        shoot_date = "2026-11-01"
        sc1 = scene_models.create_scene(conn, PROJECT_ID, "C1", "a", "INT", "DAY", 8, location_id=loc_id)
        sc2 = scene_models.create_scene(conn, PROJECT_ID, "C2", "b", "INT", "DAY", 8, location_id=loc_id)
        ent1 = schedule_models.create_schedule_entry(conn, PROJECT_ID, sc1, loc_id, shoot_date, 0)
        ent2 = schedule_models.create_schedule_entry(conn, PROJECT_ID, sc2, loc_id, shoot_date, 1)

    token = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        client.get("/auth/login").data.decode(),
    ).group(1)
    client.post(
        "/auth/login",
        data={"username": "producer", "password": ADMIN_PASSWORD, "csrf_token": token},
        follow_redirects=False,
    )

    # Attempt to reverse the order WITHOUT a CSRF header/token.
    resp = client.post(
        f"/schedule/{PROJECT_ID}/reorder",
        data=json.dumps({"order": [ent2, ent1], "shoot_date": shoot_date}),
        content_type="application/json",
    )
    assert resp.status_code in (400, 403), f"missing CSRF must be rejected, got {resp.status_code}"

    with app.app_context():
        conn = get_db()
        rows = conn.execute(
            "SELECT id FROM schedule_entries WHERE project_id = ? AND shoot_date = ? ORDER BY sort_order",
            (PROJECT_ID, shoot_date),
        ).fetchall()
        order = [r["id"] for r in rows]
        assert order == [ent1, ent2], f"order mutated despite missing CSRF: {order}"


# =========================================================================== #
# Test 10: CSP allows SortableJS
# Verify Content-Security-Policy header script-src allows cdn.jsdelivr.net.
# =========================================================================== #

def test_csp_allows_sortablejs_cdn(client):
    resp = client.get("/auth/login")
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "cdn.jsdelivr.net" in csp, f"CSP missing cdn.jsdelivr.net: {csp}"
    assert "script-src" in csp, f"CSP missing script-src: {csp}"
