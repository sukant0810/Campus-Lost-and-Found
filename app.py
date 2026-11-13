import os
import re
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, abort, session
from werkzeug.security import generate_password_hash, check_password_hash
from mysql.connector import IntegrityError
from db import run, run_insert, init_users_table, init_claim_tables

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-only-key")
init_users_table()
init_claim_tables()

CATEGORIES = ["Electronics", "Books", "ID Card", "Clothing", "Accessories", "Keys", "Bags", "Other"]
STATUSES = ["Lost", "Found", "Returned"]
FIELDS = ["item_name", "description", "category", "location", "date_found", "owner_name", "contact"]
PER_PAGE = 9
CONTACT_RE = re.compile(r"^([\w.+-]+@[\w-]+\.[\w.]+|\+?\d{10,13})$")
USERNAME_RE = re.compile(r"^\w{3,30}$")
DEFAULT_QUESTION = "Describe a unique detail of this item (colour, marks, contents)."


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin access required.", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapper


@app.before_request
def require_login():
    if request.endpoint not in ("login", "signup", "static") and not session.get("logged_in"):
        return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        errors = []
        if not USERNAME_RE.match(username):
            errors.append("Username must be 3-30 letters, numbers or underscores.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if not errors:
            try:
                run("INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                    (username, generate_password_hash(password)), write=True)
                flash("Account created. Please login.", "success")
                return redirect(url_for("login"))
            except IntegrityError:
                errors.append("Username already exists.")
        for e in errors:
            flash(e, "error")
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = run("SELECT * FROM users WHERE username = %s", (username,), one=True)
        if user and check_password_hash(user["password_hash"], password):
            admin_name = os.getenv("ADMIN_USERNAME", "").strip().lower()
            session["logged_in"] = True
            session["username"] = user["username"]
            session["is_admin"] = bool(admin_name) and user["username"].lower() == admin_name
            flash("Logged in successfully.", "success")
            return redirect(url_for("index"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("login"))


def validate(f):
    errors = []
    if len(f["item_name"]) < 2:
        errors.append("Item name must be at least 2 characters.")
    if f["category"] not in CATEGORIES:
        errors.append("Please select a valid category.")
    if not f["location"]:
        errors.append("Location is required.")
    if len(f["description"]) < 5:
        errors.append("Description must be at least 5 characters.")
    if len(f["owner_name"]) < 2:
        errors.append("Name must be at least 2 characters.")
    if not CONTACT_RE.match(f["contact"]):
        errors.append("Enter a valid email or 10-digit phone number.")
    try:
        if datetime.strptime(f["date_found"], "%Y-%m-%d").date() > date.today():
            errors.append("Date cannot be in the future.")
    except ValueError:
        errors.append("Enter a valid date.")
    return errors


@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    page = max(request.args.get("page", 1, type=int), 1)

    where = " WHERE 1=1"
    params = []
    if q:
        where += " AND (item_name LIKE %s OR category LIKE %s OR location LIKE %s)"
        params += [f"%{q}%"] * 3
    if status in STATUSES:
        where += " AND status = %s"
        params.append(status)

    count = run("SELECT COUNT(*) AS n FROM items" + where, params, one=True)["n"]
    pages = max(1, -(-count // PER_PAGE))
    page = min(page, pages)
    items = run("SELECT * FROM items" + where + " ORDER BY id DESC LIMIT %s OFFSET %s",
                params + [PER_PAGE, (page - 1) * PER_PAGE])

    stats = {s: 0 for s in STATUSES}
    total = 0
    for row in run("SELECT status, COUNT(*) AS n FROM items GROUP BY status"):
        total += row["n"]
        if row["status"] in stats:
            stats[row["status"]] = row["n"]

    return render_template("index.html", items=items, q=q, status=status, statuses=STATUSES,
                           page=page, pages=pages, count=count, stats=stats, total=total)


@app.route("/report/<kind>", methods=["GET", "POST"])
def report(kind):
    if kind not in ("lost", "found"):
        abort(404)
    form = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in FIELDS}
        question = request.form.get("verify_question", "").strip() if kind == "found" else ""
        answer = request.form.get("verify_answer", "").strip() if kind == "found" else ""
        form["verify_question"] = question
        form["verify_answer"] = answer
        errors = validate(form)
        if bool(question) != bool(answer):
            errors.append("Fill both the verification question and its answer, or leave both empty.")
        if len(question) > 150 or len(answer) > 100:
            errors.append("Verification question max 150 characters, answer max 100.")
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            item_id = run_insert(
                "INSERT INTO items (item_name, description, category, location, date_found, status, owner_name, contact) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (form["item_name"], form["description"], form["category"], form["location"],
                 form["date_found"], kind.title(), form["owner_name"], form["contact"]),
            )
            if question and answer:
                run("INSERT INTO verifications (item_id, question, answer) VALUES (%s, %s, %s)",
                    (item_id, question, answer), write=True)
            flash(f"{kind.title()} item reported successfully.", "success")
            return redirect(url_for("index"))
    return render_template("report.html", kind=kind, form=form, categories=CATEGORIES,
                           today=date.today().isoformat())


@app.route("/item/<int:item_id>")
def details(item_id):
    item = run("SELECT * FROM items WHERE id = %s", (item_id,), one=True)
    if not item:
        abort(404)
    if session.get("is_admin"):
        claims = run("SELECT * FROM claims WHERE item_id = %s ORDER BY id DESC", (item_id,))
        verification = run("SELECT * FROM verifications WHERE item_id = %s", (item_id,), one=True)
    else:
        claims = run("SELECT * FROM claims WHERE item_id = %s AND username = %s ORDER BY id DESC",
                     (item_id, session.get("username")))
        verification = None
    return render_template("details.html", item=item, claims=claims, verification=verification)


@app.route("/item/<int:item_id>/claim", methods=["GET", "POST"])
def claim(item_id):
    item = run("SELECT * FROM items WHERE id = %s", (item_id,), one=True)
    if not item:
        abort(404)
    if item["status"] != "Found":
        flash("Only Found items can be claimed.", "error")
        return redirect(url_for("details", item_id=item_id))
    v = run("SELECT question FROM verifications WHERE item_id = %s", (item_id,), one=True)
    question = v["question"] if v else DEFAULT_QUESTION
    form = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in ("claimant_name", "contact", "answer")}
        errors = []
        if len(form["claimant_name"]) < 2:
            errors.append("Name must be at least 2 characters.")
        if not CONTACT_RE.match(form["contact"]):
            errors.append("Enter a valid email or 10-digit phone number.")
        if not 2 <= len(form["answer"]) <= 200:
            errors.append("Answer must be 2 to 200 characters.")
        pending = run("SELECT id FROM claims WHERE item_id = %s AND username = %s AND status = 'Pending'",
                      (item_id, session.get("username")), one=True)
        if pending:
            errors.append("You already have a pending claim for this item.")
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            run("INSERT INTO claims (item_id, username, claimant_name, contact, answer) "
                "VALUES (%s, %s, %s, %s, %s)",
                (item_id, session.get("username"), form["claimant_name"], form["contact"], form["answer"]),
                write=True)
            flash("Claim submitted. The admin will verify your answer.", "success")
            return redirect(url_for("details", item_id=item_id))
    return render_template("claim.html", item=item, question=question, form=form)


@app.route("/claim/<int:claim_id>/approve", methods=["POST"])
@admin_required
def approve_claim(claim_id):
    c = run("SELECT * FROM claims WHERE id = %s", (claim_id,), one=True)
    if not c or c["status"] != "Pending":
        flash("Claim not found or already reviewed.", "error")
        return redirect(url_for("index"))
    run("UPDATE claims SET status = 'Approved' WHERE id = %s", (claim_id,), write=True)
    run("UPDATE claims SET status = 'Rejected' WHERE item_id = %s AND id != %s AND status = 'Pending'",
        (c["item_id"], claim_id), write=True)
    run("UPDATE items SET status = 'Returned' WHERE id = %s", (c["item_id"],), write=True)
    flash("Claim approved. Item marked as Returned.", "success")
    return redirect(url_for("details", item_id=c["item_id"]))


@app.route("/claim/<int:claim_id>/reject", methods=["POST"])
@admin_required
def reject_claim(claim_id):
    c = run("SELECT * FROM claims WHERE id = %s", (claim_id,), one=True)
    if not c or c["status"] != "Pending":
        flash("Claim not found or already reviewed.", "error")
        return redirect(url_for("index"))
    run("UPDATE claims SET status = 'Rejected' WHERE id = %s", (claim_id,), write=True)
    flash("Claim rejected.", "success")
    return redirect(url_for("details", item_id=c["item_id"]))


@app.route("/item/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(item_id):
    item = run("SELECT * FROM items WHERE id = %s", (item_id,), one=True)
    if not item:
        abort(404)
    form = {k: "" if item[k] is None else str(item[k]) for k in FIELDS}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in FIELDS}
        errors = validate(form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            run(
                "UPDATE items SET item_name = %s, description = %s, category = %s, location = %s, "
                "date_found = %s, owner_name = %s, contact = %s WHERE id = %s",
                (form["item_name"], form["description"], form["category"], form["location"],
                 form["date_found"], form["owner_name"], form["contact"], item_id),
                write=True,
            )
            flash("Item updated successfully.", "success")
            return redirect(url_for("details", item_id=item_id))
    return render_template("edit.html", item=item, form=form, categories=CATEGORIES,
                           today=date.today().isoformat())


@app.route("/item/<int:item_id>/return", methods=["POST"])
@admin_required
def mark_returned(item_id):
    changed = run("UPDATE items SET status = 'Returned' WHERE id = %s AND status != 'Returned'",
                  (item_id,), write=True)
    flash("Item marked as Returned." if changed else "Item not found or already returned.",
          "success" if changed else "error")
    return redirect(url_for("details", item_id=item_id))


@app.route("/item/<int:item_id>/delete", methods=["POST"])
@admin_required
def delete(item_id):
    run("DELETE FROM claims WHERE item_id = %s", (item_id,), write=True)
    run("DELETE FROM verifications WHERE item_id = %s", (item_id,), write=True)
    changed = run("DELETE FROM items WHERE id = %s", (item_id,), write=True)
    flash("Item deleted." if changed else "Item not found.", "success" if changed else "error")
    return redirect(url_for("index"))


@app.errorhandler(404)
def not_found(e):
    return render_template("base.html", not_found=True), 404


if __name__ == "__main__":
    app.run(debug=True)