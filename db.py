import sqlite3
from pathlib import Path
from flask import g

MAX_COMMENT_LENGTH = 1000


def get_connection():
    con = sqlite3.connect("database.db")
    con.execute("PRAGMA foreign_keys = ON")
    con.row_factory = sqlite3.Row
    return con


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def ensure_meals_schema():
    con = get_connection()
    init_sql = Path(__file__).with_name("init.sql").read_text(encoding="utf-8")
    con.executescript(init_sql)
    columns = con.execute("PRAGMA table_info(meals)").fetchall()
    existing = {row[1] for row in columns}
    if "diet_tags" not in existing:
        con.execute("ALTER TABLE meals ADD COLUMN diet_tags TEXT DEFAULT ''")

    con.execute("""
        CREATE TABLE IF NOT EXISTS meal_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meal_id INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
            author TEXT NOT NULL,
            body TEXT NOT NULL CHECK(length(trim(body)) > 0),
            parent_comment_id INTEGER REFERENCES meal_comments(id) ON DELETE CASCADE,
            commenter_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    comment_columns = con.execute("PRAGMA table_info(meal_comments)").fetchall()
    existing_comment_columns = {row[1] for row in comment_columns}
    if "parent_comment_id" not in existing_comment_columns:
        con.execute("ALTER TABLE meal_comments ADD COLUMN parent_comment_id INTEGER REFERENCES meal_comments(id) ON DELETE CASCADE")
    if "commenter_user_id" not in existing_comment_columns:
        con.execute("ALTER TABLE meal_comments ADD COLUMN commenter_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        con.execute("""
            UPDATE meal_comments
            SET commenter_user_id = (
                SELECT users.id FROM users WHERE users.username = meal_comments.author
            )
            WHERE commenter_user_id IS NULL
        """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS meal_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meal_id INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(meal_id, user_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            meal_id INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
            comment_id INTEGER NOT NULL REFERENCES meal_comments(id) ON DELETE CASCADE,
            notification_type TEXT NOT NULL CHECK(notification_type IN ('new_comment', 'comment_reply')),
            is_read INTEGER NOT NULL DEFAULT 0 CHECK(is_read IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.commit()
    con.close()


def execute(sql, params=[]):
    con = get_connection()
    result = con.execute(sql, params)
    con.commit()
    g.last_insert_id = result.lastrowid
    con.close()


def last_insert_id():
    return g.last_insert_id


def query(sql, params=[]):
    con = get_connection()
    result = con.execute(sql, params).fetchall()
    con.close()
    return result

def get_meal_comments(meal_id):
    return query(
        """
        SELECT id, meal_id, author, body, parent_comment_id, commenter_user_id, created_at
        FROM meal_comments
        WHERE meal_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (meal_id,),
    )


def get_meal_types():
    return query("SELECT id, name FROM meal_types ORDER BY id")


def add_meal_comment(meal_id, author, body, parent_comment_id=None, commenter_user_id=None):
    author = (author or "").strip() or "Anonyymi"
    body = (body or "").strip()

    if not body:
        raise ValueError("Comment cannot be empty.")
    if len(body) > MAX_COMMENT_LENGTH:
        raise ValueError("Comment cannot be longer than 1000 characters.")

    execute(
        """
        INSERT INTO meal_comments (meal_id, author, body, parent_comment_id, commenter_user_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (meal_id, author, body, parent_comment_id, commenter_user_id),
    )
    return last_insert_id()


def create_notification(user_id, actor_user_id, meal_id, comment_id, notification_type):
    if user_id == actor_user_id:
        return
    if notification_type not in {"new_comment", "comment_reply"}:
        raise ValueError("Invalid notification type.")
    execute(
        """
        INSERT INTO notifications (user_id, actor_user_id, meal_id, comment_id, notification_type)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, actor_user_id, meal_id, comment_id, notification_type),
    )


def get_notifications(user_id):
    return query(
        """
        SELECT n.id, n.user_id, n.actor_user_id, n.meal_id, n.comment_id,
               n.notification_type, n.is_read, n.created_at, m.name AS meal_name,
               actor.username AS actor_username
        FROM notifications n
        JOIN meals m ON m.id = n.meal_id
        LEFT JOIN users actor ON actor.id = n.actor_user_id
        WHERE n.user_id = ?
        ORDER BY n.created_at DESC, n.id DESC
        """,
        (user_id,),
    )


def get_unread_notification_count(user_id):
    rows = query(
        "SELECT COUNT(*) AS count FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,),
    )
    return rows[0]["count"]


def get_notification_target(notification_id, user_id):
    rows = query(
        """
        SELECT meal_id, comment_id
        FROM notifications
        WHERE id = ? AND user_id = ?
        """,
        (notification_id, user_id),
    )
    return row_to_dict(rows[0]) if rows else None


def mark_notification_read(notification_id, user_id):
    execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
        (notification_id, user_id),
    )


def get_meal_rating_summary(meal_id, user_id=None):
    summary = query(
        """
        SELECT ROUND(AVG(rating), 1) AS average_rating, COUNT(*) AS rating_count
        FROM meal_ratings
        WHERE meal_id = ?
        """,
        (meal_id,),
    )[0]
    user_rating = None
    if user_id:
        rows = query(
            "SELECT rating FROM meal_ratings WHERE meal_id = ? AND user_id = ?",
            (meal_id, user_id),
        )
        user_rating = rows[0]["rating"] if rows else None

    return {
        "average": summary["average_rating"] or 0,
        "count": summary["rating_count"],
        "user_rating": user_rating,
    }


def save_meal_rating(meal_id, user_id, rating):
    if rating not in range(1, 6):
        raise ValueError("Rating must be between 1 and 5.")

    execute(
        """
        INSERT INTO meal_ratings (meal_id, user_id, rating)
        VALUES (?, ?, ?)
        ON CONFLICT(meal_id, user_id) DO UPDATE SET
            rating = excluded.rating,
            created_at = CURRENT_TIMESTAMP
        """,
        (meal_id, user_id, rating),
    )