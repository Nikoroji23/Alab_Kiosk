"""Admin panel (Flask) - runs on its own port (default 5001).
Run:  python admin_app.py     then open  http://127.0.0.1:5001
"""
from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_from_directory, session, url_for)

import config
import database as db

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
db.init_db()


@app.before_request
def require_login():
    if request.endpoint in (None, "login", "static"):
        return None
    if not session.get("admin"):
        return redirect(url_for("login"))
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == config.ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("logs"))
        flash("Wrong password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------- Logs ----------------
@app.route("/")
def logs():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    rows = db.get_logs(q, status)
    out = sum(1 for r in rows if r["status"] == "borrowed")
    return render_template("logs.html", rows=rows, q=q, status=status,
                           out_count=out, back_count=len(rows) - out)


@app.route("/logs/<int:tid>/force-return", methods=["POST"])
def force_return(tid):
    if db.complete_return(tid):
        flash("Transaction marked as returned manually.", "ok")
    return redirect(request.referrer or url_for("logs"))


@app.route("/captures/<path:filename>")
def photo(filename):
    return send_from_directory(config.CAPTURE_DIR, filename)


# ---------------- Students ----------------
@app.route("/students")
def students():
    q = request.args.get("q", "").strip()
    return render_template("students.html", rows=db.list_students(q), q=q,
                           departments=config.DEPARTMENTS, years=config.YEAR_LEVELS)


@app.route("/students/add", methods=["POST"])
def student_add():
    f = request.form
    sn, name = f.get("student_number", "").strip(), f.get("name", "").strip()
    if not sn or not name:
        flash("Student number and name are required.", "error")
    elif db.add_student(sn, name, f.get("department", "").strip(), f.get("year_level", "").strip()):
        flash("Student added.", "ok")
    else:
        flash("That student number already exists.", "error")
    return redirect(url_for("students"))


@app.route("/students/<sn>/edit", methods=["GET", "POST"])
def student_edit(sn):
    student = db.get_student(sn)
    if not student:
        abort(404)
    if request.method == "POST":
        f = request.form
        new_sn = f.get("student_number", "").strip()
        if not new_sn:
            flash("Student number is required.", "error")
        elif db.update_student(sn, new_sn, f.get("name", "").strip(), f.get("department", "").strip(),
                               f.get("year_level", "").strip()):
            flash("Student updated.", "ok")
            return redirect(url_for("students"))
        else:
            flash("That student number already exists.", "error")
    return render_template("student_edit.html", s=student, departments=config.DEPARTMENTS, years=config.YEAR_LEVELS)


@app.route("/students/<sn>/delete", methods=["POST"])
def student_delete(sn):
    if db.delete_student(sn):
        flash("Student deleted.", "ok")
    else:
        flash("Cannot delete: this student still has unreturned items.", "error")
    return redirect(url_for("students"))


# ---------------- Compartments ----------------
@app.route("/compartments")
def compartments():
    return render_template("compartments.html", rows=db.list_compartments())


@app.route("/compartments/<int:cid>/status", methods=["POST"])
def compartment_status(cid):
    db.set_compartment_status(cid, request.form.get("status", ""))
    return redirect(url_for("compartments"))


if __name__ == "__main__":
    app.run(host=config.ADMIN_HOST, port=config.ADMIN_PORT, debug=False)
