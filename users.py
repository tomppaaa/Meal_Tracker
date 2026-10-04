import db
from werkzeug.security import check_password_hash, generate_password_hash

MAX_USERNAME_LENGTH = 50
MAX_PASSWORD_LENGTH = 128


def create_user(username, password):
    """Create a new user and return the new user id."""
    username = (username or "").strip()
    if not username:
        raise ValueError("Username cannot be empty.")
    if len(username) > MAX_USERNAME_LENGTH:
        raise ValueError("Username cannot be longer than 50 characters.")
    if not password:
        raise ValueError("Password cannot be empty.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError("Password cannot be longer than 128 characters.")

    existing = get_user_by_username(username)
    if existing:
        raise ValueError("Username already exists.")

    password_hash = generate_password_hash(password)
    db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )
    return db.last_insert_id()


def get_user_by_id(user_id):
    """Return a user dict by id or None if not found."""
    row = db.query(
        "SELECT id, username, password_hash, created_at FROM users WHERE id = ?",
        (user_id,),
    )
    return db.row_to_dict(row[0]) if row else None


def get_user_by_username(username):
    """Return a user dict by username or None if not found."""
    row = db.query(
        "SELECT id, username, password_hash, created_at FROM users WHERE username = ?",
        (username,),
    )
    return db.row_to_dict(row[0]) if row else None


def get_all_users():
    """Return all users as a list of dicts."""
    rows = db.query(
        "SELECT id, username, created_at FROM users ORDER BY created_at DESC"
    )
    return [db.row_to_dict(row) for row in rows]


def verify_user(username, password):
    """Check username/password pair and return the user dict if valid."""
    if len(username or "") > MAX_USERNAME_LENGTH or len(password or "") > MAX_PASSWORD_LENGTH:
        return None
    user = get_user_by_username(username)
    if not user:
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return user


def update_username(user_id, new_username):
    """Update username for a user."""
    new_username = (new_username or "").strip()
    if not new_username:
        raise ValueError("Username cannot be empty.")
    if len(new_username) > MAX_USERNAME_LENGTH:
        raise ValueError("Username cannot be longer than 50 characters.")

    existing = get_user_by_username(new_username)
    if existing and existing["id"] != user_id:
        raise ValueError("Username already exists.")

    db.execute(
        "UPDATE users SET username = ? WHERE id = ?",
        (new_username, user_id),
    )
    return True


def update_password(user_id, new_password):
    """Update password hash for a user."""
    if not new_password:
        raise ValueError("Password cannot be empty.")
    if len(new_password) > MAX_PASSWORD_LENGTH:
        raise ValueError("Password cannot be longer than 128 characters.")

    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), user_id),
    )
    return True


def delete_user(user_id):
    """Delete a user record by id."""
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return True


__all__ = [
    "create_user",
    "get_user_by_id",
    "get_user_by_username",
    "get_all_users",
    "verify_user",
    "update_username",
    "update_password",
    "delete_user",
]
