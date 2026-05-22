CREATE TABLE IF NOT EXISTS membership_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    duration_months INTEGER NOT NULL,
    price_cents INTEGER NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL DEFAULT '',
    emergency_contact TEXT NOT NULL DEFAULT '',
    membership_type_id INTEGER REFERENCES membership_types(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'frozen', 'cancelled')),
    join_date TEXT NOT NULL DEFAULT (date('now')),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_members_membership_type_id ON members(membership_type_id);
CREATE INDEX IF NOT EXISTS idx_members_status ON members(status);

CREATE TABLE IF NOT EXISTS trainers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL DEFAULT '',
    specializations TEXT NOT NULL DEFAULT '',
    bio TEXT NOT NULL DEFAULT '',
    hire_date TEXT NOT NULL DEFAULT (date('now')),
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS class_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    duration_minutes INTEGER NOT NULL DEFAULT 60,
    default_capacity INTEGER NOT NULL DEFAULT 20,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS class_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_type_id INTEGER NOT NULL REFERENCES class_types(id) ON DELETE RESTRICT,
    trainer_id INTEGER REFERENCES trainers(id) ON DELETE SET NULL,
    session_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    room TEXT NOT NULL DEFAULT '',
    capacity INTEGER NOT NULL DEFAULT 20,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_class_schedules_class_type_id ON class_schedules(class_type_id);
CREATE INDEX IF NOT EXISTS idx_class_schedules_trainer_id ON class_schedules(trainer_id);
CREATE INDEX IF NOT EXISTS idx_class_schedules_session_date ON class_schedules(session_date);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
    class_schedule_id INTEGER REFERENCES class_schedules(id) ON DELETE RESTRICT,
    check_in_time TEXT NOT NULL DEFAULT (datetime('now')),
    check_out_time TEXT,
    attendance_type TEXT NOT NULL DEFAULT 'class' CHECK(attendance_type IN ('class', 'open_gym')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_attendance_member_id ON attendance(member_id);
CREATE INDEX IF NOT EXISTS idx_attendance_class_schedule_id ON attendance(class_schedule_id);

CREATE TABLE IF NOT EXISTS equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    serial_number TEXT NOT NULL DEFAULT '',
    purchase_date TEXT,
    purchase_price_cents INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available', 'in_use', 'maintenance', 'retired')),
    location TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS maintenance_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id) ON DELETE RESTRICT,
    description TEXT NOT NULL,
    maintenance_date TEXT NOT NULL DEFAULT (date('now')),
    cost_cents INTEGER NOT NULL DEFAULT 0,
    performed_by TEXT NOT NULL DEFAULT '',
    next_due_date TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_maintenance_log_equipment_id ON maintenance_log(equipment_id);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
    amount_cents INTEGER NOT NULL,
    description TEXT NOT NULL,
    billing_date TEXT NOT NULL DEFAULT (date('now')),
    due_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'paid', 'overdue', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_invoices_member_id ON invoices(member_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE RESTRICT,
    amount_cents INTEGER NOT NULL,
    payment_date TEXT NOT NULL DEFAULT (date('now')),
    payment_method TEXT NOT NULL DEFAULT 'cash' CHECK(payment_method IN ('cash', 'card', 'bank_transfer', 'other')),
    reference_number TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_payments_invoice_id ON payments(invoice_id);

CREATE TABLE IF NOT EXISTS fitness_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
    trainer_id INTEGER REFERENCES trainers(id) ON DELETE SET NULL,
    assessment_date TEXT NOT NULL DEFAULT (date('now')),
    weight_kg REAL,
    height_cm REAL,
    body_fat_pct REAL,
    bmi REAL,
    resting_heart_rate INTEGER,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_fitness_assessments_member_id ON fitness_assessments(member_id);
CREATE INDEX IF NOT EXISTS idx_fitness_assessments_trainer_id ON fitness_assessments(trainer_id);
