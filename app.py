import base64
import os
import pickle
import uuid

from flask import Flask, jsonify, render_template, request

from database import add_employee, init_db
from face_utils import encode_face

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


if __name__ == "__main__":
    app.run(debug=True)
