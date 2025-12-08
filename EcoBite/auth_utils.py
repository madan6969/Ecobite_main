from flask import session

# Same roles as before
ALLOWED_ROLES = {"user", "business", "admin"}

def require_login():
    """
    Your current 'fake' login logic: if not logged in,
    set a default demo user.
    """
    # If you ever want real login, just restore the old version here.
    if "user_id" not in session:
        session["user_id"] = 1
        session["email"] = "student@campus.edu"
        session["role"] = "user"
    return None
