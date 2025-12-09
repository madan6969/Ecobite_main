# db_utils.py
"""
DB helper functions for EcoBite.

All DB access should go through:
    - get_cursor()
    - conn (global connection)
    - dict_rows()
    - compute_stats()

Uses environment variables so it works on:
- Local (.env)
- Render (Environment tab) with Railway MySQL
"""

import os
import mariadb
from dotenv import load_dotenv

# Load .env when running locally
load_dotenv()

# --------- DB CONFIG ---------
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")

# IMPORTANT:
# - LOCAL: set DB_PASSWORD in .env to your HeidiSQL password (you said: 6969)
# - RENDER: DB_PASSWORD is set in the Environment tab with your Railway password
DB_PASSWORD = os.getenv("DB_PASSWORD", "6969")   # fallback only for LOCAL dev

DB_NAME = os.getenv("DB_NAME", "ecobite")

# --------- CONNECTION HELPERS ---------

def get_db_connection():
    """Create and return a new MariaDB connection."""
    return mariadb.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )


# We *do* create a global connection – the app expects a global `conn`
# If credentials are wrong, you'll see an error right at startup.
conn = get_db_connection()


def get_cursor():
    """
    Return a cursor. If the connection died, try to reconnect once.
    """
    global conn
    try:
        return conn.cursor()
    except mariadb.Error:
        # Try reconnecting one time
        conn = get_db_connection()
        return conn.cursor()


# --------- SMALL UTILITIES ---------

def dict_rows(rows, description):
    """
    Convert list of tuples + cursor.description into list of dicts.
    Similar to DictCursor behavior.
    """
    if not rows:
        return []
    col_names = [col[0] for col in description]
    out = []
    for row in rows:
        d = {}
        for name, value in zip(col_names, row):
            d[name] = value
        out.append(d)
    return out


def compute_stats(user_id=None):
    """
    Compute simple stats either globally or for a specific user.
    This matches what your UI expects.
    """
    cur = get_cursor()
    stats = {}

    if user_id is None:
        # Global stats
        try:
            cur.execute(
                """
                SELECT COUNT(*) FROM posts
                WHERE status='active'
                  AND (expires_at IS NULL OR expires_at > NOW())
                """
            )
            stats["available_now"] = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM posts WHERE status IN ('claimed', 'completed')"
            )
            stats["successfully_shared"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM posts")
            stats["total_posts"] = cur.fetchone()[0]

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

    # Per-user stats
    try:
        cur.execute("SELECT COUNT(*) FROM posts WHERE user_id=?", (user_id,))
        stats["posts_created"] = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*) FROM posts
            WHERE user_id=? AND status IN ('claimed', 'completed')
            """,
            (user_id,),
        )
        stats["posts_shared"] = cur.fetchone()[0]

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

        cur.execute("SELECT COUNT(*) FROM claims WHERE claimer_id=?", (user_id,))
        stats["claims_made"] = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*) FROM claims
            WHERE claimer_id=? AND status='approved'
            """,
            (user_id,),
        )
        stats["claims_accepted"] = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*) FROM claims
            WHERE claimer_id=? AND status='rejected'
            """,
            (user_id,),
        )
        stats["claims_rejected"] = cur.fetchone()[0]

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
