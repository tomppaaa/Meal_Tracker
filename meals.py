import math

import db

MAX_MEAL_NAME_LENGTH = 50
MAX_MEAL_TYPE_LENGTH = 50


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
        raise ValueError(f"{label} must be a valid number greater than or equal to 0.") from error

    if number < 0 or (not integer and not math.isfinite(number)):
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
    row = db.query("SELECT * FROM meals WHERE id = ?", (meal_id,))
    return db.row_to_dict(row[0]) if row else None


def get_meals_by_user(user_id):
    """Return all meals belonging to a specific user."""
    rows = db.query(
        "SELECT * FROM meals WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    )
    return [db.row_to_dict(row) for row in rows]


def get_all_meals():
    """Return all meals as a list of dicts."""
    rows = db.query("SELECT * FROM meals ORDER BY created_at DESC")
    return [db.row_to_dict(row) for row in rows]


def search_meals(search_query, min_price, max_price, selected_diets, selected_meal_types):
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
            SELECT meal_id, ROUND(AVG(rating), 1) AS average_rating, COUNT(*) AS rating_count
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


__all__ = [
    "create_meal",
    "get_meal_by_id",
    "get_meals_by_user",
    "get_all_meals",
    "search_meals",
    "update_meal",
    "delete_meal",
]
