# routes_api.py

from datetime import datetime
import json
import os

from flask import request, jsonify, session

from db_utils import get_cursor, dict_rows, conn
from auth_utils import require_login

import cloudinary
import cloudinary.uploader

# Use CLOUDINARY_URL from environment (Render env var). This line ensures HTTPS URLs.
cloudinary.config(secure=True)


def register_api_routes(app):
    # ---------- FOOD POSTS LIST + CREATE ----------

    @app.route("/api/food-posts", methods=["GET", "POST"])
    def api_food_posts():
        cur = get_cursor()
        if not cur:
            return jsonify({"error": "Database error"}), 500

        # ---------- CREATE POST ----------
        if request.method == "POST":
            if "user_id" not in session:
                return jsonify({"error": "Unauthorized"}), 401

            # Check content type: our create page sends multipart/form-data (FormData + file)
            is_multipart = request.content_type and "multipart/form-data" in request.content_type

            if is_multipart:
                form = request.form
                title = (form.get("title") or "").strip()
                desc = (form.get("description") or "").strip()
                category = form.get("category") or "Other"
                quantity = form.get("qty") or form.get("quantity") or ""
                location = (form.get("location") or "").strip()
                expires_at = form.get("expiry_time") or form.get("expires_at")
                dietary = form.getlist("diet") or []
                pickup_start = None
                pickup_end = None
                weight = 0
            else:
                # JSON fallback (not used by your current UI, but kept for safety)
                data = request.get_json() or {}
                title = (data.get("title") or "").strip()
                desc = (data.get("description") or "").strip()
                category = data.get("category") or "Other"
                quantity = data.get("quantity") or ""
                location = (data.get("location_text") or data.get("location") or "").strip()
                expires_at = data.get("expires_at")
                dietary = data.get("dietary_tags") or []
                pickup_start = data.get("pickup_window_start")
                pickup_end = data.get("pickup_window_end")
                weight = data.get("estimated_weight_kg") or 0

            if not title or not desc or not location or not expires_at:
                return jsonify({"error": "Missing required fields"}), 400

            # ---- handle image upload (Cloudinary) ----
            image_url = None
            image_file = request.files.get("photo") or request.files.get("image")
            if image_file and image_file.filename:
                try:
                    ext = os.path.splitext(image_file.filename)[1].lower()
                    if ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
                        uploaded = cloudinary.uploader.upload(
                            image_file,
                            folder="ecobite_uploads",
                            resource_type="image"
                        )
                        image_url = uploaded.get("secure_url")
                except Exception as e:
                    print("❌ Cloudinary upload error:", e)

            dietary_json = json.dumps(dietary)

            try:
                cur.execute(
                    """
                    INSERT INTO posts (
                        user_id, title, description, category, quantity,
                        estimated_weight_kg, dietary_json, location,
                        pickup_window_start, pickup_window_end, expires_at,
                        status, image_url, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, NOW())
                    """,
                    (
                        session["user_id"],
                        title,
                        desc,
                        category,
                        quantity,
                        weight,
                        dietary_json,
                        location,
                        pickup_start,
                        pickup_end,
                        expires_at,
                        image_url,
                    ),
                )
                conn.commit()
                post_id = cur.lastrowid

                new_post = {
                    "id": post_id,
                    "user_id": session["user_id"],
                    "title": title,
                    "description": desc,
                    "category": category,
                    "quantity": quantity,
                    "estimated_weight_kg": weight,
                    "dietary_json": dietary_json,
                    "location": location,
                    "pickup_window_start": pickup_start,
                    "pickup_window_end": pickup_end,
                    "expires_at": expires_at,
                    "status": "active",
                    "owner_email": session.get("email"),
                    "ownerEmail": session.get("email"),
                    "image_url": image_url,
                }
                return jsonify(new_post), 201

            except Exception as e:
                print(f"❌ API Create Post Error: {e}")
                conn.rollback()
                return jsonify({"error": str(e)}), 500

        # ---------- LIST POSTS (keep your existing code here) ----------
        #  ... (do not change the rest of api_food_posts)


        # ---------- LIST POSTS ----------
        try:
            status_filter = request.args.get("status", "available")
            search = (request.args.get("search") or "").strip()
            cat_filter = request.args.get("type", "All Types")
            diet_filter = request.args.get("dietary", "")
            sort_order = request.args.get("sort", "newest")

            query = """
                SELECT p.*, u.email AS owner_email
                FROM posts p
                JOIN users u ON p.user_id = u.id
                WHERE 1=1
            """
            params = []

            if status_filter == "available":
                query += " AND p.status='active' AND (p.expires_at IS NULL OR p.expires_at > NOW())"
            elif status_filter == "claimed":
                query += " AND p.status='claimed'"
            elif status_filter == "expired":
                query += " AND (p.status='expired' OR p.expires_at <= NOW())"

            if search:
                query += " AND (p.title LIKE ? OR p.description LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%"])

            if cat_filter and cat_filter != "All Types":
                query += " AND p.category = ?"
                params.append(cat_filter)

            if diet_filter:
                query += " AND p.dietary_json LIKE ?"
                params.append(f"%{diet_filter}%")

            if sort_order == "endingSoon":
                query += " ORDER BY p.expires_at ASC"
            else:
                query += " ORDER BY p.created_at DESC"

            cur.execute(query, tuple(params))
            posts = dict_rows(cur.fetchall(), cur.description)

            for p in posts:
                if "owner_email" in p:
                    p["ownerEmail"] = p["owner_email"]

            return jsonify(posts)

        except Exception as e:
            print(f"❌ API List Posts Error: {e}")
            return jsonify({"error": str(e)}), 500


        # ---------- LIST POSTS ----------
        try:
            status_filter = request.args.get("status", "available")
            search = (request.args.get("search") or "").strip()
            cat_filter = request.args.get("type", "All Types")
            diet_filter = request.args.get("dietary", "")
            sort_order = request.args.get("sort", "newest")

            query = """
                SELECT p.*, u.email AS owner_email
                FROM posts p
                JOIN users u ON p.user_id = u.id
                WHERE 1=1
            """
            params = []

            if status_filter == "available":
                query += " AND p.status='active' AND (p.expires_at IS NULL OR p.expires_at > NOW())"
            elif status_filter == "claimed":
                query += " AND p.status='claimed'"
            elif status_filter == "expired":
                query += " AND (p.status='expired' OR p.expires_at <= NOW())"

            if search:
                query += " AND (p.title LIKE ? OR p.description LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%"])

            if cat_filter and cat_filter != "All Types":
                query += " AND p.category = ?"
                params.append(cat_filter)

            if diet_filter:
                query += " AND p.dietary_json LIKE ?"
                params.append(f"%{diet_filter}%")

            if sort_order == "endingSoon":
                query += " ORDER BY p.expires_at ASC"
            else:
                query += " ORDER BY p.created_at DESC"

            cur.execute(query, tuple(params))
            posts = dict_rows(cur.fetchall(), cur.description)

            # Add camelCase for frontend
            for p in posts:
                if "owner_email" in p:
                    p["ownerEmail"] = p["owner_email"]

            return jsonify(posts)

        except Exception as e:
            print(f"❌ API List Posts Error: {e}")
            return jsonify({"error": str(e)}), 500

    # ---------- MY POSTS ----------
    @app.get("/api/food-posts/mine")
    def api_my_posts():
        need = require_login()
        if need:
            return jsonify({"error": "Unauthorized"}), 401

        cur = get_cursor()
        if not cur:
            return jsonify({"error": "Database error"}), 500

        try:
            cur.execute(
                """
                SELECT * FROM posts
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (session["user_id"],),
            )
            posts = dict_rows(cur.fetchall(), cur.description)

            # Add claims summary for each post
            for p in posts:
                cur.execute(
                    """
                    SELECT
                        COUNT(CASE WHEN status='pending' THEN 1 END) AS pending,
                        COUNT(CASE WHEN status='approved' THEN 1 END) AS accepted,
                        COUNT(CASE WHEN status='rejected' THEN 1 END) AS rejected
                    FROM claims
                    WHERE post_id = ?
                    """,
                    (p["id"],),
                )
                counts = dict_rows(cur.fetchall(), cur.description)[0]
                p["claims_summary"] = counts

            return jsonify(posts)
        except Exception as e:
            print(f"❌ API My Posts Error: {e}")
            return jsonify({"error": str(e)}), 500

    # ---------- SINGLE POST ----------
    @app.get("/api/food-posts/<int:id>")
    def api_get_post(id):
        cur = get_cursor()
        if not cur:
            return jsonify({"error": "Database error"}), 500

        try:
            cur.execute(
                """
                SELECT p.*, u.email AS owner_email
                FROM posts p
                JOIN users u ON p.user_id = u.id
                WHERE p.id = ?
                """,
                (id,),
            )
            rows = cur.fetchall()
            if not rows:
                return jsonify({"error": "Post not found"}), 404

            post = dict_rows(rows, cur.description)[0]
            post["ownerEmail"] = post.get("owner_email")

            # If owner, also include claims
            if "user_id" in session and session["user_id"] == post["user_id"]:
                cur.execute(
                    """
                    SELECT c.*, u.email AS claimer_email
                    FROM claims c
                    JOIN users u ON c.claimer_id = u.id
                    WHERE c.post_id = ?
                    """,
                    (id,),
                )
                post["claims"] = dict_rows(cur.fetchall(), cur.description)

            return jsonify(post)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ---------- UPDATE POST STATUS ----------
    @app.patch("/api/food-posts/<int:id>/status")
    def api_update_post_status(id):
        need = require_login()
        if need:
            return jsonify({"error": "Unauthorized"}), 401

        cur = get_cursor()
        if not cur:
            return jsonify({"error": "Database error"}), 500

        data = request.get_json() or {}
        new_status = data.get("status")
        if not new_status:
            return jsonify({"error": "Status required"}), 400

        try:
            cur.execute("SELECT user_id FROM posts WHERE id=?", (id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Post not found"}), 404
            if row[0] != session["user_id"]:
                return jsonify({"error": "Forbidden"}), 403

            cur.execute("UPDATE posts SET status=? WHERE id=?", (new_status, id))
            conn.commit()
            return jsonify({"success": True, "status": new_status})
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500

    # ---------- CREATE CLAIM ----------
    @app.post("/api/food-posts/<int:id>/claims")
    def api_create_claim(id):
        need = require_login()
        if need:
            return jsonify({"error": "Unauthorized"}), 401

        cur = get_cursor()
        if not cur:
            return jsonify({"error": "Database error"}), 500

        data = request.get_json() or {}
        req_qty = data.get("requested_quantity", "1")
        msg = data.get("message", "")

        try:
            cur.execute(
                "SELECT user_id, status, expires_at, quantity FROM posts WHERE id=?",
                (id,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Post not found"}), 404

            owner_id, status, expires_at, qty = row

            if owner_id == session["user_id"]:
                return jsonify({"error": "Cannot claim own post"}), 400
            if status != "active":
                return jsonify({"error": "Post not available"}), 400
            if expires_at and expires_at <= datetime.now():
                return jsonify({"error": "Post expired"}), 400

            cur.execute(
                """
                INSERT INTO claims (post_id, claimer_id, message, requested_quantity,
                                    status, created_at)
                VALUES (?, ?, ?, ?, 'pending', NOW())
                """,
                (id, session["user_id"], msg, req_qty),
            )
            conn.commit()

            claim_id = cur.lastrowid
            cur.execute("SELECT * FROM claims WHERE id=?", (claim_id,))
            new_claim = dict_rows(cur.fetchall(), cur.description)[0]
            return jsonify(new_claim), 201

        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500

    # ---------- MY CLAIMS ----------
    @app.get("/api/claims/mine")
    def api_my_claims():
        need = require_login()
        if need:
            return jsonify({"error": "Unauthorized"}), 401

        cur = get_cursor()
        if not cur:
            return jsonify({"error": "Database error"}), 500

        try:
            cur.execute(
                """
                SELECT c.*, p.title AS post_title, p.location, p.expires_at,
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
            return jsonify(claims)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ---------- CLAIMS FOR MY POSTS ----------
    @app.get("/api/claims/for-my-posts")
    def api_incoming_claims():
        need = require_login()
        if need:
            return jsonify({"error": "Unauthorized"}), 401

        cur = get_cursor()
        if not cur:
            return jsonify({"error": "Database error"}), 500

        try:
            cur.execute(
                """
                SELECT c.*, p.title AS post_title, u.email AS claimer_email
                FROM claims c
                JOIN posts p ON c.post_id = p.id
                JOIN users u ON c.claimer_id = u.id
                WHERE p.user_id = ?
                ORDER BY c.created_at DESC
                """,
                (session["user_id"],),
            )
            claims = dict_rows(cur.fetchall(), cur.description)
            return jsonify(claims)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ---------- UPDATE CLAIM (approve / reject) ----------
    @app.patch("/api/claims/<int:id>")
    def api_update_claim(id):
        need = require_login()
        if need:
            return jsonify({"error": "Unauthorized"}), 401

        cur = get_cursor()
        if not cur:
            return jsonify({"error": "Database error"}), 500

        data = request.get_json() or {}
        action = data.get("status")  # accepted or rejected
        if action not in ["accepted", "rejected"]:
            return jsonify({"error": "Invalid status"}), 400

        try:
            cur.execute(
                """
                SELECT c.post_id, p.user_id, c.requested_quantity, p.quantity
                FROM claims c
                JOIN posts p ON c.post_id = p.id
                WHERE c.id = ?
                """,
                (id,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Claim not found"}), 404

            post_id, owner_id, req_qty, post_qty = row
            if owner_id != session["user_id"]:
                return jsonify({"error": "Forbidden"}), 403

            new_status = "approved" if action == "accepted" else "rejected"

            cur.execute(
                "UPDATE claims SET status=?, decided_at=NOW() WHERE id=?",
                (new_status, id),
            )

            # If approved, optionally decrement quantity / mark claimed
            if new_status == "approved":
                try:
                    p_q = float(str(post_qty).split()[0])
                    r_q = float(str(req_qty).split()[0])
                    rem_q = max(0, p_q - r_q)

                    if rem_q <= 0:
                        cur.execute(
                            "UPDATE posts SET status='claimed', quantity='0' WHERE id=?",
                            (post_id,),
                        )
                    else:
                        cur.execute(
                            "UPDATE posts SET quantity=? WHERE id=?",
                            (str(rem_q), post_id),
                        )
                except Exception:
                    pass

            conn.commit()
            return jsonify({"success": True, "status": new_status})
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500

    # ---------- CANCEL CLAIM ----------
    @app.patch("/api/claims/<int:id>/cancel")
    def api_cancel_claim(id):
        need = require_login()
        if need:
            return jsonify({"error": "Unauthorized"}), 401

        cur = get_cursor()
        if not cur:
            return jsonify({"error": "Database error"}), 500

        try:
            cur.execute("SELECT claimer_id FROM claims WHERE id=?", (id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Claim not found"}), 404
            if row[0] != session["user_id"]:
                return jsonify({"error": "Forbidden"}), 403

            cur.execute("UPDATE claims SET status='cancelled' WHERE id=?", (id,))
            conn.commit()
            return jsonify({"success": True})
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500

    # ---------- STATS ----------
    @app.get("/api/stats/global")
    def api_stats_global():
        from db_utils import compute_stats

        return jsonify(compute_stats())

    @app.get("/api/stats/me")
    def api_stats_me():
        need = require_login()
        if need:
            return jsonify({"error": "Unauthorized"}), 401

        from db_utils import compute_stats

        return jsonify(compute_stats(session["user_id"]))
