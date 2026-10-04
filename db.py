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
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    comment_columns = con.execute("PRAGMA table_info(meal_comments)").fetchall()
    existing_comment_columns = {row[1] for row in comment_columns}
    if "parent_comment_id" not in existing_comment_columns:
        con.execute("ALTER TABLE meal_comments ADD COLUMN parent_comment_id INTEGER REFERENCES meal_comments(id) ON DELETE CASCADE")
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
        SELECT id, meal_id, author, body, parent_comment_id, created_at
        FROM meal_comments
        WHERE meal_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (meal_id,),
    )


def get_meal_types():
    return query("SELECT id, name FROM meal_types ORDER BY id")


def add_meal_comment(meal_id, author, body, parent_comment_id=None):
    author = (author or "").strip() or "Anonyymi"
    body = (body or "").strip()

    if not body:
        raise ValueError("Comment cannot be empty.")
    if len(body) > MAX_COMMENT_LENGTH:
        raise ValueError("Comment cannot be longer than 1000 characters.")

    execute(
        "INSERT INTO meal_comments (meal_id, author, body, parent_comment_id) VALUES (?, ?, ?, ?)",
        (meal_id, author, body, parent_comment_id),
    )
    return last_insert_id()


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