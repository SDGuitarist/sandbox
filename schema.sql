-- schema.sql (database agent owns this file)
-- Seeding order: departments, budget_categories, users, projects, project_members, then domain tables

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;

-- ============================================================
-- CORE TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    phase TEXT NOT NULL DEFAULT 'development'
        CHECK (phase IN ('development','pre_production','production','post_production','distribution')),
    total_budget_cents INTEGER NOT NULL DEFAULT 0 CHECK (total_budget_cents >= 0),
    start_date TEXT,
    end_date TEXT,
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS project_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('producer','ad','department_head','crew_member')),
    UNIQUE(project_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_project_members_project ON project_members(project_id);
CREATE INDEX IF NOT EXISTS idx_project_members_user ON project_members(user_id);

-- ============================================================
-- DEPARTMENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    head_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE(project_id, name)
);
CREATE INDEX IF NOT EXISTS idx_departments_project ON departments(project_id);

-- ============================================================
-- CREW & CAST
-- ============================================================

CREATE TABLE IF NOT EXISTS crew_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    role_title TEXT NOT NULL,
    department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    phone TEXT,
    email TEXT,
    daily_rate_cents INTEGER DEFAULT 0 CHECK (daily_rate_cents >= 0),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_crew_project ON crew_members(project_id);
CREATE INDEX IF NOT EXISTS idx_crew_department ON crew_members(department_id);
CREATE INDEX IF NOT EXISTS idx_crew_user ON crew_members(user_id);

CREATE TABLE IF NOT EXISTS cast_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    character_name TEXT NOT NULL,
    cast_id_number INTEGER NOT NULL CHECK (cast_id_number BETWEEN 1 AND 99),
    agent_name TEXT,
    agent_phone TEXT,
    agent_email TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(project_id, cast_id_number)
);
CREATE INDEX IF NOT EXISTS idx_cast_project ON cast_members(project_id);

-- ============================================================
-- SCENES
-- ============================================================

CREATE TABLE IF NOT EXISTS scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scene_number TEXT NOT NULL,
    description TEXT,
    int_ext TEXT NOT NULL CHECK (int_ext IN ('INT','EXT','INT/EXT')),
    day_night TEXT NOT NULL CHECK (day_night IN ('DAY','NIGHT','DAWN','DUSK')),
    page_count_eighths INTEGER NOT NULL DEFAULT 8 CHECK (page_count_eighths > 0),
    location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'not_started'
        CHECK (status IN ('not_started','in_prep','ready','shooting','wrapped','on_hold')),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(project_id, scene_number)
);
CREATE INDEX IF NOT EXISTS idx_scenes_project ON scenes(project_id);
CREATE INDEX IF NOT EXISTS idx_scenes_location ON scenes(location_id);

CREATE TABLE IF NOT EXISTS scene_cast (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    cast_member_id INTEGER NOT NULL REFERENCES cast_members(id) ON DELETE CASCADE,
    UNIQUE(scene_id, cast_member_id)
);
CREATE INDEX IF NOT EXISTS idx_scene_cast_scene ON scene_cast(scene_id);
CREATE INDEX IF NOT EXISTS idx_scene_cast_cast ON scene_cast(cast_member_id);

CREATE TABLE IF NOT EXISTS scene_elements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    element_type TEXT NOT NULL CHECK (element_type IN ('prop','wardrobe','sfx','vehicle','animal','special_equipment')),
    description TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scene_elements_scene ON scene_elements(scene_id);

-- ============================================================
-- LOCATIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    address TEXT,
    contact_name TEXT,
    contact_phone TEXT,
    permit_status TEXT DEFAULT 'pending' CHECK (permit_status IN ('pending','approved','denied')),
    nearest_hospital TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_locations_project ON locations(project_id);

-- ============================================================
-- SCHEDULE
-- ============================================================

CREATE TABLE IF NOT EXISTS schedule_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    shoot_date TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(project_id, scene_id)
);
CREATE INDEX IF NOT EXISTS idx_schedule_project_date ON schedule_entries(project_id, shoot_date);
CREATE INDEX IF NOT EXISTS idx_schedule_scene ON schedule_entries(scene_id);

-- ============================================================
-- CALL SHEETS
-- ============================================================

CREATE TABLE IF NOT EXISTS call_sheets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    sheet_number INTEGER NOT NULL,
    shoot_date TEXT NOT NULL,
    crew_call_time TEXT DEFAULT '07:00',
    weather_note TEXT,
    general_notes TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(project_id, shoot_date)
);
CREATE INDEX IF NOT EXISTS idx_callsheets_project ON call_sheets(project_id);

CREATE TABLE IF NOT EXISTS call_sheet_scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_sheet_id INTEGER NOT NULL REFERENCES call_sheets(id) ON DELETE CASCADE,
    scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_cs_scenes_sheet ON call_sheet_scenes(call_sheet_id);

CREATE TABLE IF NOT EXISTS call_sheet_cast (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_sheet_id INTEGER NOT NULL REFERENCES call_sheets(id) ON DELETE CASCADE,
    cast_member_id INTEGER NOT NULL REFERENCES cast_members(id) ON DELETE CASCADE,
    pickup_time TEXT,
    makeup_time TEXT,
    on_set_time TEXT,
    status TEXT NOT NULL DEFAULT 'W' CHECK (status IN ('W','SW','WF','SWF','H')),
    remarks TEXT
);
CREATE INDEX IF NOT EXISTS idx_cs_cast_sheet ON call_sheet_cast(call_sheet_id);

-- ============================================================
-- BUDGET & EXPENSES
-- ============================================================

CREATE TABLE IF NOT EXISTS budget_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    account_number TEXT NOT NULL,
    name TEXT NOT NULL,
    parent_group TEXT NOT NULL CHECK (parent_group IN ('ATL','BTL_PRODUCTION','BTL_POST','OTHER')),
    UNIQUE(project_id, account_number)
);
CREATE INDEX IF NOT EXISTS idx_budget_cat_project ON budget_categories(project_id);

CREATE TABLE IF NOT EXISTS budget_line_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES budget_categories(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    estimated_cents INTEGER NOT NULL DEFAULT 0 CHECK (estimated_cents >= 0),
    actual_cents INTEGER NOT NULL DEFAULT 0 CHECK (actual_cents >= 0),
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_line_items_category ON budget_line_items(category_id);
CREATE INDEX IF NOT EXISTS idx_line_items_project ON budget_line_items(project_id);

CREATE TABLE IF NOT EXISTS department_budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    allocated_cents INTEGER NOT NULL DEFAULT 0 CHECK (allocated_cents >= 0),
    spent_cents INTEGER NOT NULL DEFAULT 0 CHECK (spent_cents >= 0),
    CHECK (spent_cents <= allocated_cents),
    UNIQUE(project_id, department_id)
);
CREATE INDEX IF NOT EXISTS idx_dept_budgets_project ON department_budgets(project_id);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    category_id INTEGER REFERENCES budget_categories(id) ON DELETE SET NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    vendor TEXT NOT NULL,
    description TEXT,
    expense_date TEXT NOT NULL,
    approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_expenses_project ON expenses(project_id);
CREATE INDEX IF NOT EXISTS idx_expenses_department ON expenses(department_id);

-- ============================================================
-- FTS5 SEARCH (external content)
-- ============================================================

CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    entity_type UNINDEXED, entity_id UNINDEXED, title, body,
    content='', contentless_delete=1
);

-- FTS5 sync triggers use BEFORE (not AFTER) to prevent silent index corruption
-- Triggers are created by the search agent on: scenes, cast_members, crew_members, locations
