# db_utils.py
"""
Central database helper functions for EcoBite.

This file is written to be BACKWARDS COMPATIBLE with the rest of your
project, so these imports still work everywhere:

    from db_utils import get_cursor, dict_rows, compute_stats, conn

as well as:

    from db_utils import get_db_connection

It uses environment variables so it works both on Railway/Render and locally.
"""

import os
import mariadb
from dotenv import load_dotenv

# Load .env in local dev; on Render/Railway the env vars are already set
load_dotenv()

# --- Connection settings (from env) -----------------------------------------

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))

# your local defaults (same as inspect_db.py)
DB_USER = os.getenv("DB_USER", "ecobite")

DB_PASSWORD = (
    os.getenv("DB_PASSWORD")
    or os.getenv("DB_PASS")
    or "2312093"
)

DB_NAME = os.getenv("DB_NAME", "ecobite")



# internal global connection (used by web app)
_conn = None


# --- Low-level connection helpers -------------------------------------------

def get_db_connection():
    """
    Create and return a NEW MariaDB connection.

    Used by scripts like migrate_db.py.
    """
    return mariadb.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )


def get_conn():
    """
    Return a shared connection object for the web app.

    Recreates the connection if it was never created or if ping() fails.
    """
    global _conn
    if _conn is None:
        _conn = get_db_connection()
        return _conn

    try:
        # ping() will raise on a dead connection
        _conn.ping()
    except mariadb.Error:
        _conn = get_db_connection()
    return _conn


# Name expected by existing code: imported as `conn`
conn = get_conn()


def get_cursor(dictionary: bool = False):
    """
    Return a cursor from the shared connection.

    dictionary=True -> rows are dicts; otherwise rows are tuples.
    """
    return get_conn().cursor(dictionary=dictionary)


# --- Row / dict helpers ------------------------------------------------------

def dict_rows(rows, description=None):
    """
    Convert DB-API rows + cursor.description into a list of dicts.

    * If rows are already dicts (from dictionary cursor), they are returned
      unchanged.
    * Otherwise we use cursor.description to build dicts.

    Existing code calls: dict_rows(cur.fetchall(), cur.description)
    """
    if not rows:
        return []

    first = rows[0]
    if isinstance(first, dict):
        # already dict-style from dictionary cursor
        return rows

    if description is None:
        raise ValueError("cursor.description is required when rows are tuples")

    columns = [col[0] for col in description]
    out = []
    for row in rows:
        d = {columns[i]: row[i] for i in range(len(columns))}
        out.append(d)
    return out


# --- Simple query helpers (optional, but useful) -----------------------------

def query_one(sql, params=None, *, dict_result: bool = True):
    """Run a SELECT that returns a single row or None."""
    cur = get_cursor(dictionary=dict_result)
    cur.execute(sql, params or ())
    return cur.fetchone()


def query_all(sql, params=None, *, dict_result: bool = True):
    """Run a SELECT that returns a list of rows."""
    cur = get_cursor(dictionary=dict_result)
    cur.execute(sql, params or ())
    return cur.fetchall()


def execute(sql, params=None):
    """
    Run an INSERT / UPDATE / DELETE.
    Returns the last inserted id (if any).
    """
    c = get_conn()
    cur = c.cursor()
    cur.execute(sql, params or ())
    c.commit()
    return cur.lastrowid


# --- Stats helper used on home/profile pages ---------------------------------

def compute_stats(user_id=None):
    """
    Compute simple stats for the dashboard.

    - If user_id is None -> global stats.
    - If user_id is given -> stats for that user only.

    Returns a dict (missing keys default to 0).
    """
    stats = {
        "total_posts": 0,
        "available_now": 0,
        "shared": 0,
        "my_posts": 0,
        "my_shared": 0,
    }

    cur = get_cursor()
    try:
        if user_id is None:
            # Global stats
            cur.execute("SELECT COUNT(*) FROM posts")
            stats["total_posts"] = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*)
                FROM posts
                WHERE status='active'
                  AND (expires_at IS NULL OR expires_at > NOW())
            """)
            stats["available_now"] = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*)
                FROM posts
                WHERE status IN ('claimed', 'completed')
            """)
            stats["shared"] = cur.fetchone()[0]
        else:
            # Per-user stats
            cur.execute("SELECT COUNT(*) FROM posts WHERE user_id=?", (user_id,))
            stats["my_posts"] = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*)
                FROM posts
                WHERE user_id=? AND status IN ('claimed', 'completed')
            """, (user_id,))
            stats["my_shared"] = cur.fetchone()[0]

    except Exception as e:
        # Don't crash the app just because stats failed
        print(f"❌ compute_stats error: {e}")

    return stats
