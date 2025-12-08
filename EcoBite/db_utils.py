import os
from datetime import datetime, timedelta  # if you ever need these here
import mariadb

from flask import flash, has_request_context

# Optional: load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ------------------ Database config -------------------
DB_USER = os.getenv("DB_USER", "ecobite")
DB_PASS = os.getenv("DB_PASS", "2312093")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "ecobite")

print(f"📊 Database Config: Host={DB_HOST}, Port={DB_PORT}, User={DB_USER}, Database={DB_NAME}")

conn, cursor = None, None

try:
    conn = mariadb.connect(
        user=DB_USER, password=DB_PASS,
        host=DB_HOST, port=DB_PORT,
        database=DB_NAME
    )
    cursor = conn.cursor()
    print("✅ Connected to MariaDB!")
except mariadb.Error as e:
    error_msg = str(e)
    print(f"❌ Database connection failed: {e}")
    if "Unknown database" in error_msg:
        print(f"💡 Tip: The database '{DB_NAME}' might not exist.")
        print(f"   Create it with: CREATE DATABASE `{DB_NAME}`;")
        print(f"   Or connect without specifying database and create it.")
    elif "Access denied" in error_msg:
        print(f"💡 Tip: Check your credentials - User: {DB_USER}, Password: {DB_PASS}")
    else:
        print(f"💡 Check if MariaDB is running on {DB_HOST}:{DB_PORT}")

# ------------------ Helper functions -------------------

def get_cursor():
    """Get database cursor, creating connection if needed"""
    global conn, cursor
    if cursor is None or conn is None:
        try:
            conn = mariadb.connect(
                user=DB_USER, password=DB_PASS,
                host=DB_HOST, port=DB_PORT,
                database=DB_NAME
            )
            cursor = conn.cursor()
            print("✅ Connected to MariaDB!")
        except mariadb.Error as e:
            error_msg = str(e)
            print(f"❌ Database connection failed: {e}")

            # If database doesn't exist, try to create it
            if "Unknown database" in error_msg:
                try:
                    print(f"🔄 Attempting to create database '{DB_NAME}'...")
                    # Connect without database specified
                    temp_conn = mariadb.connect(
                        user=DB_USER, password=DB_PASS,
                        host=DB_HOST, port=DB_PORT
                    )
                    temp_cursor = temp_conn.cursor()
                    # Create database
                    temp_cursor.execute(
                        f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                    )
                    temp_conn.commit()
                    temp_cursor.close()
                    temp_conn.close()
                    print(f"✅ Database '{DB_NAME}' created successfully!")

                    # Now connect with the database
                    conn = mariadb.connect(
                        user=DB_USER, password=DB_PASS,
                        host=DB_HOST, port=DB_PORT,
                        database=DB_NAME
                    )
                    cursor = conn.cursor()
                    print("✅ Connected to MariaDB!")
                except mariadb.Error as create_error:
                    print(f"❌ Failed to create database: {create_error}")
                    if has_request_context():
                        flash("Database connection error. Please ensure MariaDB is running and the database exists.", "error")
                    return None
            else:
                if has_request_context():
                    flash("Database connection error. Please check your database configuration.", "error")
                return None
    return cursor


def dict_rows(rows, desc):
    cols = [d[0] for d in desc]
    return [dict(zip(cols, r)) for r in rows]


def co2_estimate(shared_count):
    return int(shared_count * 1.5)


def compute_stats(user_id=None):
    stats = {"available": 0, "shared": 0, "total": 0, "co2": 0}
    cur = get_cursor()
    if cur is None:
        return stats
    try:
        # available
        q = """
            SELECT COUNT(*) FROM posts
            WHERE status='active' AND (expires_at IS NULL OR expires_at > NOW())
        """
        cur.execute(q + (" AND user_id=?" if user_id else ""), (user_id,) if user_id else ())
        stats["available"] = cur.fetchone()[0]
        # shared
        cur.execute(
            "SELECT COUNT(*) FROM posts WHERE status='claimed'"
            + (" AND user_id=?" if user_id else ""),
            (user_id,) if user_id else ()
        )
        stats["shared"] = cur.fetchone()[0]
        # total
        cur.execute(
            "SELECT COUNT(*) FROM posts"
            + (" WHERE user_id=?" if user_id else ""),
            (user_id,) if user_id else ()
        )
        stats["total"] = cur.fetchone()[0]
        stats["co2"] = co2_estimate(stats["shared"])
    except Exception as e:
        print("❌ Stats error:", e)
    return stats
