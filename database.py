import sqlite3
import os

from werkzeug.security import generate_password_hash


def init_db(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            role TEXT,
            department TEXT,
            contact TEXT,
            centre TEXT,
            photo_path TEXT,
            face_encoding BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS visit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
            site_name TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('verified', 'unknown')),
            purpose TEXT,
            notes TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'site_staff')),
            assigned_centre TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS centres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS gadgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visit_id INTEGER NOT NULL REFERENCES visit_logs(id) ON DELETE CASCADE,
            gadget_type TEXT NOT NULL CHECK(gadget_type IN ('Laptop', 'Phone', 'Tablet', 'Hard Drive', 'Camera', 'Other')),
            gadget_name TEXT NOT NULL,
            serial_number TEXT,
            checked_in_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            checked_out_time TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()
    migrate_db(db_path)
    init_users(db_path)
    init_centres(db_path)


def migrate_db(db_path):
    conn = sqlite3.connect(db_path)
    for col in ["centre"]:
        try:
            conn.execute(f"ALTER TABLE employees ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
    for col in ["purpose", "notes"]:
        try:
            conn.execute(f"ALTER TABLE visit_logs ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
    for col in ["unrecognized_photo_path"]:
        try:
            conn.execute(f"ALTER TABLE visit_logs ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
    for col in ["active"]:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
    conn.execute("UPDATE users SET active = 1 WHERE active IS NULL")
    for col in ["checked_out_time"]:
        try:
            conn.execute(f"ALTER TABLE gadgets ADD COLUMN {col} TIMESTAMP")
        except sqlite3.OperationalError:
            pass
    conn.close()


def init_users(db_path):
    conn = get_connection(db_path)
    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing == 0:
        default_users = [
            ("admin", generate_password_hash("admin123"), "admin", None),
            ("staff1", generate_password_hash("staff123"), "site_staff", "Civic Centre"),
            ("staff2", generate_password_hash("staff123"), "site_staff", "Sakubva"),
        ]
        conn.executemany(
            "INSERT INTO users (username, password_hash, role, assigned_centre) VALUES (?, ?, ?, ?)",
            default_users,
        )
        conn.commit()
    conn.close()


def init_centres(db_path):
    conn = get_connection(db_path)
    existing = conn.execute("SELECT COUNT(*) FROM centres").fetchone()[0]
    if existing == 0:
        centres = ["Civic Centre", "Stores", "Housing", "Chikanga", "Hobhouse"]
        for c in centres:
            conn.execute("INSERT INTO centres (name) VALUES (?)", (c,))
        conn.commit()
    conn.close()


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def add_employee(db_path, full_name, role, department, contact, centre, photo_path, face_encoding):
    conn = get_connection(db_path)
    cursor = conn.execute(
        "INSERT INTO employees (full_name, role, department, contact, centre, photo_path, face_encoding) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (full_name, role, department, contact, centre, photo_path, face_encoding),
    )
    conn.commit()
    emp_id = cursor.lastrowid
    conn.close()
    return emp_id


def get_all_employees(db_path):
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM employees ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_log(db_path, employee_id, site_name, status, purpose=None, notes=None, unrecognized_photo_path=None):
    conn = get_connection(db_path)
    cursor = conn.execute(
        "INSERT INTO visit_logs (employee_id, site_name, status, purpose, notes, unrecognized_photo_path) VALUES (?, ?, ?, ?, ?, ?)",
        (employee_id, site_name, status, purpose, notes, unrecognized_photo_path),
    )
    conn.commit()
    log_id = cursor.lastrowid
    conn.close()
    return log_id


def delete_log(db_path, log_id):
    conn = get_connection(db_path)
    conn.execute("DELETE FROM visit_logs WHERE id = ?", (log_id,))
    conn.commit()
    conn.close()


def update_log_employee(db_path, log_id, employee_id, status='verified'):
    conn = get_connection(db_path)
    conn.execute("UPDATE visit_logs SET employee_id = ?, status = ? WHERE id = ?", (employee_id, status, log_id))
    conn.commit()
    conn.close()


def get_log_by_id(db_path, log_id):
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT vl.*, e.full_name, e.role, e.department, e.centre AS emp_centre, e.photo_path AS emp_photo_path FROM visit_logs vl LEFT JOIN employees e ON vl.employee_id = e.id WHERE vl.id = ?",
        (log_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_logs(db_path):
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT vl.*, e.full_name, e.role, e.department
        FROM visit_logs vl
        LEFT JOIN employees e ON vl.employee_id = e.id
        ORDER BY vl.timestamp DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_filtered_logs(db_path, date=None, site=None, name=None, status=None, centre=None):
    query = """
        SELECT vl.*, e.full_name, e.role, e.department, e.centre
        FROM visit_logs vl
        LEFT JOIN employees e ON vl.employee_id = e.id
        WHERE 1=1
    """
    params = []
    if date:
        query += " AND DATE(vl.timestamp) = ?"
        params.append(date)
    if site:
        query += " AND vl.site_name = ?"
        params.append(site)
    if name:
        query += " AND e.full_name LIKE ?"
        params.append(f"%{name}%")
    if status:
        query += " AND vl.status = ?"
        params.append(status)
    if centre:
        query += " AND e.centre = ?"
        params.append(centre)
    query += " ORDER BY vl.timestamp DESC"
    conn = get_connection(db_path)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_distinct_sites(db_path):
    conn = get_connection(db_path)
    rows = conn.execute("SELECT DISTINCT site_name FROM visit_logs ORDER BY site_name").fetchall()
    conn.close()
    return [r["site_name"] for r in rows]


def get_user_by_username(db_path, username):
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_user(db_path, username, password, role, assigned_centre=None):
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO users (username, password_hash, role, assigned_centre) VALUES (?, ?, ?, ?)",
        (username, generate_password_hash(password), role, assigned_centre),
    )
    conn.commit()
    conn.close()


def get_all_staff(db_path):
    conn = get_connection(db_path)
    rows = conn.execute("SELECT id, username, assigned_centre, created_at FROM users WHERE role = 'site_staff' ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_centres(db_path):
    conn = get_connection(db_path)
    rows = conn.execute("SELECT id, name FROM centres ORDER BY name").fetchall()
    conn.close()
    return [r["name"] for r in rows]


def get_distinct_departments(db_path):
    conn = get_connection(db_path)
    rows = conn.execute("SELECT DISTINCT department FROM employees WHERE department IS NOT NULL AND department != '' ORDER BY department").fetchall()
    conn.close()
    return [r["department"] for r in rows if r["department"]]


def get_filtered_employees(db_path, name=None, department=None, role=None, centre=None):
    query = "SELECT * FROM employees WHERE 1=1"
    params = []
    if name:
        query += " AND full_name LIKE ?"
        params.append(f"%{name}%")
    if department:
        query += " AND department = ?"
        params.append(department)
    if role:
        query += " AND role LIKE ?"
        params.append(f"%{role}%")
    if centre:
        query += " AND centre = ?"
        params.append(centre)
    query += " ORDER BY created_at DESC"
    conn = get_connection(db_path)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_employee_by_id(db_path, emp_id):
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM employees WHERE id = ?", (emp_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_employee(db_path, emp_id, full_name, role, department, contact, centre):
    conn = get_connection(db_path)
    conn.execute(
        "UPDATE employees SET full_name = ?, role = ?, department = ?, contact = ?, centre = ? WHERE id = ?",
        (full_name, role, department, contact, centre, emp_id),
    )
    conn.commit()
    conn.close()


def delete_employee(db_path, emp_id):
    conn = get_connection(db_path)
    conn.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
    conn.commit()
    conn.close()


def get_dashboard_stats(db_path):
    conn = get_connection(db_path)
    emp_count = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    total_logs = conn.execute("SELECT COUNT(*) FROM visit_logs").fetchone()[0]
    today_visits = conn.execute("SELECT COUNT(*) FROM visit_logs WHERE DATE(timestamp) = DATE('now')").fetchone()[0]
    unknown_count = conn.execute("SELECT COUNT(*) FROM visit_logs WHERE status = 'unknown'").fetchone()[0]
    recent_unknown = conn.execute("""
        SELECT vl.*, e.full_name
        FROM visit_logs vl
        LEFT JOIN employees e ON vl.employee_id = e.id
        WHERE vl.status = 'unknown'
        ORDER BY vl.timestamp DESC LIMIT 10
    """).fetchall()
    conn.close()
    return {
        "employee_count": emp_count,
        "total_logs": total_logs,
        "today_visits": today_visits,
        "unknown_count": unknown_count,
        "recent_unknown": [dict(r) for r in recent_unknown],
    }


def get_unrecognized_logs(db_path):
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT vl.*, e.full_name, e.role, e.department, e.centre
        FROM visit_logs vl
        LEFT JOIN employees e ON vl.employee_id = e.id
        WHERE vl.status = 'unknown'
        ORDER BY vl.timestamp DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_today_centre_visits(db_path, centre):
    conn = get_connection(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM visit_logs WHERE site_name = ? AND DATE(timestamp) = DATE('now')",
        (centre,),
    ).fetchone()[0]
    conn.close()
    return count


def get_staff_recent_logs(db_path, centre, limit=20):
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT vl.*, e.full_name, e.role
        FROM visit_logs vl
        LEFT JOIN employees e ON vl.employee_id = e.id
        WHERE vl.site_name = ?
        ORDER BY vl.timestamp DESC LIMIT ?
    """, (centre, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_orphaned_logs(db_path):
    conn = get_connection(db_path)
    result = conn.execute("""
        DELETE FROM visit_logs
        WHERE employee_id IS NOT NULL
        AND employee_id NOT IN (SELECT id FROM employees)
    """)
    deleted = result.rowcount
    conn.commit()
    conn.close()
    return deleted


def add_gadget(db_path, visit_id, gadget_type, gadget_name, serial_number=None):
    conn = get_connection(db_path)
    cursor = conn.execute(
        "INSERT INTO gadgets (visit_id, gadget_type, gadget_name, serial_number, checked_in_time) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (visit_id, gadget_type, gadget_name, serial_number),
    )
    conn.commit()
    gadget_id = cursor.lastrowid
    conn.close()
    return gadget_id


def get_unchecked_gadgets_for_employee(db_path, employee_id):
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT g.*
        FROM gadgets g
        JOIN visit_logs vl ON g.visit_id = vl.id
        WHERE vl.employee_id = ? AND g.checked_out_time IS NULL
        ORDER BY g.checked_in_time
    """, (employee_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_gadgets_for_visit(db_path, visit_id):
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM gadgets WHERE visit_id = ? ORDER BY checked_in_time",
        (visit_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def checkout_gadget(db_path, gadget_id):
    conn = get_connection(db_path)
    conn.execute(
        "UPDATE gadgets SET checked_out_time = CURRENT_TIMESTAMP WHERE id = ? AND checked_out_time IS NULL",
        (gadget_id,),
    )
    conn.commit()
    conn.close()


def get_all_checked_in_gadgets(db_path):
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT g.*, vl.site_name, vl.employee_id, e.full_name
        FROM gadgets g
        JOIN visit_logs vl ON g.visit_id = vl.id
        LEFT JOIN employees e ON vl.employee_id = e.id
        WHERE g.checked_out_time IS NULL
        ORDER BY g.checked_in_time DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
