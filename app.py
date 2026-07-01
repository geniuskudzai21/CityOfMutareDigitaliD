import base64
import functools
import os
import pickle
import tempfile
import uuid

from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from werkzeug.security import check_password_hash

from database import (
    add_employee,
    add_log,
    get_all_employees,
    get_dashboard_stats,
    get_distinct_sites,
    get_filtered_logs,
    get_staff_recent_logs,
    get_user_by_username,
    init_db,
)
from face_utils import encode_face, match_face

app = Flask(__name__)
app.secret_key = os.urandom(32).hex()

db_path = os.path.join(app.instance_path, "database.db")
PHOTO_DIR = os.path.join(app.static_folder, "enrolled_photos")

with app.app_context():
    init_db(db_path)


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
    return redirect(url_for("login"))


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
    recent_logs = get_staff_recent_logs(db_path, centre)
    return render_template("staff_dashboard.html", centre=centre, logs=recent_logs)


@app.route("/enroll", methods=["GET", "POST"])
@login_required
@role_required("admin")
def enroll():
    if request.method == "POST":
        data = request.get_json()

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
            photo_path,
            pickle.dumps(encoding),
        )
        return jsonify({"success": True})
    return render_template("enroll.html")


@app.route("/verify", methods=["GET", "POST"])
@login_required
def verify():
    if request.method == "GET":
        return render_template("verify.html")
    data = request.get_json()

    header, encoded = data["photo"].split(",", 1)
    image_data = base64.b64decode(encoded)

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(image_data)
        tmp_path = tmp.name

    site_name = data.get("site_name", "Main Gate")

    unknown_encoding = encode_face(tmp_path)
    os.remove(tmp_path)

    if unknown_encoding is None:
        add_log(db_path, None, site_name, "unknown")
        return jsonify({"verified": False})

    employees = get_all_employees(db_path)
    known = []
    for emp in employees:
        if emp["face_encoding"]:
            known.append(pickle.loads(emp["face_encoding"]))

    if not known:
        add_log(db_path, None, site_name, "unknown")
        return jsonify({"verified": False})

    idx = match_face(unknown_encoding, known)
    if idx is not None:
        emp = employees[idx]
        add_log(db_path, emp["id"], site_name, "verified")
        return jsonify({
            "verified": True,
            "full_name": emp["full_name"],
            "role": emp["role"],
            "department": emp["department"],
            "photo_url": f"/{emp['photo_path'].replace(os.sep, '/')}",
        })

    add_log(db_path, None, site_name, "unknown")
    return jsonify({"verified": False})


@app.route("/logs")
@login_required
@role_required("admin")
def logs():
    date = request.args.get("date")
    site = request.args.get("site")
    name = request.args.get("name")
    log_entries = get_filtered_logs(db_path, date, site, name)
    sites = get_distinct_sites(db_path)
    return render_template("logs.html", logs=log_entries, sites=sites, selected_date=date, selected_site=site, selected_name=name)


if __name__ == "__main__":
    app.run(debug=True)
