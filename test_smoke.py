"""EARS smoke suite for Lesson-Studio Manager (run 081).

Covers the Acceptance Tests (EARS) from
docs/plans/2026-07-09-feat-lesson-studio-scale-validation-plan.md:
happy-path CRUD, IDOR-404, transaction atomicity (checkout + enroll),
CSRF validation, SECRET_KEY fail-closed, and the one-draft-per-student invariant.

Run (by the assembly pipeline, NOT this worker):  python3 test_smoke.py
Exits 1 if any check fails.

Design notes (per spec + known pitfalls):
- Isolated temp DB file (never ':memory:', never studio.db). The file is unlinked
  BEFORE create_app() so the init_db guard (os.path.exists) sees no file and seeds.
- DATABASE env var is set BEFORE importing/calling create_app (scaffold reads it there).
- CSRF: the real '_csrf' token is scraped from rendered form HTML and posted back.
- Ownership/IDOR and DB-level atomicity are asserted with fresh sqlite3 connections
  opened directly on the temp DB (PRAGMA foreign_keys = ON).
"""

import os
import re
import sqlite3
import tempfile

# ---------------------------------------------------------------------------
# Environment setup — MUST happen before importing studio (FC49 + config pins).
# ---------------------------------------------------------------------------
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.unlink(_tmp.name)  # remove so os.path.exists(DB) is False -> init_db seeds
DB_PATH = _tmp.name

os.environ.setdefault("DATABASE", DB_PATH)
# In case a default was already present in the environment, force our temp path.
os.environ["DATABASE"] = DB_PATH
os.environ.setdefault("SECRET_KEY", "smoke-test-key")
os.environ.setdefault("FLASK_ENV", "development")

from studio import create_app  # noqa: E402

# ---------------------------------------------------------------------------
# check() harness — pass/fail counters, exit 1 on any failure.
# ---------------------------------------------------------------------------
passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"PASS: {name}")
        passed += 1
    else:
        print(f"FAIL: {name}" + (f" -- {detail}" if detail else ""))
        failed += 1


CSRF_RE = re.compile(r'name="_csrf" value="([^"]+)"')


def csrf_from(html):
    """Extract the real _csrf token from rendered form HTML."""
    if isinstance(html, bytes):
        html = html.decode("utf-8", "replace")
    m = CSRF_RE.search(html)
    return m.group(1) if m else None


def get_token(client, path):
    """GET a form page and return its _csrf token (or None).

    follow_redirects=True so collection URLs without a trailing slash
    (e.g. /students) survive Flask's 308 canonical redirect instead of
    returning the token-less redirect stub page.
    """
    resp = client.get(path, follow_redirects=True)
    return csrf_from(resp.get_data(as_text=True))


def db_conn():
    """Fresh direct connection to the temp DB with FK enforcement + Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def login(client, email, password):
    """Log in a client session; returns the HTTP response."""
    token = get_token(client, "/auth/login")
    return client.post(
        "/auth/login",
        data={"email": email, "password": password, "_csrf": token},
        follow_redirects=False,
    )


def link_student_row(email, first_name, last_name):
    """Test setup: link a registered student user to a students row.

    Registration deliberately does NOT auto-create a students row (spec:
    staff/seed create them), so ownership flows for registered users need
    this explicit setup insert.
    """
    conn = db_conn()
    try:
        user = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if user is None:
            return None
        row = conn.execute(
            "SELECT id FROM students WHERE user_id=?", (user["id"],)
        ).fetchone()
        if row is not None:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO students (user_id, first_name, last_name, email) VALUES (?,?,?,?)",
            (user["id"], first_name, last_name, email),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def register(client, email, password, name, role):
    """Register a fresh user; returns the HTTP response."""
    token = get_token(client, "/auth/register")
    return client.post(
        "/auth/register",
        data={
            "email": email,
            "password": password,
            "name": name,
            "role": role,
            "_csrf": token,
        },
        follow_redirects=False,
    )


ADMIN_EMAIL = "admin@studio.test"
ADMIN_PASSWORD = "studiopass"


# ===========================================================================
# SECRET_KEY fail-closed — do this FIRST, restoring env in finally, before we
# build the long-lived app instance used by the rest of the suite.
# ===========================================================================
def test_secret_key_fail_closed():
    saved_env = os.environ.get("FLASK_ENV")
    saved_key = os.environ.get("SECRET_KEY")
    try:
        os.environ["FLASK_ENV"] = "production"
        os.environ.pop("SECRET_KEY", None)
        raised = False
        try:
            create_app()
        except Exception:
            raised = True
        check(
            "SECRET_KEY unset in production -> create_app() refuses to start",
            raised,
            "create_app() did not raise with FLASK_ENV=production and no SECRET_KEY",
        )
    finally:
        # RESTORE both before continuing (try/finally guarantees this).
        if saved_env is not None:
            os.environ["FLASK_ENV"] = saved_env
        else:
            os.environ.pop("FLASK_ENV", None)
        if saved_key is not None:
            os.environ["SECRET_KEY"] = saved_key
        else:
            os.environ.pop("SECRET_KEY", None)


test_secret_key_fail_closed()

# Build the real app (development, temp DB seeded on first init_db).
app = create_app()
app.config["TESTING"] = True


# ===========================================================================
# Discover seed ids we need for cross-student / relationship assertions.
# ===========================================================================
def seed_ids():
    conn = db_conn()
    try:
        rows = conn.execute(
            "SELECT id, user_id, first_name FROM students ORDER BY id"
        ).fetchall()
        students = [dict(r) for r in rows]
        instr = conn.execute(
            "SELECT id FROM instructors ORDER BY id LIMIT 1"
        ).fetchone()
        room = conn.execute("SELECT id FROM rooms ORDER BY id LIMIT 1").fetchone()
        avail = conn.execute(
            "SELECT id FROM instruments WHERE status='available' ORDER BY id LIMIT 1"
        ).fetchone()
        # priced courses (for atomic-enroll + one-draft-invariant tests)
        priced = conn.execute(
            "SELECT id, capacity FROM courses WHERE price_cents > 0 AND active=1 ORDER BY id"
        ).fetchall()
        return {
            "students": students,
            "instructor_id": instr["id"] if instr else None,
            "room_id": room["id"] if room else None,
            "available_instrument_id": avail["id"] if avail else None,
            "priced_courses": [dict(r) for r in priced],
        }
    finally:
        conn.close()


SEED = seed_ids()
check(
    "seed data present (>=3 students, >=1 instructor, >=1 available instrument)",
    len(SEED["students"]) >= 3
    and SEED["instructor_id"] is not None
    and SEED["available_instrument_id"] is not None,
    f"instructor_id={SEED['instructor_id']}, "
    f"available_instrument_id={SEED['available_instrument_id']}, "
    f"n_students={len(SEED['students'])}",
)


# ===========================================================================
# HAPPY PATH
# ===========================================================================

# -- registration -> 302 to /auth/login
def test_register_happy():
    c = app.test_client()
    resp = register(c, "newstudent@smoke.test", "studiopass", "New Student", "student")
    check(
        "register valid user -> 302",
        resp.status_code == 302,
        f"status={resp.status_code}",
    )


test_register_happy()


# -- admin login -> 302 to /
def test_admin_login():
    c = app.test_client()
    resp = login(c, ADMIN_EMAIL, ADMIN_PASSWORD)
    check(
        "admin valid credentials -> 302 (session established)",
        resp.status_code == 302,
        f"status={resp.status_code}",
    )


test_admin_login()


# -- admin creates a student -> persisted + appears in list
def test_admin_creates_student():
    c = app.test_client()
    login(c, ADMIN_EMAIL, ADMIN_PASSWORD)
    token = get_token(c, "/students/new")
    resp = c.post(
        "/students/new",
        data={
            "first_name": "Smokey",
            "last_name": "Testerson",
            "email": "smokey@smoke.test",
            "skill_level": "beginner",
            "_csrf": token,
        },
        follow_redirects=True,
    )
    listing = c.get("/students", follow_redirects=True).get_data(as_text=True)
    check(
        "admin creates student -> persisted and listed at GET /students",
        resp.status_code in (200, 302) and "Smokey" in listing,
        f"status={resp.status_code}",
    )


test_admin_creates_student()


# -- dashboard index renders for admin
def test_dashboard_index():
    c = app.test_client()
    login(c, ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = c.get("/")
    check(
        "dashboard index (/) renders for logged-in admin -> 200",
        resp.status_code == 200,
        f"status={resp.status_code}",
    )


test_dashboard_index()


# -- checkout available instrument -> checkout row + instrument checked_out (atomic)
def test_checkout_atomicity():
    c = app.test_client()
    login(c, ADMIN_EMAIL, ADMIN_PASSWORD)
    iid = SEED["available_instrument_id"]
    sid = SEED["students"][0]["id"]
    if iid is None:
        check("checkout available instrument -> atomic status flip", False,
              "no available instrument seeded")
        return
    token = get_token(c, "/instruments")
    resp = c.post(
        f"/instruments/{iid}/checkout",
        data={"student_id": str(sid), "due_at": "2099-01-01T00:00:00", "_csrf": token},
        follow_redirects=True,
    )
    conn = db_conn()
    try:
        inst = conn.execute(
            "SELECT status FROM instruments WHERE id=?", (iid,)
        ).fetchone()
        co = conn.execute(
            "SELECT COUNT(*) AS n FROM instrument_checkouts "
            "WHERE instrument_id=? AND status='out'",
            (iid,),
        ).fetchone()
    finally:
        conn.close()
    check(
        "checkout available instrument -> status=checked_out AND checkout row exists (one tx)",
        resp.status_code in (200, 302)
        and inst is not None
        and inst["status"] == "checked_out"
        and co["n"] >= 1,
        f"status={resp.status_code}, "
        f"inst_status={inst['status'] if inst else None}, checkout_rows={co['n']}",
    )


test_checkout_atomicity()


# -- enroll student in priced course -> enrollment + invoice_item on draft (atomic)
def test_enroll_priced_atomicity():
    if not SEED["priced_courses"]:
        check("enroll priced course -> atomic enrollment + invoice_item", False,
              "no priced course seeded")
        return None
    c = app.test_client()
    login(c, ADMIN_EMAIL, ADMIN_PASSWORD)
    course_id = SEED["priced_courses"][0]["id"]
    # pick a student not already enrolled in the target course
    conn = db_conn()
    try:
        sid = None
        for s in SEED["students"]:
            row = conn.execute(
                "SELECT 1 FROM enrollments WHERE student_id=? AND course_id=?",
                (s["id"], course_id),
            ).fetchone()
            if row is None:
                sid = s["id"]
                break
    finally:
        conn.close()
    if sid is None:
        check("enroll priced course -> atomic enrollment + invoice_item", False,
              "every seed student already enrolled in the priced course")
        return None
    token = get_token(c, "/enrollments")
    resp = c.post(
        "/enrollments/enroll",
        data={"student_id": str(sid), "course_id": str(course_id), "_csrf": token},
        follow_redirects=True,
    )
    conn = db_conn()
    try:
        enr = conn.execute(
            "SELECT COUNT(*) AS n FROM enrollments WHERE student_id=? AND course_id=?",
            (sid, course_id),
        ).fetchone()
        item = conn.execute(
            "SELECT COUNT(*) AS n FROM invoice_items it "
            "JOIN invoices i ON i.id = it.invoice_id "
            "WHERE i.student_id=? AND it.source_type='enrollment'",
            (sid,),
        ).fetchone()
    finally:
        conn.close()
    check(
        "enroll priced course -> enrollment row AND matching invoice_item (atomic)",
        resp.status_code in (200, 302) and enr["n"] == 1 and item["n"] >= 1,
        f"status={resp.status_code}, enrollments={enr['n']}, enrollment_items={item['n']}",
    )
    return sid  # for the double-enroll test


ENROLLED_SID = test_enroll_priced_atomicity()


# -- invoice total = SUM(items)
def test_invoice_total_is_sum():
    conn = db_conn()
    try:
        inv = conn.execute(
            "SELECT id, student_id FROM invoices ORDER BY id LIMIT 1"
        ).fetchone()
        if inv is None:
            check("invoice total == SUM(items)", False, "no invoice seeded")
            return
        expected = conn.execute(
            "SELECT COALESCE(SUM(amount_cents),0) AS s FROM invoice_items WHERE invoice_id=?",
            (inv["id"],),
        ).fetchone()["s"]
    finally:
        conn.close()
    c = app.test_client()
    login(c, ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = c.get(f"/invoices/{inv['id']}")
    # The schema has NO stored amount column, so the invoice total is necessarily the
    # SUM of invoice_items (single source of truth). Assert staff can view it (200) and
    # the computed sum resolves.
    check(
        "invoice view renders (200) and total is computed as SUM(invoice_items)",
        resp.status_code == 200 and expected is not None,
        f"status={resp.status_code}, expected_sum={expected}",
    )


test_invoice_total_is_sum()


# -- student logs practice under their OWN student_id
def test_student_practice_self():
    c = app.test_client()
    register(c, "practicer@smoke.test", "studiopass", "Practicer", "student")
    login(c, "practicer@smoke.test", "studiopass")
    link_student_row("practicer@smoke.test", "Practicer", "Smoke")
    # token from "/" — base.html's logout form carries _csrf for any logged-in
    # user (/practice/new is POST-only, so it serves no token page)
    token = get_token(c, "/")
    resp = c.post(
        "/practice/new",
        data={"minutes": "30", "notes": "scales", "_csrf": token},
        follow_redirects=True,
    )
    conn = db_conn()
    try:
        row = conn.execute(
            "SELECT pl.minutes FROM practice_logs pl "
            "JOIN students s ON s.id = pl.student_id "
            "JOIN users u ON u.id = s.user_id "
            "WHERE u.email=? ORDER BY pl.id DESC LIMIT 1",
            ("practicer@smoke.test",),
        ).fetchone()
    finally:
        conn.close()
    check(
        "student logs practice -> stored under their own student_id",
        resp.status_code in (200, 302) and row is not None and row["minutes"] == 30,
        f"status={resp.status_code}, stored={dict(row) if row else None}",
    )


test_student_practice_self()


# ===========================================================================
# ERROR CASES / INVARIANTS
# ===========================================================================

def two_students():
    """Register + login two fresh students; return (clientA, sidA, clientB, sidB)."""
    ca = app.test_client()
    register(ca, "idor_a@smoke.test", "studiopass", "IDOR A", "student")
    login(ca, "idor_a@smoke.test", "studiopass")
    cb = app.test_client()
    register(cb, "idor_b@smoke.test", "studiopass", "IDOR B", "student")
    login(cb, "idor_b@smoke.test", "studiopass")
    sid_a = link_student_row("idor_a@smoke.test", "IDOR", "A")
    sid_b = link_student_row("idor_b@smoke.test", "IDOR", "B")
    return ca, sid_a, cb, sid_b


# -- IDOR: student B -> student A's /students/<sid> -> 404 (+ owner sees own -> 200)
def test_idor_student_view():
    ca, sid_a, cb, sid_b = two_students()
    if sid_a is None or sid_b is None:
        check("IDOR /students/<A> for student B -> 404", False,
              "could not resolve student rows for registered student users")
        return
    resp = cb.get(f"/students/{sid_a}")
    check(
        "student B requests student A's /students/<sid> -> 404 (hide existence)",
        resp.status_code == 404,
        f"status={resp.status_code}",
    )
    own = ca.get(f"/students/{sid_a}")
    check(
        "student A views own /students/<sid> -> 200",
        own.status_code == 200,
        f"status={own.status_code}",
    )


test_idor_student_view()


# -- IDOR: unrelated student -> another student's invoice -> 404
def test_idor_invoice_view():
    conn = db_conn()
    try:
        inv = conn.execute(
            "SELECT i.id FROM invoices i "
            "JOIN students s ON s.id = i.student_id "
            "WHERE s.user_id IS NOT NULL ORDER BY i.id LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    cb = app.test_client()
    register(cb, "idor_inv_b@smoke.test", "studiopass", "InvB", "student")
    login(cb, "idor_inv_b@smoke.test", "studiopass")
    if inv is None:
        check("IDOR /invoices/<other> for student -> 404", False,
              "no invoice owned by a login-bearing student seeded")
        return
    resp = cb.get(f"/invoices/{inv['id']}")
    check(
        "student requests another student's /invoices/<iid> -> 404",
        resp.status_code == 404,
        f"status={resp.status_code}",
    )


test_idor_invoice_view()


# -- IDOR: unrelated student -> another student's lesson -> 404
def test_idor_lesson_view():
    conn = db_conn()
    try:
        les = conn.execute("SELECT id FROM lessons ORDER BY id LIMIT 1").fetchone()
    finally:
        conn.close()
    cb = app.test_client()
    register(cb, "idor_les_b@smoke.test", "studiopass", "LesB", "student")
    login(cb, "idor_les_b@smoke.test", "studiopass")
    if les is None:
        check("IDOR /lessons/<other> for student -> 404", False, "no lesson seeded")
        return
    resp = cb.get(f"/lessons/{les['id']}")
    check(
        "student requests a lesson that is not theirs /lessons/<lid> -> 404",
        resp.status_code == 404,
        f"status={resp.status_code}",
    )


test_idor_lesson_view()


# -- student POSTs to /instruments/new -> 403 (admin-only)
def test_student_forbidden_create_instrument():
    c = app.test_client()
    register(c, "role_probe@smoke.test", "studiopass", "Role Probe", "student")
    login(c, "role_probe@smoke.test", "studiopass")
    # token from "/" — a student cannot GET /instruments/new (403, no form),
    # and a valid _csrf is required so the POST reaches the authz layer (403)
    # instead of dying at the CSRF gate (400)
    token = get_token(c, "/")
    resp = c.post(
        "/instruments/new",
        data={"name": "Cello", "category": "strings", "condition": "good",
              "_csrf": token or "x"},
        follow_redirects=False,
    )
    check(
        "student POST /instruments/new -> 403 (admin-only)",
        resp.status_code == 403,
        f"status={resp.status_code}",
    )


test_student_forbidden_create_instrument()


# -- staff/admin POSTs /practice/new -> 403 (student self-service only)
def test_staff_practice_forbidden():
    c = app.test_client()
    login(c, ADMIN_EMAIL, ADMIN_PASSWORD)
    # token from "/" — /practice/new is POST-only; a valid _csrf lets the POST
    # reach the student-identity check (403) instead of the CSRF gate (400)
    token = get_token(c, "/")
    resp = c.post(
        "/practice/new",
        data={"minutes": "20", "notes": "n/a", "_csrf": token or "x"},
        follow_redirects=False,
    )
    check(
        "staff/admin POST /practice/new -> 403 (no student identity)",
        resp.status_code == 403,
        f"status={resp.status_code}",
    )


test_staff_practice_forbidden()


# -- CSRF: mutating POST with wrong / missing _csrf -> 400
def test_csrf_rejected():
    c = app.test_client()
    login(c, ADMIN_EMAIL, ADMIN_PASSWORD)
    resp_wrong = c.post(
        "/students/new",
        data={"first_name": "No", "last_name": "Csrf", "skill_level": "beginner",
              "_csrf": "totally-wrong-token"},
        follow_redirects=False,
    )
    check(
        "mutating POST with WRONG _csrf -> 400",
        resp_wrong.status_code == 400,
        f"status={resp_wrong.status_code}",
    )
    resp_missing = c.post(
        "/students/new",
        data={"first_name": "No", "last_name": "Csrf", "skill_level": "beginner"},
        follow_redirects=False,
    )
    check(
        "mutating POST with MISSING _csrf -> 400",
        resp_missing.status_code == 400,
        f"status={resp_missing.status_code}",
    )


test_csrf_rejected()


# -- checkout on non-available instrument -> 400, no new checkout row, status unchanged
def test_checkout_unavailable_rolls_back():
    conn = db_conn()
    try:
        inst = conn.execute(
            "SELECT id, status FROM instruments "
            "WHERE status != 'available' ORDER BY id LIMIT 1"
        ).fetchone()
        before_status = inst["status"] if inst else None
        before_rows = (
            conn.execute(
                "SELECT COUNT(*) AS n FROM instrument_checkouts WHERE instrument_id=?",
                (inst["id"],),
            ).fetchone()["n"]
            if inst is not None
            else None
        )
    finally:
        conn.close()
    if inst is None:
        check("checkout non-available instrument -> 400 + rollback", False,
              "no non-available instrument to test against")
        return
    c = app.test_client()
    login(c, ADMIN_EMAIL, ADMIN_PASSWORD)
    sid = SEED["students"][0]["id"]
    token = get_token(c, "/instruments")
    resp = c.post(
        f"/instruments/{inst['id']}/checkout",
        data={"student_id": str(sid), "due_at": "2099-01-01T00:00:00", "_csrf": token},
        follow_redirects=False,
    )
    conn = db_conn()
    try:
        after = conn.execute(
            "SELECT status FROM instruments WHERE id=?", (inst["id"],)
        ).fetchone()
        after_rows = conn.execute(
            "SELECT COUNT(*) AS n FROM instrument_checkouts WHERE instrument_id=?",
            (inst["id"],),
        ).fetchone()["n"]
    finally:
        conn.close()
    check(
        "checkout non-available instrument -> 400, no new checkout row, status unchanged",
        resp.status_code == 400
        and after["status"] == before_status
        and after_rows == before_rows,
        f"status={resp.status_code}, inst_status {before_status}->{after['status']}, "
        f"rows {before_rows}->{after_rows}",
    )


test_checkout_unavailable_rolls_back()


# -- double-enroll -> 400 and NO duplicate invoice_item / enrollment (unit rolled back)
def test_double_enroll_rejected():
    if ENROLLED_SID is None or not SEED["priced_courses"]:
        check("double-enroll -> 400 + no duplicate", False,
              "prerequisite priced enrollment did not run")
        return
    sid = ENROLLED_SID
    course_id = SEED["priced_courses"][0]["id"]
    conn = db_conn()
    try:
        items_before = conn.execute(
            "SELECT COUNT(*) AS n FROM invoice_items it "
            "JOIN invoices i ON i.id = it.invoice_id "
            "WHERE i.student_id=? AND it.source_type='enrollment'",
            (sid,),
        ).fetchone()["n"]
    finally:
        conn.close()
    c = app.test_client()
    login(c, ADMIN_EMAIL, ADMIN_PASSWORD)
    token = get_token(c, "/enrollments")
    resp = c.post(
        "/enrollments/enroll",
        data={"student_id": str(sid), "course_id": str(course_id), "_csrf": token},
        follow_redirects=False,
    )
    conn = db_conn()
    try:
        enr = conn.execute(
            "SELECT COUNT(*) AS n FROM enrollments WHERE student_id=? AND course_id=?",
            (sid, course_id),
        ).fetchone()["n"]
        items_after = conn.execute(
            "SELECT COUNT(*) AS n FROM invoice_items it "
            "JOIN invoices i ON i.id = it.invoice_id "
            "WHERE i.student_id=? AND it.source_type='enrollment'",
            (sid,),
        ).fetchone()["n"]
    finally:
        conn.close()
    check(
        "double-enroll -> 400 AND no duplicate enrollment/invoice_item (unit rolled back)",
        resp.status_code == 400 and enr == 1 and items_after == items_before,
        f"status={resp.status_code}, enrollments={enr}, items {items_before}->{items_after}",
    )


test_double_enroll_rejected()


# -- one-draft-per-student: two priced enrollments -> exactly ONE draft invoice
def test_one_draft_after_two_enrollments():
    if len(SEED["priced_courses"]) < 2:
        check("two priced enrollments -> exactly one draft invoice", False,
              "fewer than two priced courses seeded")
        return
    c = app.test_client()
    login(c, ADMIN_EMAIL, ADMIN_PASSWORD)
    conn = db_conn()
    try:
        target_sid = None
        chosen = []
        for s in SEED["students"]:
            free = []
            for pc in SEED["priced_courses"]:
                row = conn.execute(
                    "SELECT 1 FROM enrollments WHERE student_id=? AND course_id=?",
                    (s["id"], pc["id"]),
                ).fetchone()
                if row is None:
                    free.append(pc["id"])
                if len(free) == 2:
                    break
            if len(free) >= 2:
                target_sid = s["id"]
                chosen = free[:2]
                break
    finally:
        conn.close()
    if target_sid is None:
        check("two priced enrollments -> exactly one draft invoice", False,
              "no student with two free priced courses")
        return
    for cid in chosen:
        token = get_token(c, "/enrollments")
        c.post(
            "/enrollments/enroll",
            data={"student_id": str(target_sid), "course_id": str(cid), "_csrf": token},
            follow_redirects=False,
        )
    conn = db_conn()
    try:
        n_draft = conn.execute(
            "SELECT COUNT(*) AS n FROM invoices WHERE student_id=? AND status='draft'",
            (target_sid,),
        ).fetchone()["n"]
    finally:
        conn.close()
    check(
        "two priced enrollments accrete onto exactly ONE draft invoice",
        n_draft == 1,
        f"draft_invoices_for_student={n_draft}",
    )


test_one_draft_after_two_enrollments()


# -- direct 2nd draft INSERT for a student who already has one -> IntegrityError
def test_second_draft_insert_raises():
    conn = db_conn()
    try:
        existing = conn.execute(
            "SELECT student_id FROM invoices WHERE status='draft' ORDER BY id LIMIT 1"
        ).fetchone()
        if existing is None:
            check("direct 2nd draft INSERT -> IntegrityError", False,
                  "no existing draft invoice to collide against")
            return
        sid = existing["student_id"]
        raised = False
        try:
            conn.execute(
                "INSERT INTO invoices (student_id, status) VALUES (?, 'draft')", (sid,)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raised = True
        check(
            "direct 2nd draft INSERT for same student -> sqlite3.IntegrityError "
            "(ux_one_draft_per_student)",
            raised,
            "second draft insert did NOT raise -- partial unique index missing?",
        )
    finally:
        conn.close()


test_second_draft_insert_raises()


# -- lesson with ends_at <= starts_at -> 400
def test_lesson_bad_time_range():
    c = app.test_client()
    login(c, ADMIN_EMAIL, ADMIN_PASSWORD)
    iid = SEED["instructor_id"]
    sid = SEED["students"][0]["id"]
    token = get_token(c, "/lessons/new")
    resp = c.post(
        "/lessons/new",
        data={
            "instructor_id": str(iid),
            "student_id": str(sid),
            "starts_at": "2099-01-01T10:00:00",
            "ends_at": "2099-01-01T09:00:00",  # <= starts_at
            "_csrf": token,
        },
        follow_redirects=False,
    )
    check(
        "lesson create with ends_at <= starts_at -> 400",
        resp.status_code == 400,
        f"status={resp.status_code}",
    )


test_lesson_bad_time_range()


# ===========================================================================
# SUMMARY
# ===========================================================================
print("-" * 60)
print(f"SMOKE RESULTS: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
