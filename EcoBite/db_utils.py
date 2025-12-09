"""
DB helper functions for EcoBite.

All DB access should go through:
    - get_cursor()
    - conn (global connection)
    - dict_rows()
    - compute_stats()
so the rest of your code works unchanged.

Uses env vars so it works on Render + Railway + local (.env).
"""

import os
import mariadb
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "ecobite")
DB_PASSWORD = os.getenv("DB_PASSWORD", "ecobite")
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
    Like MySQL's DictCursor, but manual.
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
    This is not super optimized, but good enough for your project.
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
            # On any error, just return zeros so UI doesn't crash
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
        # If anything fails, don't break UI
        stats.setdefault("posts_created", 0)
        stats.setdefault("posts_shared", 0)
        stats.setdefault("weight_shared_kg", 0.0)
        stats.setdefault("claims_made", 0)
        stats.setdefault("claims_accepted", 0)
        stats.setdefault("claims_rejected", 0)
        stats.setdefault("join_date", None)

    return stats
