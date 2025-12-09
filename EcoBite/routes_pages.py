import json
import os
from datetime import datetime, timedelta

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from db_utils import get_cursor, compute_stats, dict_rows, conn
from auth_utils import require_login, ALLOWED_ROLES

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def register_pages(app):
    # --------------- Landing & Auth ----------------

    @app.get("/")
    def landing():
        if "user_id" in session:
            return redirect(url_for("home"))
        return render_template("landing.html")

    @app.get("/get-started")
    def get_started():
        if "user_id" in session:
            return redirect(url_for("home"))
        return render_template("get_started.html")

    @app.get("/login")
    def login():
        if "user_id" in session:
            return redirect(url_for("home"))
        return render_template("login.html")

    @app.post("/login")
    def login_post():
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        cur = get_cursor()
        if cur is None:
            return redirect(url_for("login"))
        try:
            cur.execute(
                "SELECT id,email,password_hash,role FROM users WHERE email=?",
                (email,),
            )
            row = cur.fetchone()
            if not row or not check_password_hash(row[2], password):
                flash("Invalid email or password.", "error")
                return redirect(url_for("login"))
            session.update({"user_id": row[0], "email": row[1], "role": row[3]})
            flash("Welcome back!", "success")
            return redirect(url_for("home"))
        except Exception as e:
            print(f"❌ Login error: {e}")
            flash("An error occurred. Please try again.", "error")
            return redirect(url_for("login"))

    @app.post("/logout")
    def logout():
        session.clear()
        flash("Logged out.", "info")
        return redirect(url_for("landing"))

    @app.get("/signup")
    def signup():
        if "user_id" in session:
            return redirect(url_for("home"))
        return render_template("signup.html")

    @app.post("/signup")
    def signup_post():
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        name = request.form.get("name", "").strip()
        role = (request.form.get("role", "user") or "user").strip().lower()
        if role not in ALLOWED_ROLES:
            role = "user"

        if not email or not password or not name:
            flash("Email, name, and password are required.", "error")
            return redirect(url_for("signup"))

        pw_hash = generate_password_hash(password)
        cur = get_cursor()
        if cur is None:
            flash("Database connection error. Please try again.", "error")
            return redirect(url_for("signup"))

        try:
            cur.execute("SELECT id FROM users WHERE email=?", (email,))
            if cur.fetchone():
                flash(
                    "Email already exists. Please use a different email or login instead.",
                    "error",
                )
                return redirect(url_for("signup"))

            cur.execute(
                "INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,?)",
                (name, email, pw_hash, role),
            )
            conn.commit()

            cur.execute("SELECT id,role FROM users WHERE email=?", (email,))
            u = cur.fetchone()
            session.update({"user_id": u[0], "email": email, "role": u[1]})
            flash("Account created!", "success")
            return redirect(url_for("home"))
        except Exception as e:
            conn.rollback()
            print(f"❌ Signup error: {e}")
            flash("An error occurred. Please try again.", "error")
            return redirect(url_for("signup"))

    # --------------- Home / Feed ----------------

    @app.get("/home")
    def home():
        if "user_id" not in session:
            return redirect(url_for("login"))
        cur = get_cursor()
        posts = []
        if cur:
            try:
                cur.execute(
                    """
                    SELECT p.id,p.description,p.category,p.quantity,p.status,
                           p.location,p.expires_at,u.email AS owner_email
                    FROM posts p
                    JOIN users u ON p.user_id=u.id
                    WHERE p.status='active'
                      AND (p.expires_at IS NULL OR p.expires_at > NOW())
                    ORDER BY p.created_at DESC
                    """
                )
                posts = dict_rows(cur.fetchall(), cur.description)
            except Exception as e:
                print("❌ Feed error:", e)
                posts = []
        stats = compute_stats()
        return render_template(
            "index.html", posts=posts, stats=stats, email=session["email"]
        )

    # --------------- Create Post (HTML) ----------------

    @app.route("/create", methods=["GET", "POST"])
    def create():
        need = require_login()
        if need:
            return need

        if request.method == "POST":
            desc = request.form.get("description", "").strip()
            category = request.form.get("category", "Other")
            qty = request.form.get("qty", "")
            expiry_str = request.form.get("expiry_time", "")
            location = request.form.get("location", "").strip()
            diets = request.form.getlist("diet")
            dietary_json = json.dumps(diets) if diets else None

            photo = request.files.get("photo")
            photo_filename = None
            if photo and photo.filename:
                filename = secure_filename(photo.filename)
                photo_filename = f"{session['user_id']}_{filename}"
                photo.save(os.path.join(UPLOAD_FOLDER, photo_filename))

            if not desc or not expiry_str or not location:
                flash("All required fields must be filled.", "error")
                return redirect(url_for("create"))

            try:
                if "T" in expiry_str:
                    expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%dT%H:%M")
                else:
                    expiry_dt = datetime.now() + timedelta(
                        minutes=int(expiry_str) if expiry_str.isdigit() else 60
                    )

                cur = get_cursor()
                if cur is None:
                    flash("Database connection error. Please try again.", "error")
                    return redirect(url_for("create"))

                # NOTE: Make sure your 'posts' table has a VARCHAR column named 'photo'
                # or remove 'photo' from these fields if you don't want to store filenames.
                cur.execute(
                    """
                    INSERT INTO posts (
                        user_id,description,category,quantity,
                        dietary_json,location,expires_at,status,photo
                    )
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        session["user_id"],
                        desc,
                        category,
                        qty or None,
                        dietary_json,
                        location,
                        expiry_dt,
                        "active",
                        photo_filename,
                    ),
                )
                conn.commit()
                flash("Post shared successfully!", "success")
                return redirect(url_for("home"))
            except ValueError as e:
                print("❌ Date parse error:", e)
                flash("Invalid date/time format.", "error")
                return redirect(url_for("create"))
            except Exception as e:
                print("❌ Post error:", e)
                conn.rollback()
                flash("Could not create post.", "error")
                return redirect(url_for("create"))

        return render_template("create.html")

    # --------------- My Posts ----------------

    @app.get("/myposts")
    def myposts():
        need = require_login()
        if need:
            return need
        cur = get_cursor()
        if cur is None:
            flash("Database connection error. Please try again.", "error")
            return redirect(url_for("home"))
        posts = []
        try:
            cur.execute(
                """
                SELECT id,description,category,quantity,status,created_at
                FROM posts WHERE user_id=? ORDER BY created_at DESC
                """,
                (session["user_id"],),
            )
            posts = dict_rows(cur.fetchall(), cur.description)
        except Exception as e:
            print("❌ MyPosts error:", e)
            posts = []
        stats = compute_stats(session["user_id"])
        return render_template("myposts.html", posts=posts, stats=stats)

    # --------------- Profile ----------------

    @app.get("/profile")
    def profile():
        need = require_login()
        if need:
            return need
        stats = compute_stats(session["user_id"])
        return render_template("profile.html", stats=stats)
