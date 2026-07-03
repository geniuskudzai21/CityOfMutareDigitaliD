import base64
import functools
import os
import pickle
import tempfile
import uuid

from datetime import datetime

from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from werkzeug.security import check_password_hash

from database import (
    add_employee,
    add_gadget,
    add_log,
    add_user,
    checkout_gadget,
    get_all_checked_in_gadgets,
    get_gadgets_for_visit,
    get_unchecked_gadgets_for_employee,
    get_all_centres,
    get_distinct_departments,
    get_all_employees,
    get_all_staff,
    get_dashboard_stats,
    get_distinct_sites,
    get_filtered_employees,
    get_filtered_logs,
    get_employee_by_id,
    update_employee,
    delete_employee,
    get_staff_recent_logs,
    get_today_centre_visits,
    get_unrecognized_logs,
    delete_log,
    update_log_employee,
    get_log_by_id,
    get_all_logs,
    get_user_by_username,
    init_db,
    delete_orphaned_logs,
)
from face_utils import encode_face, match_face

app = Flask(__name__)
app.secret_key = os.urandom(32).hex()

db_path = os.path.join(app.instance_path, "database.db")
PHOTO_DIR = os.path.join(app.static_folder, "enrolled_photos")
UNRECOGNIZED_PHOTO_DIR = os.path.join(app.static_folder, "unrecognized_photos")

with app.app_context():
    init_db(db_path)
    delete_orphaned_logs(db_path)


def login_required(route_function):
    @functools.wraps(route_function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return route_function(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(route_function):
        @functools.wraps(route_function)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if session.get("role") not in roles:
                return redirect(url_for("login"))
            return route_function(*args, **kwargs)
        return wrapper
    return decorator


@app.context_processor
def inject_user():
    return {
        "logged_in": "user_id" in session,
        "username": session.get("username", ""),
        "role": session.get("role", ""),
        "assigned_centre": session.get("assigned_centre", ""),
        "now": datetime.now(),
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = get_user_by_username(db_path, username)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["assigned_centre"] = user["assigned_centre"]
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("staff_dashboard"))
        return render_template("login.html", error="Invalid username or password.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    if "user_id" in session:
        if session["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("staff_dashboard"))
    return render_template("welcome.html")


@app.route("/admin/dashboard")
@login_required
@role_required("admin")
def admin_dashboard():
    stats = get_dashboard_stats(db_path)
    return render_template("admin_dashboard.html", stats=stats)


@app.route("/staff/dashboard")
@login_required
@role_required("site_staff")
def staff_dashboard():
    centre = session.get("assigned_centre", "")
    recent_logs = get_staff_recent_logs(db_path, centre, limit=5)
    today_count = get_today_centre_visits(db_path, centre)
    return render_template("staff_dashboard.html", centre=centre, logs=recent_logs, today_count=today_count)


@app.route("/staff/logs")
@login_required
@role_required("site_staff")
def staff_logs():
    centre = session.get("assigned_centre", "")
    all_logs = get_staff_recent_logs(db_path, centre)
    for log in all_logs:
        log["gadgets"] = get_gadgets_for_visit(db_path, log["id"])
    return render_template("staff/logs.html", centre=centre, logs=all_logs)


@app.route("/admin/enroll", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_enroll():
    if request.method == "POST":
        return handle_enroll(request.get_json())
    centres = get_all_centres(db_path)
    departments = get_distinct_departments(db_path)
    return render_template("admin/enroll.html", centres=centres, departments=departments)


def handle_enroll(data):
    header, encoded = data["photo"].split(",", 1)
    image_data = base64.b64decode(encoded)

    filename = f"{uuid.uuid4().hex}.jpg"
    photo_path = os.path.join(PHOTO_DIR, filename)
    os.makedirs(PHOTO_DIR, exist_ok=True)
    with open(photo_path, "wb") as f:
        f.write(image_data)

    encoding = encode_face(photo_path)
    if encoding is None:
        os.remove(photo_path)
        return jsonify({"success": False, "error": "No face detected in the photo."})

    add_employee(
        db_path,
        data["full_name"],
        data.get("role"),
        data.get("department"),
        data.get("contact"),
        data.get("centre"),
        photo_path,
        pickle.dumps(encoding),
    )
    return jsonify({"success": True})


@app.route("/verify", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_verify():
    if request.method == "GET":
        centres = get_all_centres(db_path)
        return render_template("verify.html", centres=centres)

    data = request.get_json()
    header, encoded = data["photo"].split(",", 1)
    image_data = base64.b64decode(encoded)
    site_name = data.get("site_name", "")

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(image_data)
        tmp_path = tmp.name

    unknown_encoding = encode_face(tmp_path)
    os.remove(tmp_path)

    if unknown_encoding is None:
        filename = f"{uuid.uuid4().hex}.jpg"
        photo_path = os.path.join(UNRECOGNIZED_PHOTO_DIR, filename)
        os.makedirs(UNRECOGNIZED_PHOTO_DIR, exist_ok=True)
        with open(photo_path, "wb") as f:
            f.write(image_data)
        add_log(db_path, None, site_name, "unknown", unrecognized_photo_path=photo_path)
        return jsonify({"verified": False})

    employees = get_all_employees(db_path)
    known = []
    for emp in employees:
        if emp["face_encoding"]:
            known.append((emp, pickle.loads(emp["face_encoding"])))

    if not known:
        filename = f"{uuid.uuid4().hex}.jpg"
        photo_path = os.path.join(UNRECOGNIZED_PHOTO_DIR, filename)
        os.makedirs(UNRECOGNIZED_PHOTO_DIR, exist_ok=True)
        with open(photo_path, "wb") as f:
            f.write(image_data)
        add_log(db_path, None, site_name, "unknown", unrecognized_photo_path=photo_path)
        return jsonify({"verified": False})

    emp_list, enc_list = zip(*known)
    idx = match_face(unknown_encoding, list(enc_list))
    if idx is not None:
        emp = emp_list[idx]
        return jsonify({
            "verified": True,
            "employee_id": emp["id"],
            "full_name": emp["full_name"],
            "role": emp["role"],
            "department": emp["department"],
            "photo_url": f"/{emp['photo_path'].replace(os.sep, '/')}",
        })

    filename = f"{uuid.uuid4().hex}.jpg"
    photo_path = os.path.join(UNRECOGNIZED_PHOTO_DIR, filename)
    os.makedirs(UNRECOGNIZED_PHOTO_DIR, exist_ok=True)
    with open(photo_path, "wb") as f:
        f.write(image_data)

    add_log(db_path, None, site_name, "unknown", unrecognized_photo_path=photo_path)
    return jsonify({"verified": False})


@app.route("/admin/confirm-visit", methods=["POST"])
@login_required
@role_required("admin")
def admin_confirm_visit():
    data = request.get_json()
    log_id = add_log(
        db_path,
        data["employee_id"],
        data.get("site_name", ""),
        "verified",
        data.get("purpose"),
        data.get("notes"),
    )
    for gadget in data.get("gadgets", []):
        add_gadget(
            db_path,
            log_id,
            gadget["gadget_type"],
            gadget["gadget_name"],
            gadget.get("serial_number"),
        )
    return jsonify({"success": True})

    employees = get_all_employees(db_path)
    known = []
    for emp in employees:
        if emp["face_encoding"]:
            known.append(pickle.loads(emp["face_encoding"]))

    if not known:
        add_log(db_path, None, site_name, "unknown", purpose, notes)
        return jsonify({"verified": False})

    idx = match_face(unknown_encoding, known)
    if idx is not None:
        emp = emp_list[idx]
        unchecked = get_unchecked_gadgets_for_employee(db_path, emp["id"])
        return jsonify({
            "verified": True,
            "employee_id": emp["id"],
            "full_name": emp["full_name"],
            "role": emp["role"],
            "department": emp["department"],
            "photo_url": f"/{emp['photo_path'].replace(os.sep, '/')}",
            "gadgets": unchecked,
        })

    filename = f"{uuid.uuid4().hex}.jpg"
    photo_path = os.path.join(UNRECOGNIZED_PHOTO_DIR, filename)
    os.makedirs(UNRECOGNIZED_PHOTO_DIR, exist_ok=True)
    with open(photo_path, "wb") as f:
        f.write(image_data)

    add_log(db_path, None, site_name, "unknown", purpose, notes, unrecognized_photo_path=photo_path)
    return jsonify({"verified": False})


@app.route("/staff/verify", methods=["GET", "POST"])
@login_required
@role_required("site_staff")
def staff_verify():
    if request.method == "GET":
        return render_template("staff/verify.html")
    data = request.get_json()
    header, encoded = data["photo"].split(",", 1)
    image_data = base64.b64decode(encoded)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(image_data)
        tmp_path = tmp.name
    unknown_encoding = encode_face(tmp_path)
    os.remove(tmp_path)
    site_name = session.get("assigned_centre", "")

    if unknown_encoding is None:
        filename = f"{uuid.uuid4().hex}.jpg"
        photo_path = os.path.join(UNRECOGNIZED_PHOTO_DIR, filename)
        os.makedirs(UNRECOGNIZED_PHOTO_DIR, exist_ok=True)
        with open(photo_path, "wb") as f:
            f.write(image_data)
        add_log(db_path, None, site_name, "unknown", unrecognized_photo_path=photo_path)
        return jsonify({"verified": False, "error": "No face detected"})

    employees = get_all_employees(db_path)
    known = []
    for emp in employees:
        if emp["face_encoding"]:
            known.append((emp, pickle.loads(emp["face_encoding"])))
    if not known:
        filename = f"{uuid.uuid4().hex}.jpg"
        photo_path = os.path.join(UNRECOGNIZED_PHOTO_DIR, filename)
        os.makedirs(UNRECOGNIZED_PHOTO_DIR, exist_ok=True)
        with open(photo_path, "wb") as f:
            f.write(image_data)
        add_log(db_path, None, site_name, "unknown", unrecognized_photo_path=photo_path)
        return jsonify({"verified": False, "error": "No enrolled faces"})

    emp_list, enc_list = zip(*known)
    idx = match_face(unknown_encoding, list(enc_list))
    if idx is not None:
        emp = emp_list[idx]
        unchecked = get_unchecked_gadgets_for_employee(db_path, emp["id"])
        return jsonify({
            "verified": True,
            "employee_id": emp["id"],
            "full_name": emp["full_name"],
            "role": emp["role"],
            "department": emp["department"],
            "photo_url": f"/{emp['photo_path'].replace(os.sep, '/')}",
            "gadgets": unchecked,
        })

    filename = f"{uuid.uuid4().hex}.jpg"
    photo_path = os.path.join(UNRECOGNIZED_PHOTO_DIR, filename)
    os.makedirs(UNRECOGNIZED_PHOTO_DIR, exist_ok=True)
    with open(photo_path, "wb") as f:
        f.write(image_data)
    add_log(db_path, None, site_name, "unknown", unrecognized_photo_path=photo_path)
    return jsonify({"verified": False, "error": "No match found"})


@app.route("/staff/confirm-visit", methods=["POST"])
@login_required
@role_required("site_staff")
def staff_confirm_visit():
    data = request.get_json()
    log_id = add_log(
        db_path,
        data["employee_id"],
        session.get("assigned_centre", ""),
        "verified",
        data.get("purpose"),
        data.get("notes"),
    )
    for gadget in data.get("gadgets", []):
        add_gadget(
            db_path,
            log_id,
            gadget["gadget_type"],
            gadget["gadget_name"],
            gadget.get("serial_number"),
        )
    return jsonify({"success": True})


@app.route("/staff/checkout-gadget", methods=["POST"])
@login_required
@role_required("site_staff")
def staff_checkout_gadget():
    data = request.get_json()
    gadget_ids = data.get("gadget_ids", [])
    for gid in gadget_ids:
        checkout_gadget(db_path, gid)
    return jsonify({"success": True})


@app.route("/admin/gadgets")
@login_required
@role_required("admin")
def admin_gadgets():
    gadgets = get_all_checked_in_gadgets(db_path)
    return render_template("admin/gadgets.html", gadgets=gadgets)


@app.route("/admin/logs")
@login_required
@role_required("admin")
def admin_logs():
    date = request.args.get("date")
    site = request.args.get("site")
    name = request.args.get("name")
    status = request.args.get("status")
    centre = request.args.get("centre")
    log_entries = get_filtered_logs(db_path, date, site, name, status, centre)
    for log in log_entries:
        log["gadgets"] = get_gadgets_for_visit(db_path, log["id"])
    sites = get_distinct_sites(db_path)
    centres = get_all_centres(db_path)
    return render_template("admin/logs.html", logs=log_entries, sites=sites, centres=centres,
                           selected_date=date, selected_site=site, selected_name=name,
                           selected_status=status, selected_centre=centre)


@app.route("/admin/unrecognized")
@login_required
@role_required("admin")
def admin_unrecognized():
    return redirect(url_for("admin_logs"))


@app.route("/admin/unrecognized/<int:log_id>/delete", methods=["POST"], endpoint="admin_unrecognized_delete")
@login_required
@role_required("admin")
def admin_unrecognized_delete(log_id):
    delete_log(db_path, log_id)
    return redirect(url_for("admin_logs"))


@app.route("/admin/unrecognized/<int:log_id>/edit", methods=["GET", "POST"], endpoint="admin_unrecognized_edit")
@login_required
@role_required("admin")
def admin_unrecognized_edit(log_id):
    return redirect(url_for("admin_log_edit", log_id=log_id))


@app.route("/admin/logs/<int:log_id>/view")
@login_required
@role_required("admin")
def admin_log_view(log_id):
    log = get_log_by_id(db_path, log_id)
    if not log:
        return redirect(url_for("admin_logs"))
    return render_template("admin/log_view.html", log=log)


@app.route("/admin/logs/<int:log_id>/delete", methods=["POST"], endpoint="admin_log_delete")
@login_required
@role_required("admin")
def admin_log_delete(log_id):
    delete_log(db_path, log_id)
    return redirect(url_for("admin_logs"))


@app.route("/admin/logs/<int:log_id>/edit", methods=["GET", "POST"], endpoint="admin_log_edit")
@login_required
@role_required("admin")
def admin_log_edit(log_id):
    # Simple edit: allow updating purpose and notes and assigning employee
    from database import get_log_by_id as _get_log_by_id
    if request.method == "GET":
        log = _get_log_by_id(db_path, log_id)
        if not log:
            return redirect(url_for("admin_logs"))
        employees = get_all_employees(db_path)
        return render_template("admin/log_edit.html", log=log, employees=employees)
    # POST
    employee_id = request.form.get("employee_id")
    purpose = request.form.get("purpose")
    notes = request.form.get("notes")
    conn = get_connection(db_path)
    conn.execute("UPDATE visit_logs SET employee_id = ?, purpose = ?, notes = ?, status = ? WHERE id = ?",
                 (int(employee_id) if employee_id else None, purpose, notes, 'verified' if employee_id else 'unknown', log_id))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_logs"))



@app.route("/admin/centres", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_centres():
    centres = get_all_centres(db_path)
    staff_list = get_all_staff(db_path)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        centre = request.form.get("centre")
        error = None
        if not username or not password:
            error = "Username and password are required."
        elif get_user_by_username(db_path, username):
            error = "Username already exists."
        if error:
            return render_template("admin/centres.html", centres=centres, staff=staff_list, error=error, form=request.form)
        add_user(db_path, username, password, "site_staff", centre)
        return redirect(url_for("admin_centres"))
    return render_template("admin/centres.html", centres=centres, staff=staff_list)


@app.route("/admin/employees")
@login_required
@role_required("admin")
def admin_employees():
    name = request.args.get("name")
    department = request.args.get("department")
    role = request.args.get("role")
    centre = request.args.get("centre")
    employees = get_filtered_employees(db_path, name, department, role, centre)
    centres = get_all_centres(db_path)
    departments = get_distinct_departments(db_path)
    return render_template("admin/employees.html", employees=employees, centres=centres, departments=departments,
                           selected_name=name, selected_department=department, selected_role=role, selected_centre=centre)


@app.route("/admin/employees/<int:emp_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_employee_edit(emp_id):
    emp = get_employee_by_id(db_path, emp_id)
    if not emp:
        return redirect(url_for("admin_employees"))
    if request.method == "POST":
        full_name = request.form.get("full_name")
        role = request.form.get("role")
        department = request.form.get("department")
        if department == "__other__":
            department = request.form.get("department_other", "")
        contact = request.form.get("contact")
        centre = request.form.get("centre")
        update_employee(db_path, emp_id, full_name, role, department, contact, centre)
        return redirect(url_for("admin_employees"))
    centres = get_all_centres(db_path)
    departments = get_distinct_departments(db_path)
    return render_template("admin/employee_edit.html", emp=emp, centres=centres, departments=departments)


@app.route("/admin/employees/<int:emp_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def admin_employee_delete(emp_id):
    delete_employee(db_path, emp_id)
    return redirect(url_for("admin_employees"))


@app.route("/admin/employees/<int:emp_id>/create-login", methods=["POST"])
@login_required
@role_required("admin")
def admin_employee_create_login(emp_id):
    emp = get_employee_by_id(db_path, emp_id)
    if not emp:
        return redirect(url_for("admin_employees"))
    username = request.form.get("username")
    password = request.form.get("password")
    centre = request.form.get("centre") or emp.get("centre") or ""
    error = None
    if not username or not password:
        error = "Username and password are required."
    elif get_user_by_username(db_path, username):
        error = f"Username '{username}' already exists."
    if error:
        employees = get_filtered_employees(db_path)
        centres = get_all_centres(db_path)
        departments = get_distinct_departments(db_path)
        return render_template("admin/employees.html", employees=employees, centres=centres, departments=departments,
                               login_error=error, login_emp_id=emp_id)
    add_user(db_path, username, password, "site_staff", centre)
    return redirect(url_for("admin_employees"))


if __name__ == "__main__":
    app.run(debug=True)
