# routes_claims.py

from datetime import datetime
from flask import (
    request, redirect, url_for, flash,
    session, render_template
)

from db_utils import get_cursor, dict_rows, conn
from auth_utils import require_login


def register_claim_routes(app):
    # =====================================================
    # CLAIM SYSTEM (HTML pages: Request / Approve / Reject)
    # =====================================================

    # ---- 1. Claim a post (HTML form) ----
    @app.post("/claim/<int:post_id>")
    def claim_post(post_id):
        need = require_login()
        if need:
            return need

        message = request.form.get("message", "").strip()
        cur = get_cursor()
        if cur is None:
            flash("Database connection error. Please try again.", "error")
            return redirect(url_for("home"))

        try:
            # Prevent claiming own post
            cur.execute("SELECT user_id,status FROM posts WHERE id=?", (post_id,))
            row = cur.fetchone()

            if not row:
                flash("Post not found.", "error")
                return redirect(url_for("home"))

            if row[0] == session["user_id"]:
                flash("You cannot claim your own post.", "error")
                return redirect(url_for("home"))

            if row[1] != "active":
                flash("Post is not available.", "error")
                return redirect(url_for("home"))

            # Insert claim
            cur.execute(
                """
                INSERT INTO claims (post_id, claimer_id, message)
                VALUES (?, ?, ?)
                """,
                (post_id, session["user_id"], message or None),
            )
            conn.commit()
            flash("Request sent to owner!", "success")

        except Exception as e:
            # Handle duplicate claim nicely
            msg = str(e)
            conn.rollback()
            if "Duplicate" in msg or "duplicate" in msg:
                flash("You already requested this item.", "warning")
            else:
                print("❌ Claim error:", e)
                flash("Could not process claim.", "error")

        return redirect(url_for("home"))

    # ---- 2. Owner approves / rejects (HTML) ----
    @app.post("/claim/<int:claim_id>/<action>")
    def update_claim_status(claim_id, action):
        need = require_login()
        if need:
            return need

        if action not in ("approve", "reject"):
            return "Invalid action", 400

        cur = get_cursor()
        if cur is None:
            flash("Database connection error. Please try again.", "error")
            return redirect(url_for("myposts"))

        try:
            cur.execute(
                """
                SELECT c.post_id, p.user_id
                FROM claims c
                JOIN posts p ON c.post_id = p.id
                WHERE c.id = ?
                """,
                (claim_id,),
            )
            claim = cur.fetchone()
            if not claim:
                flash("Claim not found.", "error")
                return redirect(url_for("myposts"))

            post_id, owner_id = claim
            if owner_id != session["user_id"]:
                flash("You are not authorized.", "error")
                return redirect(url_for("myposts"))

            new_status = "approved" if action == "approve" else "rejected"

            cur.execute(
                """
                UPDATE claims
                SET status = ?, decided_at = NOW()
                WHERE id = ?
                """,
                (new_status, claim_id),
            )

            # If approved -> mark post as claimed
            if new_status == "approved":
                cur.execute("UPDATE posts SET status='claimed' WHERE id=?", (post_id,))

            conn.commit()
            flash(f"Claim {new_status}.", "success")

        except Exception as e:
            print("❌ Approve/Reject error:", e)
            conn.rollback()
            flash("Action failed.", "error")

        return redirect(url_for("myposts"))

    # ---- 3. My Requests (claims made by me) ----
    @app.get("/requests")
    def requests_page():
        need = require_login()
        if need:
            return need

        cur = get_cursor()
        if cur is None:
            flash("Database connection error. Please try again.", "error")
            return redirect(url_for("home"))

        claims = []
        try:
            cur.execute(
                """
                SELECT c.id, c.status, c.message, c.created_at,
                       p.description, p.category, p.location,
                       u.email AS owner_email
                FROM claims c
                JOIN posts p ON c.post_id = p.id
                JOIN users u ON p.user_id = u.id
                WHERE c.claimer_id = ?
                ORDER BY c.created_at DESC
                """,
                (session["user_id"],),
            )
            claims = dict_rows(cur.fetchall(), cur.description)
        except Exception as e:
            print("❌ Requests error:", e)
            claims = []

        return render_template("requests.html", claims=claims)

    # ---- 4. Claims Received (requests on my posts) ----
    @app.get("/claims")
    def claims():
        need = require_login()
        if need:
            return need

        cur = get_cursor()
        if cur is None:
            flash("Database connection error. Please try again.", "error")
            return redirect(url_for("home"))

        incoming = []
        try:
            cur.execute(
                """
                SELECT c.id, c.status, c.message, c.created_at,
                       p.description,
                       u.email AS claimer_email
                FROM claims c
                JOIN posts p ON c.post_id = p.id
                JOIN users u ON c.claimer_id = u.id
                WHERE p.user_id = ?
                ORDER BY c.created_at DESC
                """,
                (session["user_id"],),
            )
            incoming = dict_rows(cur.fetchall(), cur.description)
        except Exception as e:
            print("❌ Claims error:", e)
            incoming = []

        return render_template("claims.html", claims=incoming)
