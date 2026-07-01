import sqlite3
import os


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
            photo_path TEXT,
            face_encoding BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS visit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
            site_name TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('verified', 'unknown')),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def add_employee(db_path, full_name, role, department, contact, photo_path, face_encoding):
    conn = get_connection(db_path)
    cursor = conn.execute(
        "INSERT INTO employees (full_name, role, department, contact, photo_path, face_encoding) VALUES (?, ?, ?, ?, ?, ?)",
        (full_name, role, department, contact, photo_path, face_encoding),
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


def add_log(db_path, employee_id, site_name, status):
    conn = get_connection(db_path)
    cursor = conn.execute(
        "INSERT INTO visit_logs (employee_id, site_name, status) VALUES (?, ?, ?)",
        (employee_id, site_name, status),
    )
    conn.commit()
    log_id = cursor.lastrowid
    conn.close()
    return log_id


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


def get_filtered_logs(db_path, date=None, site=None):
    query = """
        SELECT vl.*, e.full_name, e.role, e.department
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
