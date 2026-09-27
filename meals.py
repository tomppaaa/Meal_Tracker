import db

MAX_MEAL_NAME_LENGTH = 50


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

    name = (name or "").strip()
    meal_type = (meal_type or "").strip()
    if not name:
        raise ValueError("Meal name cannot be empty.")
    if len(name) > MAX_MEAL_NAME_LENGTH:
        raise ValueError("Meal name cannot be longer than 50 characters.")
    if not meal_type:
        raise ValueError("Meal type cannot be empty.")

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
            int(calories or 0),
            float(protein or 0.0),
            float(carbs or 0.0),
            float(fat or 0.0),
            float(price or 0.0),
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
        if key in {"name", "meal_type"}:
            value = (value or "").strip()
        if key == "name" and len(value) > MAX_MEAL_NAME_LENGTH:
            raise ValueError("Meal name cannot be longer than 50 characters.")
        if key in {"calories"}:
            value = int(value or 0)
        if key in {"protein", "carbs", "fat", "price"}:
            value = float(value or 0.0)
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
    "update_meal",
    "delete_meal",
]
