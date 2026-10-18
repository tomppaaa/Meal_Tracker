import math

import db

MAX_MEAL_NAME_LENGTH = 50
MAX_MEAL_TYPE_LENGTH = 50
MAX_COMMENT_LENGTH = 1000


def _normalize_meal_name(name):
    name = name or ""
    if not name.strip():
        raise ValueError("Meal name cannot be empty.")
    if name[:1].isspace():
        raise ValueError("Meal name cannot start with whitespace.")

    name = name.strip()
    if len(name) > MAX_MEAL_NAME_LENGTH:
        raise ValueError("Meal name cannot be longer than 50 characters.")
    return name


def _validate_meal_number(field, value, integer=False):
    label = field.capitalize()
    if value in (None, ""):
        value = 0

    try:
        number = int(value) if integer else float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(
            f"{label} must be a valid number greater than or equal to 0."
        ) from error

    if (
        number < 0
        or (integer and number > db.MAX_SQLITE_INTEGER)
        or (not integer and not math.isfinite(number))
    ):
        raise ValueError(f"{label} must be a valid number greater than or equal to 0.")
    return number


def create_meal(
    user_id,
    name,
    meal_type,
    calories=0,
    protein=0.0,
    carbs=0.0,
    fat=0.0,
    price=0.0,
    recipe_notes=None,
    diet_tags="",
):
    """Create a new meal record and return the inserted meal id."""
    if not user_id:
        raise ValueError("User id is required.")

    name = _normalize_meal_name(name)
    meal_type = (meal_type or "").strip()
    if not meal_type:
        raise ValueError("Meal type cannot be empty.")
    if len(meal_type) > MAX_MEAL_TYPE_LENGTH:
        raise ValueError("Meal type cannot be longer than 50 characters.")

    calories = _validate_meal_number("calories", calories, integer=True)
    protein = _validate_meal_number("protein", protein)
    carbs = _validate_meal_number("carbs", carbs)
    fat = _validate_meal_number("fat", fat)
    price = _validate_meal_number("price", price)

    db.execute(
        """
        INSERT INTO meals (
            user_id, name, meal_type, calories, protein, carbs, fat, price, recipe_notes, diet_tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            name,
            meal_type,
            calories,
            protein,
            carbs,
            fat,
            price,
            recipe_notes,
            diet_tags,
        ),
    )
    return db.last_insert_id()


def get_meal_by_id(meal_id):
    """Return a meal dict by id, or None if not found."""
    row = db.query(
        """
        SELECT
            id,
            user_id,
            name,
            meal_type,
            calories,
            protein,
            carbs,
            fat,
            price,
            recipe_notes,
            diet_tags,
            created_at
        FROM meals
        WHERE id = ?
        """,
        (meal_id,),
    )
    return db.row_to_dict(row[0]) if row else None


def get_meals_by_user(user_id):
    """Return all meals belonging to a specific user."""
    rows = db.query(
        """
        SELECT
            id,
            user_id,
            name,
            meal_type,
            calories,
            protein,
            carbs,
            fat,
            price,
            recipe_notes,
            diet_tags,
            created_at
        FROM meals
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,),
    )
    return [db.row_to_dict(row) for row in rows]


def get_all_meals():
    """Return all meals as a list of dicts."""
    rows = db.query(
        """
        SELECT
            id,
            user_id,
            name,
            meal_type,
            calories,
            protein,
            carbs,
            fat,
            price,
            recipe_notes,
            diet_tags,
            created_at
        FROM meals
        ORDER BY created_at DESC
        """
    )
    return [db.row_to_dict(row) for row in rows]


def search_meals(
    search_query, min_price, max_price, selected_diets, selected_meal_types
):
    """Search meals using the selected text, price, diet, and meal-type filters."""
    sql = """
        SELECT
            m.id,
            m.user_id,
            m.name,
            m.meal_type,
            m.calories AS total_calories,
            m.protein AS total_protein,
            m.carbs AS total_carbs,
            m.fat AS total_fat,
            m.price,
            m.created_at,
            u.username,
            m.diet_tags,
            COALESCE(rating_summary.average_rating, 0) AS rating_average,
            COALESCE(rating_summary.rating_count, 0) AS rating_count
        FROM meals m
        LEFT JOIN users u ON u.id = m.user_id
        LEFT JOIN (
            SELECT
                meal_id,
                ROUND(AVG(rating), 1) AS average_rating,
                COUNT(*) AS rating_count
            FROM meal_ratings
            GROUP BY meal_id
        ) rating_summary ON rating_summary.meal_id = m.id
    """
    params = []
    conditions = []

    if search_query:
        search_value = f"%{search_query}%"
        conditions.append(
            "(LOWER(m.name) LIKE LOWER(?) OR LOWER(m.meal_type) LIKE LOWER(?) "
            "OR CAST(m.price AS TEXT) LIKE ?)"
        )
        params.extend([search_value, search_value, search_value])

    if min_price is not None:
        conditions.append("CAST(m.price AS REAL) >= ?")
        params.append(min_price)

    if max_price is not None:
        conditions.append("CAST(m.price AS REAL) <= ?")
        params.append(max_price)

    if selected_diets:
        diet_filters = []
        for diet_id in selected_diets:
            diet_filters.append("(',' || COALESCE(m.diet_tags, '') || ',') LIKE ?")
            params.append(f"%,{diet_id},%")
        conditions.append("(" + " OR ".join(diet_filters) + ")")

    if selected_meal_types:
        meal_type_filters = []
        for meal_type in selected_meal_types:
            meal_type_filters.append("LOWER(m.meal_type) = LOWER(?)")
            params.append(meal_type)
        conditions.append("(" + " OR ".join(meal_type_filters) + ")")

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY m.created_at DESC"
    rows = db.query(sql, params)
    return [db.row_to_dict(row) for row in rows]


def update_meal(meal_id, **fields):
    """Update meal fields with keyword arguments."""
    allowed_fields = {
        "name",
        "meal_type",
        "calories",
        "protein",
        "carbs",
        "fat",
        "price",
        "recipe_notes",
        "diet_tags",
    }

    updates = []
    values = []

    for key, value in fields.items():
        if key not in allowed_fields:
            continue
        if key == "name":
            value = _normalize_meal_name(value)
        elif key == "meal_type":
            value = (value or "").strip()
            if not value:
                raise ValueError("Meal type cannot be empty.")
            if len(value) > MAX_MEAL_TYPE_LENGTH:
                raise ValueError("Meal type cannot be longer than 50 characters.")
        if key in {"calories", "protein", "carbs", "fat", "price"}:
            value = _validate_meal_number(key, value, integer=key == "calories")
        updates.append(f"{key} = ?")
        values.append(value)

    if not updates:
        return False

    values.append(meal_id)
    db.execute(
        f"UPDATE meals SET {', '.join(updates)} WHERE id = ?",
        values,
    )
    return True


def delete_meal(meal_id):
    """Delete an meal by id."""
    db.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
    return True


def get_meal_comments(meal_id):
    return db.query(
        """
        SELECT
            id,
            meal_id,
            author,
            body,
            parent_comment_id,
            commenter_user_id,
            created_at
        FROM meal_comments
        WHERE meal_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (meal_id,),
    )


def get_meal_types():
    return db.query("SELECT id, name FROM meal_types ORDER BY id")


def get_diets():
    return db.query("SELECT id, name FROM diets ORDER BY id")


def get_meal_comment_target(comment_id, meal_id):
    rows = db.query(
        """
        SELECT id, commenter_user_id
        FROM meal_comments
        WHERE id = ? AND meal_id = ?
        """,
        (comment_id, meal_id),
    )
    return db.row_to_dict(rows[0]) if rows else None


def add_meal_comment(
    meal_id, author, body, parent_comment_id=None, commenter_user_id=None
):
    author = (author or "").strip() or "Anonymous"
    body = (body or "").strip()

    if not body:
        raise ValueError("Comment cannot be empty.")
    if len(body) > MAX_COMMENT_LENGTH:
        raise ValueError("Comment cannot be longer than 1000 characters.")

    db.execute(
        """
        INSERT INTO meal_comments (meal_id, author, body, parent_comment_id, commenter_user_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (meal_id, author, body, parent_comment_id, commenter_user_id),
    )
    return db.last_insert_id()


def create_notification(user_id, actor_user_id, meal_id, comment_id, notification_type):
    if user_id == actor_user_id:
        return
    if notification_type not in {"new_comment", "comment_reply"}:
        raise ValueError("Invalid notification type.")
    db.execute(
        """
        INSERT INTO notifications (user_id, actor_user_id, meal_id, comment_id, notification_type)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, actor_user_id, meal_id, comment_id, notification_type),
    )


def get_notifications(user_id):
    return db.query(
        """
        SELECT
            n.id,
            n.user_id,
            n.actor_user_id,
            n.meal_id,
            n.comment_id,
            n.notification_type,
            n.is_read,
            n.created_at,
            m.name AS meal_name,
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
    rows = db.query(
        """
        SELECT COUNT(*) AS count
        FROM notifications
        WHERE user_id = ? AND is_read = 0
        """,
        (user_id,),
    )
    return rows[0]["count"]


def get_notification_target(notification_id, user_id):
    rows = db.query(
        """
        SELECT meal_id, comment_id
        FROM notifications
        WHERE id = ? AND user_id = ?
        """,
        (notification_id, user_id),
    )
    return db.row_to_dict(rows[0]) if rows else None


def mark_notification_read(notification_id, user_id):
    db.execute(
        """
        UPDATE notifications
        SET is_read = 1
        WHERE id = ? AND user_id = ?
        """,
        (notification_id, user_id),
    )


def get_meal_rating_summary(meal_id, user_id=None):
    summary = db.query(
        """
        SELECT ROUND(AVG(rating), 1) AS average_rating, COUNT(*) AS rating_count
        FROM meal_ratings
        WHERE meal_id = ?
        """,
        (meal_id,),
    )[0]
    user_rating = None
    if user_id:
        rows = db.query(
            """
            SELECT rating
            FROM meal_ratings
            WHERE meal_id = ? AND user_id = ?
            """,
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

    db.execute(
        """
        INSERT INTO meal_ratings (meal_id, user_id, rating)
        VALUES (?, ?, ?)
        ON CONFLICT(meal_id, user_id) DO UPDATE SET
            rating = excluded.rating,
            created_at = CURRENT_TIMESTAMP
        """,
        (meal_id, user_id, rating),
    )


__all__ = [
    "create_meal",
    "get_meal_by_id",
    "get_meals_by_user",
    "get_all_meals",
    "search_meals",
    "update_meal",
    "delete_meal",
    "get_meal_comments",
    "get_meal_types",
    "get_diets",
    "get_meal_comment_target",
    "add_meal_comment",
    "create_notification",
    "get_notifications",
    "get_unread_notification_count",
    "get_notification_target",
    "mark_notification_read",
    "get_meal_rating_summary",
    "save_meal_rating",
]
