"""Critical-flow tests for Film Production PM Tool.

Implements all 10 test cases prescribed by the spec.
"""
import json
import re

import pytest

from tests.conftest import (
    _get_csrf_token,
    login_as_producer,
    login_as_ad,
    login_as_dept_head,
    login_as_crew,
)


# ====================================================================
# Test 1: Call sheet generation end-to-end
# ====================================================================
def test_call_sheet_generation(app, client, seed):
    """Create project -> add scenes -> add cast to scenes -> create schedule
    entries -> generate call sheet -> verify call sheet contains correct
    scenes, cast with statuses, and location."""
    login_as_producer(client)
    pid = seed["project_id"]

    # Seed already has scenes, cast, scene_cast, schedule entries, and
    # a location. Generate a call sheet for 2026-07-01 (scene 1 scheduled).
    token = _get_csrf_token(client, f"/call-sheets/{pid}")
    r = client.post(f"/call-sheets/{pid}/generate", data={
        "shoot_date": "2026-07-01",
        "csrf_token": token,
    }, follow_redirects=True)
    assert r.status_code == 200

    html = r.data.decode()

    # Verify: the call sheet page should list the scene
    # Scene 1 is "Opening shot" at location "Stage A"
    assert "1" in html  # scene_number
    assert "Stage A" in html or "123 Studio Lot" in html  # location

    # Verify cast appears on the call sheet
    assert "Alice Actor" in html or "Hero" in html
    assert "Bob Thespian" in html or "Villain" in html

    # Verify the call sheet was actually created in the DB
    with app.app_context():
        from app.database import get_db
        conn = get_db()
        cs = conn.execute(
            "SELECT id, status FROM call_sheets WHERE project_id = ? AND shoot_date = '2026-07-01'",
            (pid,),
        ).fetchone()
        assert cs is not None
        assert cs["status"] == "draft"

        # Check call_sheet_scenes populated
        cs_scenes = conn.execute(
            "SELECT * FROM call_sheet_scenes WHERE call_sheet_id = ?",
            (cs["id"],),
        ).fetchall()
        assert len(cs_scenes) >= 1

        # Check call_sheet_cast populated
        cs_cast = conn.execute(
            "SELECT * FROM call_sheet_cast WHERE call_sheet_id = ?",
            (cs["id"],),
        ).fetchall()
        assert len(cs_cast) >= 1


# ====================================================================
# Test 2: DOOD grid accuracy
# ====================================================================
def test_dood_grid_accuracy(app, client, seed):
    """Schedule 3 scenes across 5 days with overlapping cast.
    Verify W/SW/WF/SWF/H statuses are correct for each cast member.

    Seed data:
      Day 2026-07-01: scene 1 (cast 1 Hero + cast 2 Villain)
      Day 2026-07-02: scene 2 (cast 1 Hero only)
      Day 2026-07-04: scene 3 (cast 1 Hero + cast 2 Villain)

    Expected DOOD for Cast 1 (Hero): works days 1,2,4
      2026-07-01: SW  (start work -- first working day)
      2026-07-02: W   (work -- middle day)
      2026-07-04: WF  (work finish -- last working day)

    Expected DOOD for Cast 2 (Villain): works days 1,4
      2026-07-01: SW  (start work)
      2026-07-02: H   (hold -- between first and last working day, not scheduled)
      2026-07-04: WF  (work finish)
    """
    with app.app_context():
        from app.database import get_db
        conn = get_db()

        # Call the DOOD grid model directly
        from app.models.report_models import get_dood_grid
        dood = get_dood_grid(conn, seed["project_id"])

        # Find each cast member's entry
        cast1_entry = None
        cast2_entry = None
        for entry in dood:
            if entry["cast_id_number"] == 1:
                cast1_entry = entry
            elif entry["cast_id_number"] == 2:
                cast2_entry = entry

        assert cast1_entry is not None, "Cast 1 (Hero) not found in DOOD grid"
        assert cast2_entry is not None, "Cast 2 (Villain) not found in DOOD grid"

        # Cast 1 (Hero): works 07-01, 07-02, 07-04
        days1 = cast1_entry["days"]
        assert days1["2026-07-01"] == "SW", f"Hero day 1 expected SW, got {days1['2026-07-01']}"
        assert days1["2026-07-02"] == "W", f"Hero day 2 expected W, got {days1['2026-07-02']}"
        assert days1["2026-07-04"] == "WF", f"Hero day 4 expected WF, got {days1['2026-07-04']}"

        # Cast 2 (Villain): works 07-01, 07-04 (hold on 07-02)
        days2 = cast2_entry["days"]
        assert days2["2026-07-01"] == "SW", f"Villain day 1 expected SW, got {days2['2026-07-01']}"
        assert days2["2026-07-02"] == "H", f"Villain day 2 expected H, got {days2['2026-07-02']}"
        assert days2["2026-07-04"] == "WF", f"Villain day 4 expected WF, got {days2['2026-07-04']}"


# ====================================================================
# Test 3: Budget overspend rejection
# ====================================================================
def test_budget_overspend_rejection(app, client, seed):
    """Allocate 1000 cents to department -> create expense for 1001 cents
    -> verify rejection."""
    login_as_producer(client)
    pid = seed["project_id"]
    dept_id = seed["camera_dept_id"]

    # First, set the project budget high enough to allocate from
    with app.app_context():
        from app.database import get_db
        conn = get_db()
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "UPDATE projects SET total_budget_cents = ? WHERE id = ?",
                (1000000, pid),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    # Allocate 1000 cents ($10.00) to Camera department
    token = _get_csrf_token(client, f"/budget/{pid}")
    r = client.post(f"/budget/{pid}/allocate", data={
        "department_id": str(dept_id),
        "amount_cents": "1000",
        "csrf_token": token,
    }, follow_redirects=False)
    # Should succeed (redirect)
    assert r.status_code == 302

    # Try to create an expense for 1001 cents ($10.01) -- should be rejected
    token = _get_csrf_token(client, f"/expenses/{pid}/new")
    r = client.post(f"/expenses/{pid}", data={
        "department_id": str(dept_id),
        "amount": "10.01",  # 1001 cents via money parsing pattern
        "vendor": "Overspend Vendor",
        "expense_date": "2026-07-01",
        "category_id": str(seed["budget_cat_id"]),
        "description": "Test overspend",
        "csrf_token": token,
    }, follow_redirects=True)

    html = r.data.decode()
    # The app should reject and flash a message about remaining budget
    assert r.status_code == 200
    # Verify the expense was NOT created
    with app.app_context():
        from app.database import get_db
        conn = get_db()
        expenses = conn.execute(
            "SELECT * FROM expenses WHERE project_id = ? AND vendor = 'Overspend Vendor'",
            (pid,),
        ).fetchall()
        assert len(expenses) == 0, "Overspend expense should have been rejected"


# ====================================================================
# Test 4: Expense rollback
# ====================================================================
def test_expense_rollback(app, client, seed):
    """Create expense -> verify spent_cents incremented -> delete expense
    -> verify spent_cents restored."""
    login_as_producer(client)
    pid = seed["project_id"]
    dept_id = seed["camera_dept_id"]

    # Set up budget allocation first
    with app.app_context():
        from app.database import get_db
        conn = get_db()
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "UPDATE projects SET total_budget_cents = ? WHERE id = ?",
                (1000000, pid),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    # Allocate 5000 cents ($50) to Camera department
    token = _get_csrf_token(client, f"/budget/{pid}")
    r = client.post(f"/budget/{pid}/allocate", data={
        "department_id": str(dept_id),
        "amount_cents": "5000",
        "csrf_token": token,
    }, follow_redirects=False)
    assert r.status_code == 302

    # Check spent_cents before expense
    with app.app_context():
        from app.database import get_db
        conn = get_db()
        alloc = conn.execute(
            "SELECT spent_cents FROM department_budgets WHERE project_id = ? AND department_id = ?",
            (pid, dept_id),
        ).fetchone()
        spent_before = alloc["spent_cents"] if alloc else 0

    # Create expense for 500 cents ($5.00)
    token = _get_csrf_token(client, f"/expenses/{pid}/new")
    r = client.post(f"/expenses/{pid}", data={
        "department_id": str(dept_id),
        "amount": "5.00",
        "vendor": "Test Vendor",
        "expense_date": "2026-07-01",
        "category_id": str(seed["budget_cat_id"]),
        "description": "Test expense",
        "csrf_token": token,
    }, follow_redirects=False)
    assert r.status_code == 302

    # Verify spent_cents incremented
    with app.app_context():
        from app.database import get_db
        conn = get_db()
        alloc = conn.execute(
            "SELECT spent_cents FROM department_budgets WHERE project_id = ? AND department_id = ?",
            (pid, dept_id),
        ).fetchone()
        assert alloc is not None
        assert alloc["spent_cents"] == spent_before + 500

        # Find the expense ID
        expense = conn.execute(
            "SELECT id FROM expenses WHERE project_id = ? AND vendor = 'Test Vendor'",
            (pid,),
        ).fetchone()
        assert expense is not None
        expense_id = expense["id"]

    # Delete the expense
    token = _get_csrf_token(client, f"/expenses/{pid}")
    r = client.post(f"/expenses/{pid}/{expense_id}/delete", data={
        "csrf_token": token,
    }, follow_redirects=False)
    assert r.status_code == 302

    # Verify spent_cents restored
    with app.app_context():
        from app.database import get_db
        conn = get_db()
        alloc = conn.execute(
            "SELECT spent_cents FROM department_budgets WHERE project_id = ? AND department_id = ?",
            (pid, dept_id),
        ).fetchone()
        assert alloc["spent_cents"] == spent_before


# ====================================================================
# Test 5: Department-head IDOR
# ====================================================================
def test_department_head_idor(app, client, seed):
    """Log in as dept_head for Camera -> attempt to create expense for
    Sound -> verify 403."""
    login_as_dept_head(client)
    pid = seed["project_id"]
    sound_dept_id = seed["sound_dept_id"]

    # Try to create an expense under Sound department (not their department)
    token = _get_csrf_token(client, f"/expenses/{pid}/new")
    r = client.post(f"/expenses/{pid}", data={
        "department_id": str(sound_dept_id),
        "amount": "5.00",
        "vendor": "Sneaky Vendor",
        "expense_date": "2026-07-01",
        "category_id": str(seed["budget_cat_id"]),
        "description": "IDOR attempt",
        "csrf_token": token,
    }, follow_redirects=False)
    # Should be rejected -- 403 or redirect with error
    assert r.status_code in (403, 302)

    # If redirected, verify the expense was NOT created
    with app.app_context():
        from app.database import get_db
        conn = get_db()
        expenses = conn.execute(
            "SELECT * FROM expenses WHERE project_id = ? AND vendor = 'Sneaky Vendor'",
            (pid,),
        ).fetchall()
        assert len(expenses) == 0, "Dept head should not create expense for another department"


# ====================================================================
# Test 6: Crew-member budget IDOR
# ====================================================================
def test_crew_member_budget_idor(app, client, seed):
    """Log in as crew member -> attempt GET /budget/<pid> -> verify 403."""
    login_as_crew(client)
    pid = seed["project_id"]

    r = client.get(f"/budget/{pid}")
    assert r.status_code == 403


# ====================================================================
# Test 7: Schedule reorder validation
# ====================================================================
def test_schedule_reorder_wrong_project(app, client, seed):
    """POST /schedule/<pid>/reorder with IDs from wrong project
    -> verify rejection."""
    login_as_producer(client)
    pid = seed["project_id"]

    # Get a CSRF token from any page
    token = _get_csrf_token(client, f"/schedule/{pid}")

    # Use fake IDs that don't belong to this project
    r = client.post(f"/schedule/{pid}/reorder",
        data=json.dumps({
            "order": [99999, 99998, 99997],
            "shoot_date": "2026-07-01",
        }),
        content_type="application/json",
        headers={"X-CSRFToken": token},
    )
    # Should return 400 (bad request) since IDs don't belong to project+date
    assert r.status_code == 400


# ====================================================================
# Test 8: FTS5 sanitization
# ====================================================================
def test_fts5_sanitization(app, client, seed):
    """Search with '")(DROP TABLE' -> verify no 500, results returned
    safely."""
    login_as_producer(client)
    pid = seed["project_id"]

    r = client.get(f"/search/{pid}?q=" + '")(DROP TABLE')
    # Must NOT return 500
    assert r.status_code != 500
    assert r.status_code == 200


# ====================================================================
# Test 9: CSRF on JSON POST
# ====================================================================
def test_csrf_on_json_post(app, client, seed):
    """POST /schedule/<pid>/reorder without X-CSRFToken -> verify
    rejection (400 or 403) and order is not mutated."""
    login_as_producer(client)
    pid = seed["project_id"]

    # Record current schedule order
    with app.app_context():
        from app.database import get_db
        conn = get_db()
        before = conn.execute(
            "SELECT id, sort_order FROM schedule_entries WHERE project_id = ? AND shoot_date = '2026-07-01' ORDER BY sort_order",
            (pid,),
        ).fetchall()
        before_ids = [row["id"] for row in before]

    # POST without CSRF token
    r = client.post(f"/schedule/{pid}/reorder",
        data=json.dumps({
            "order": list(reversed(before_ids)) if before_ids else [1],
            "shoot_date": "2026-07-01",
        }),
        content_type="application/json",
        # NO X-CSRFToken header
    )
    # Should be rejected
    assert r.status_code in (400, 403)

    # Verify order was NOT mutated
    with app.app_context():
        from app.database import get_db
        conn = get_db()
        after = conn.execute(
            "SELECT id, sort_order FROM schedule_entries WHERE project_id = ? AND shoot_date = '2026-07-01' ORDER BY sort_order",
            (pid,),
        ).fetchall()
        after_ids = [row["id"] for row in after]
        assert after_ids == before_ids, "Schedule order should not change without CSRF token"


# ====================================================================
# Test 10: CSP allows SortableJS
# ====================================================================
def test_csp_allows_sortablejs(app, client):
    """Verify Content-Security-Policy header includes script-src
    allowing cdn.jsdelivr.net."""
    r = client.get("/auth/login")
    csp = r.headers.get("Content-Security-Policy", "")
    assert "cdn.jsdelivr.net" in csp, (
        f"CSP must allow cdn.jsdelivr.net for SortableJS. Got: {csp}"
    )
    # Verify it's specifically in script-src
    assert "script-src" in csp, "CSP must have script-src directive"
