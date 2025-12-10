"""
DB helper functions for EcoBite.

All DB access should go through:
    - get_cursor()
    - conn (global connection)
    - dict_rows()
    - compute_stats()
"""

import os
import mariadb
from dotenv import load_dotenv

load_dotenv()

# -------- DB CONFIG --------
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))

DB_USER = os.getenv("DB_USER", "root")

# IMPORTANT: use your own password here as fallback, NOT your friend's
DB_PASSWORD = (
    os.getenv("DB_PASSWORD")
    or os.getenv("DB_PASS")
    or "6969"          # <-- your LOCAL MariaDB password
)

DB_NAME = os.getenv("DB_NAME", "ecobite")

_conn = None


def get_db_connection():
    """Create a new MariaDB connection."""
    return mariadb.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )


def get_conn():
    """Return a reusable global connection."""
    global _conn
    if _conn is None:
        _conn = get_db_connection()
    return _conn


# Global connection used by the rest of the app
conn = get_conn()


def get_cursor():
    """
    Return a cursor. If the connection died, reconnect automatically.
    """
    global conn
    try:
        cur = conn.cursor()
        return cur
    except mariadb.Error:
        # Reconnect
        conn = get_db_connection()
        return conn.cursor()


def dict_rows(rows, description):
    """
    Convert list of tuples + cursor.description into list of dicts.

    Also decode any bytes/bytearray values to UTF-8 strings so that
    jsonify() won't crash with "Object of type bytes is not JSON serializable".
    """
    if not rows:
        return []

    col_names = [col[0] for col in description]
    out = []

    for row in rows:
        d = {}
        for name, value in zip(col_names, row):
            if isinstance(value, (bytes, bytearray)):
                try:
                    value = value.decode("utf-8")
                except Exception:
                    value = value.decode("latin1", errors="ignore")
            d[name] = value
        out.append(d)

    return out


def compute_stats(user_id=None):
    """
    Compute simple stats either globally or for a specific user.
    Works with posts table that has:
      - status
      - estimated_weight_kg
      - user_id
    """
    cur = get_cursor()
    stats = {}

    if cur is None:
        # if DB totally broken, just return zeros
        defaults = {
            "available_now": 0,
            "successfully_shared": 0,
            "total_posts": 0,
            "food_waste_prevented_kg": 0.0,
            "posts_created": 0,
            "posts_shared": 0,
            "weight_shared_kg": 0.0,
            "claims_made": 0,
            "claims_accepted": 0,
            "claims_rejected": 0,
            "join_date": None,
        }
        return defaults if user_id else {
            k: defaults[k] for k in
            ["available_now", "successfully_shared", "total_posts", "food_waste_prevented_kg"]
        }

    # ------- GLOBAL STATS -------
    if user_id is None:
        try:
            # Available now
            cur.execute(
                """
                SELECT COUNT(*) FROM posts
                WHERE status='active'
                  AND (expires_at IS NULL OR expires_at > NOW())
                """
            )
            stats["available_now"] = cur.fetchone()[0]

            # Successfully shared
            cur.execute(
                "SELECT COUNT(*) FROM posts WHERE status IN ('claimed', 'completed')"
            )
            stats["successfully_shared"] = cur.fetchone()[0]

            # Total posts
            cur.execute("SELECT COUNT(*) FROM posts")
            stats["total_posts"] = cur.fetchone()[0]

            # Food waste prevented
            cur.execute(
                """
                SELECT SUM(estimated_weight_kg)
                FROM posts
                WHERE status IN ('claimed', 'completed')
                """
            )
            weight = cur.fetchone()[0]
            stats["food_waste_prevented_kg"] = float(weight) if weight else 0.0
        except Exception:
            stats.setdefault("available_now", 0)
            stats.setdefault("successfully_shared", 0)
            stats.setdefault("total_posts", 0)
            stats.setdefault("food_waste_prevented_kg", 0.0)
        return stats

    # ------- PER-USER STATS -------
    try:
        # Posts created
        cur.execute("SELECT COUNT(*) FROM posts WHERE user_id=?", (user_id,))
        stats["posts_created"] = cur.fetchone()[0]

        # Posts shared
        cur.execute(
            """
            SELECT COUNT(*) FROM posts
            WHERE user_id=? AND status IN ('claimed', 'completed')
            """,
            (user_id,),
        )
        stats["posts_shared"] = cur.fetchone()[0]

        # Weight shared
        cur.execute(
            """
            SELECT SUM(estimated_weight_kg)
            FROM posts
            WHERE user_id=? AND status IN ('claimed', 'completed')
            """,
            (user_id,),
        )
        weight = cur.fetchone()[0]
        stats["weight_shared_kg"] = float(weight) if weight else 0.0

        # Claims made
        cur.execute("SELECT COUNT(*) FROM claims WHERE claimer_id=?", (user_id,))
        stats["claims_made"] = cur.fetchone()[0]

        # Claims accepted
        cur.execute(
            """
            SELECT COUNT(*) FROM claims
            WHERE claimer_id=? AND status='approved'
            """,
            (user_id,),
        )
        stats["claims_accepted"] = cur.fetchone()[0]

        # Claims rejected
        cur.execute(
            """
            SELECT COUNT(*) FROM claims
            WHERE claimer_id=? AND status='rejected'
            """,
            (user_id,),
        )
        stats["claims_rejected"] = cur.fetchone()[0]

        # Join date
        cur.execute("SELECT created_at FROM users WHERE id=?", (user_id,))
        row = cur.fetchone()
        stats["join_date"] = row[0] if row else None
    except Exception:
        stats.setdefault("posts_created", 0)
        stats.setdefault("posts_shared", 0)
        stats.setdefault("weight_shared_kg", 0.0)
        stats.setdefault("claims_made", 0)
        stats.setdefault("claims_accepted", 0)
        stats.setdefault("claims_rejected", 0)
        stats.setdefault("join_date", None)

    return stats
