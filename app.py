import base64
import os
import pickle
import tempfile
import uuid

from flask import Flask, jsonify, render_template, request

from database import add_employee, add_log, get_all_employees, init_db
from face_utils import encode_face, match_face

app = Flask(__name__)

db_path = os.path.join(app.instance_path, "database.db")
PHOTO_DIR = os.path.join(app.static_folder, "enrolled_photos")

with app.app_context():
    init_db(db_path)


@app.route("/")
def index():
    return render_template("base.html")


@app.route("/enroll", methods=["GET", "POST"])
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


@app.route("/verify", methods=["POST"])
def verify():
    data = request.get_json()

    header, encoded = data["photo"].split(",", 1)
    image_data = base64.b64decode(encoded)

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(image_data)
        tmp_path = tmp.name

    unknown_encoding = encode_face(tmp_path)
    os.remove(tmp_path)

    if unknown_encoding is None:
        add_log(db_path, None, "Main Gate", "unknown")
        return jsonify({"verified": False})

    employees = get_all_employees(db_path)
    known = []
    for emp in employees:
        if emp["face_encoding"]:
            known.append(pickle.loads(emp["face_encoding"]))

    if not known:
        add_log(db_path, None, "Main Gate", "unknown")
        return jsonify({"verified": False})

    idx = match_face(unknown_encoding, known)
    if idx is not None:
        emp = employees[idx]
        add_log(db_path, emp["id"], "Main Gate", "verified")
        return jsonify({
            "verified": True,
            "full_name": emp["full_name"],
            "role": emp["role"],
            "department": emp["department"],
            "photo_url": f"/{emp['photo_path'].replace(os.sep, '/')}",
        })

    add_log(db_path, None, "Main Gate", "unknown")
    return jsonify({"verified": False})


if __name__ == "__main__":
    app.run(debug=True)
