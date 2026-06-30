import os

from flask import Flask, jsonify, render_template, request

from database import init_db

app = Flask(__name__)

db_path = os.path.join(app.instance_path, "database.db")

with app.app_context():
    init_db(db_path)


@app.route("/")
def index():
    return render_template("base.html")


@app.route("/enroll", methods=["GET", "POST"])
def enroll():
    if request.method == "POST":
        data = request.get_json()
        return jsonify({"success": True})
    return render_template("enroll.html")


if __name__ == "__main__":
    app.run(debug=True)
