# auth_utils.py

from functools import wraps
from flask import session, redirect, url_for, flash

# Roles your site uses
ALLOWED_ROLES = {"user", "admin"}


def require_login(role=None):
    """
    For HTML views:
        need = require_login()
        if need: return need

    For API views:
        need = require_login()
        if need: return jsonify(...), 401  (they ignore the redirect and use JSON)
    """
    if "user_id" not in session:
        # Not logged in
        flash("Please log in first.", "error")
        return redirect(url_for("login"))

    if role:
        allowed = {role} if isinstance(role, str) else set(role)
        user_role = session.get("role", "user")
        if user_role not in allowed:
            flash("You are not allowed to access this page.", "error")
            return redirect(url_for("home"))

    # Logged in and allowed
    return None
