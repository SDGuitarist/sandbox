"""Shared fixtures for Film Production PM Tool tests."""
import os
import re
import pytest

# Set environment before importing app
os.environ["SECRET_KEY"] = "test-secret-key-not-production"
os.environ["ADMIN_PASSWORD"] = "test-pw"
os.environ["DATABASE"] = ":memory:"


@pytest.fixture()
def app():
    """Create app with in-memory database for testing."""
    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = True
    yield application


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


def _get_csrf_token(client, url):
    """Fetch a page and extract the CSRF token from the form."""
    r = client.get(url)
    html = r.data.decode()
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    # Try meta tag fallback
    m = re.search(r'name="csrf-token"\s+content="([^"]+)"', html)
    return m.group(1) if m else ""


def login_as_producer(client):
    """Log in as the producer user (seeded by database init)."""
    token = _get_csrf_token(client, "/auth/login")
    client.post("/auth/login", data={
        "username": "producer",
        "password": os.environ["ADMIN_PASSWORD"],
        "csrf_token": token,
    }, follow_redirects=False)


def login_as_ad(client):
    """Log in as the AD (assistant director) user."""
    token = _get_csrf_token(client, "/auth/login")
    client.post("/auth/login", data={
        "username": "ad_user",
        "password": "testpass123",
        "csrf_token": token,
    }, follow_redirects=False)


def login_as_dept_head(client):
    """Log in as a department head user."""
    token = _get_csrf_token(client, "/auth/login")
    client.post("/auth/login", data={
        "username": "dept_head_user",
        "password": "testpass123",
        "csrf_token": token,
    }, follow_redirects=False)


def login_as_crew(client):
    """Log in as a crew member user."""
    token = _get_csrf_token(client, "/auth/login")
    client.post("/auth/login", data={
        "username": "crew_user",
        "password": "testpass123",
        "csrf_token": token,
    }, follow_redirects=False)


@pytest.fixture()
def seed(app, client):
    """Seed the database with test data for all roles and entities.

    Returns a dict of IDs for use in tests:
      producer_id, ad_id, dept_head_id, crew_id,
      project_id, camera_dept_id, sound_dept_id,
      scene1_id, scene2_id, scene3_id,
      cast1_id, cast2_id,
      crew_member_id, location_id,
      schedule1_id, schedule2_id, schedule3_id,
      budget_cat_id
    """
    with app.app_context():
        from app.database import get_db
        from werkzeug.security import generate_password_hash
        conn = get_db()

        # ----------------------------------------------------------
        # The producer user (id=1) and project (id=1) are already
        # seeded by init_db. Look them up.
        # ----------------------------------------------------------
        producer = conn.execute(
            "SELECT id FROM users WHERE username = 'producer'"
        ).fetchone()
        producer_id = producer["id"]
        project_id = 1

        # ----------------------------------------------------------
        # Create additional users: AD, department head, crew member
        # ----------------------------------------------------------
        pw_hash = generate_password_hash("testpass123")

        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
                ("ad_user", pw_hash, "Assistant Director"),
            )
            conn.execute(
                "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
                ("dept_head_user", pw_hash, "Dept Head"),
            )
            conn.execute(
                "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
                ("crew_user", pw_hash, "Crew Member"),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        ad = conn.execute("SELECT id FROM users WHERE username = 'ad_user'").fetchone()
        ad_id = ad["id"]
        dh = conn.execute("SELECT id FROM users WHERE username = 'dept_head_user'").fetchone()
        dept_head_id = dh["id"]
        cr = conn.execute("SELECT id FROM users WHERE username = 'crew_user'").fetchone()
        crew_id = cr["id"]

        # ----------------------------------------------------------
        # Add all users as project members with appropriate roles
        # ----------------------------------------------------------
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT OR IGNORE INTO project_members (project_id, user_id, role) VALUES (?, ?, 'ad')",
                (project_id, ad_id),
            )
            conn.execute(
                "INSERT OR IGNORE INTO project_members (project_id, user_id, role) VALUES (?, ?, 'department_head')",
                (project_id, dept_head_id),
            )
            conn.execute(
                "INSERT OR IGNORE INTO project_members (project_id, user_id, role) VALUES (?, ?, 'crew_member')",
                (project_id, crew_id),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        # ----------------------------------------------------------
        # Look up departments (seeded by init_db): Camera and Sound
        # ----------------------------------------------------------
        camera_dept = conn.execute(
            "SELECT id FROM departments WHERE project_id = ? AND name = 'Camera'",
            (project_id,),
        ).fetchone()
        camera_dept_id = camera_dept["id"]

        sound_dept = conn.execute(
            "SELECT id FROM departments WHERE project_id = ? AND name = 'Sound'",
            (project_id,),
        ).fetchone()
        sound_dept_id = sound_dept["id"]

        # Assign dept_head_user as head of Camera department
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "UPDATE departments SET head_id = ? WHERE id = ?",
                (dept_head_id, camera_dept_id),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        # ----------------------------------------------------------
        # Create a location
        # ----------------------------------------------------------
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT INTO locations (project_id, name, address, nearest_hospital) VALUES (?, ?, ?, ?)",
                (project_id, "Stage A", "123 Studio Lot", "City General"),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        location = conn.execute(
            "SELECT id FROM locations WHERE project_id = ? AND name = 'Stage A'",
            (project_id,),
        ).fetchone()
        location_id = location["id"]

        # ----------------------------------------------------------
        # Create 3 scenes
        # ----------------------------------------------------------
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT INTO scenes (project_id, scene_number, description, int_ext, day_night, page_count_eighths, location_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (project_id, "1", "Opening shot", "INT", "DAY", 8, location_id),
            )
            conn.execute(
                "INSERT INTO scenes (project_id, scene_number, description, int_ext, day_night, page_count_eighths, location_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (project_id, "2", "Chase scene", "EXT", "NIGHT", 16, location_id),
            )
            conn.execute(
                "INSERT INTO scenes (project_id, scene_number, description, int_ext, day_night, page_count_eighths, location_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (project_id, "3", "Dialogue scene", "INT", "DAY", 12, None),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        scene1 = conn.execute(
            "SELECT id FROM scenes WHERE project_id = ? AND scene_number = '1'", (project_id,)
        ).fetchone()
        scene1_id = scene1["id"]
        scene2 = conn.execute(
            "SELECT id FROM scenes WHERE project_id = ? AND scene_number = '2'", (project_id,)
        ).fetchone()
        scene2_id = scene2["id"]
        scene3 = conn.execute(
            "SELECT id FROM scenes WHERE project_id = ? AND scene_number = '3'", (project_id,)
        ).fetchone()
        scene3_id = scene3["id"]

        # ----------------------------------------------------------
        # Create 2 cast members
        # ----------------------------------------------------------
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT INTO cast_members (project_id, name, character_name, cast_id_number) VALUES (?, ?, ?, ?)",
                (project_id, "Alice Actor", "Hero", 1),
            )
            conn.execute(
                "INSERT INTO cast_members (project_id, name, character_name, cast_id_number) VALUES (?, ?, ?, ?)",
                (project_id, "Bob Thespian", "Villain", 2),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        cast1 = conn.execute(
            "SELECT id FROM cast_members WHERE project_id = ? AND cast_id_number = 1", (project_id,)
        ).fetchone()
        cast1_id = cast1["id"]
        cast2 = conn.execute(
            "SELECT id FROM cast_members WHERE project_id = ? AND cast_id_number = 2", (project_id,)
        ).fetchone()
        cast2_id = cast2["id"]

        # Assign cast to scenes
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Cast 1 (Hero) in scenes 1, 2, 3
            conn.execute(
                "INSERT INTO scene_cast (scene_id, cast_member_id) VALUES (?, ?)",
                (scene1_id, cast1_id),
            )
            conn.execute(
                "INSERT INTO scene_cast (scene_id, cast_member_id) VALUES (?, ?)",
                (scene2_id, cast1_id),
            )
            conn.execute(
                "INSERT INTO scene_cast (scene_id, cast_member_id) VALUES (?, ?)",
                (scene3_id, cast1_id),
            )
            # Cast 2 (Villain) in scenes 1 and 3 only
            conn.execute(
                "INSERT INTO scene_cast (scene_id, cast_member_id) VALUES (?, ?)",
                (scene1_id, cast2_id),
            )
            conn.execute(
                "INSERT INTO scene_cast (scene_id, cast_member_id) VALUES (?, ?)",
                (scene3_id, cast2_id),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        # ----------------------------------------------------------
        # Create a crew member
        # ----------------------------------------------------------
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT INTO crew_members (project_id, name, role_title, department_id, daily_rate_cents) VALUES (?, ?, ?, ?, ?)",
                (project_id, "Charlie Camera", "1st AC", camera_dept_id, 50000),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        crew_member = conn.execute(
            "SELECT id FROM crew_members WHERE project_id = ? AND name = 'Charlie Camera'",
            (project_id,),
        ).fetchone()
        crew_member_id = crew_member["id"]

        # ----------------------------------------------------------
        # Create schedule entries across 5 days for DOOD testing
        # Day 1: scene 1 (cast 1 + 2)
        # Day 2: scene 2 (cast 1 only)
        # Day 3: no scenes scheduled -- will be hold day for cast between first/last
        # Day 4: scene 3 (cast 1 + 2)
        # Day 5: nothing -- beyond last working day
        # ----------------------------------------------------------
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT INTO schedule_entries (project_id, scene_id, location_id, shoot_date, sort_order) VALUES (?, ?, ?, ?, ?)",
                (project_id, scene1_id, location_id, "2026-07-01", 0),
            )
            conn.execute(
                "INSERT INTO schedule_entries (project_id, scene_id, location_id, shoot_date, sort_order) VALUES (?, ?, ?, ?, ?)",
                (project_id, scene2_id, location_id, "2026-07-02", 0),
            )
            conn.execute(
                "INSERT INTO schedule_entries (project_id, scene_id, location_id, shoot_date, sort_order) VALUES (?, ?, ?, ?, ?)",
                (project_id, scene3_id, location_id, "2026-07-04", 0),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        sched1 = conn.execute(
            "SELECT id FROM schedule_entries WHERE project_id = ? AND scene_id = ?",
            (project_id, scene1_id),
        ).fetchone()
        schedule1_id = sched1["id"]
        sched2 = conn.execute(
            "SELECT id FROM schedule_entries WHERE project_id = ? AND scene_id = ?",
            (project_id, scene2_id),
        ).fetchone()
        schedule2_id = sched2["id"]
        sched3 = conn.execute(
            "SELECT id FROM schedule_entries WHERE project_id = ? AND scene_id = ?",
            (project_id, scene3_id),
        ).fetchone()
        schedule3_id = sched3["id"]

        # ----------------------------------------------------------
        # Create a budget category (use one from seed: "Camera" = acct 2900)
        # ----------------------------------------------------------
        budget_cat = conn.execute(
            "SELECT id FROM budget_categories WHERE project_id = ? AND account_number = '2900'",
            (project_id,),
        ).fetchone()
        budget_cat_id = budget_cat["id"]

    return {
        "producer_id": producer_id,
        "ad_id": ad_id,
        "dept_head_id": dept_head_id,
        "crew_id": crew_id,
        "project_id": project_id,
        "camera_dept_id": camera_dept_id,
        "sound_dept_id": sound_dept_id,
        "scene1_id": scene1_id,
        "scene2_id": scene2_id,
        "scene3_id": scene3_id,
        "cast1_id": cast1_id,
        "cast2_id": cast2_id,
        "crew_member_id": crew_member_id,
        "location_id": location_id,
        "schedule1_id": schedule1_id,
        "schedule2_id": schedule2_id,
        "schedule3_id": schedule3_id,
        "budget_cat_id": budget_cat_id,
    }
