import hmac
import math
import secrets

from flask import Flask, request, redirect, session
from flask import render_template
import sqlite3, db, config, users, meals

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

db.ensure_meals_schema()

MAX_TEXT_INPUT_LENGTH = 10000
MAX_SEARCH_QUERY_LENGTH = 1000
MAX_MESSAGE_LENGTH = 1000


def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


@app.context_processor
def inject_csrf_token():
    user_id = session.get("user_id")
    unread_notifications = db.get_unread_notification_count(user_id) if user_id else 0
    return {
        "csrf_token": get_csrf_token(),
        "unread_notification_count": unread_notifications,
    }


@app.before_request
def protect_from_csrf():
    if request.method != "POST":
        return None

    submitted_token = request.form.get("csrf_token", "")
    session_token = session.get("csrf_token", "")
    if not session_token or not submitted_token or not hmac.compare_digest(submitted_token, session_token):
        return "Invalid CSRF token", 403
    return None


@app.before_request
def limit_input_lengths():
    for values in (request.args, request.form):
        if any(
            len(value) > MAX_TEXT_INPUT_LENGTH
            for value_list in values.listvalues()
            for value in value_list
        ):
            return "Input values cannot be longer than 10000 characters.", 400
    return None


def get_diets():
    return db.query("SELECT id, name FROM diets ORDER BY id")


def parse_price_filter(value):
    if not value:
        return None
    try:
        price = float(value)
    except ValueError as error:
        raise ValueError("Price filters must be valid numbers greater than or equal to 0.") from error
    if not math.isfinite(price) or price < 0:
        raise ValueError("Price filters must be valid numbers greater than or equal to 0.")
    return price


def build_meal_search_query(search_query, min_price_value, max_price_value, selected_diets, selected_meal_types):
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
        conditions.append("(LOWER(m.name) LIKE LOWER(?) OR LOWER(m.meal_type) LIKE LOWER(?) OR CAST(m.price AS TEXT) LIKE ?)")
        params.extend([search_value, search_value, search_value])

    if min_price_value is not None:
        conditions.append("CAST(m.price AS REAL) >= ?")
        params.append(min_price_value)

    if max_price_value is not None:
        conditions.append("CAST(m.price AS REAL) <= ?")
        params.append(max_price_value)

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
    return sql, params


def render_form_with_errors(template_name, errors=None, **context):
    return render_template(template_name, errors=errors or [], **context)


def validate_required_fields(payload, rules):
    errors = []
    for field_name, message in rules.items():
        value = payload.get(field_name, "")
        if isinstance(value, str):
            value = value.strip()
        if not value:
            errors.append(message)
    return errors


def build_profile_view(user_id, user=None):
    user = user or users.get_user_by_id(user_id)
    meal_count = len(meals.get_meals_by_user(user_id))
    total_calories = sum((meal.get("calories") or 0) for meal in meals.get_meals_by_user(user_id))
    total_price = sum((meal.get("price") or 0) for meal in meals.get_meals_by_user(user_id))
    return {
        "user": user,
        "meal_count": meal_count,
        "total_calories": total_calories,
        "total_price": total_price,
    }


def build_meal_statistics(user_id):
    user_meals = meals.get_meals_by_user(user_id)
    diet_names = {str(diet["id"]): diet["name"] for diet in get_diets()}

    def summarize(meal_list):
        count = len(meal_list)
        return {
            "count": count,
            "calories": sum((meal.get("calories") or 0) for meal in meal_list),
            "protein": sum((meal.get("protein") or 0) for meal in meal_list),
            "carbs": sum((meal.get("carbs") or 0) for meal in meal_list),
            "fat": sum((meal.get("fat") or 0) for meal in meal_list),
            "price": sum((meal.get("price") or 0) for meal in meal_list),
            "average_calories": (sum((meal.get("calories") or 0) for meal in meal_list) / count) if count else 0,
        }

    grouped_by_type = {}
    grouped_by_diet = {}
    for meal in user_meals:
        grouped_by_type.setdefault(meal["meal_type"], []).append(meal)
        for diet_id in (meal.get("diet_tags") or "").split(","):
            diet_name = diet_names.get(diet_id.strip())
            if diet_name:
                grouped_by_diet.setdefault(diet_name, []).append(meal)

    return {
        "overall": summarize(user_meals),
        "by_type": [(name, summarize(group)) for name, group in sorted(grouped_by_type.items())],
        "by_diet": [(name, summarize(group)) for name, group in sorted(grouped_by_diet.items())],
    }


@app.route("/register")
def register():
    return render_template("register.html", errors=[], username="")

@app.route("/create", methods=["POST"])
def create():
    username = request.form.get("username", "").strip()
    password1 = request.form.get("password1", "")
    password2 = request.form.get("password2", "")
    errors = validate_required_fields(
        {"username": username, "password1": password1},
        {
            "username": "Username cannot be empty.",
            "password1": "Password cannot be empty.",
        },
    )

    if password1 != password2:
        errors.append("Passwords do not match.")
    if len(password1) > users.MAX_PASSWORD_LENGTH:
        errors.append("Password cannot be longer than 128 characters.")

    if errors:
        return render_form_with_errors("register.html", errors=errors, username=username)

    try:
        user_id = users.create_user(username, password1)
    except ValueError as error:
        return render_form_with_errors("register.html", errors=[str(error)], username=username)

    session["user_id"] = user_id
    session["user_name"] = username
    session["csrf_token"] = secrets.token_urlsafe(32)
    return redirect("/")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        errors = validate_required_fields(
            {"username": username, "password": password},
            {
                "username": "Username cannot be empty.",
                "password": "Password cannot be empty.",
            },
        )
        if len(password) > users.MAX_PASSWORD_LENGTH:
            errors.append("Invalid username or password.")

        if errors:
            return render_form_with_errors("login.html", errors=errors, username=username)

        user = users.verify_user(username, password)
        if not user:
            return render_form_with_errors("login.html", errors=["Invalid username or password."], username=username)

        session["user_id"] = user["id"]
        session["user_name"] = user["username"]
        session["csrf_token"] = secrets.token_urlsafe(32)
        return redirect("/")

    return render_form_with_errors("login.html", errors=[], username="")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    return redirect("/")

@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    user = users.get_user_by_id(user_id)
    if not user:
        session.pop("user_id", None)
        session.pop("user_name", None)
        return redirect("/login")

    context = build_profile_view(user_id, user)
    return render_form_with_errors("profile.html", errors=[], **context)


@app.route("/profile/meals")
def profile_meals():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    user = users.get_user_by_id(user_id)
    if not user:
        session.pop("user_id", None)
        session.pop("user_name", None)
        return redirect("/login")

    return render_template("profile_meals.html", user=user, statistics=build_meal_statistics(user_id))


@app.route("/notifications")
@app.route("/messages")
def messages():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")
    return render_template("messages.html", notifications=db.get_notifications(user_id))


@app.route("/notifications/<int:notification_id>/open")
@app.route("/messages/<int:notification_id>/open")
def open_notification(notification_id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    notification = db.get_notification_target(notification_id, user_id)
    if not notification:
        return "Notification not found", 404

    db.mark_notification_read(notification_id, user_id)
    return redirect(
        f"/meal/{notification['meal_id']}#comment-{notification['comment_id']}"
    )


@app.route("/user/<int:user_id>")
def user_meals(user_id):
    user = users.get_user_by_id(user_id)
    if not user:
        return "User not found", 404

    user_meals = meals.get_meals_by_user(user_id)
    return render_template("user_meals.html", user=user, meals=user_meals)


@app.route("/profile/change-password", methods=["POST"])
def change_password():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    user = users.get_user_by_id(user_id)
    if not user:
        return redirect("/login")

    errors = []
    if not users.verify_user(user["username"], current_password):
        errors.append("Current password is incorrect.")
    if not new_password:
        errors.append("New password cannot be empty.")
    elif len(new_password) > users.MAX_PASSWORD_LENGTH:
        errors.append("Password cannot be longer than 128 characters.")
    if new_password != confirm_password:
        errors.append("New passwords do not match.")

    if errors:
        context = build_profile_view(user_id, user)
        return render_form_with_errors("profile.html", errors=errors, **context)

    users.update_password(user_id, new_password)
    return redirect("/profile")


@app.route("/profile/change-username", methods=["POST"])
def change_username():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    new_username = request.form.get("new_username", "").strip()
    password = request.form.get("password", "")

    user = users.get_user_by_id(user_id)
    if not user:
        return redirect("/login")

    errors = []
    if not users.verify_user(user["username"], password):
        errors.append("Password is incorrect.")
    if not new_username:
        errors.append("Username cannot be empty.")
    elif len(new_username) > users.MAX_USERNAME_LENGTH:
        errors.append("Username cannot be longer than 50 characters.")

    if errors:
        context = build_profile_view(user_id, user)
        return render_form_with_errors("profile.html", errors=errors, **context)

    try:
        users.update_username(user_id, new_username)
    except ValueError as error:
        context = build_profile_view(user_id, user)
        return render_form_with_errors("profile.html", errors=[str(error)], **context)

    session["user_name"] = new_username
    return redirect("/profile")


@app.route("/profile/delete-account", methods=["POST"])
def delete_account():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    password = request.form.get("password", "")
    user = users.get_user_by_id(user_id)
    if not user:
        return redirect("/login")

    if not users.verify_user(user["username"], password):
        context = build_profile_view(user_id, user)
        return render_form_with_errors("profile.html", errors=["Password is incorrect."], **context)

    users.delete_user(user_id)
    session.pop("user_id", None)
    session.pop("user_name", None)
    return redirect("/")


@app.route("/")
def index():
    search_query = request.args.get("query", "").strip()
    if len(search_query) > MAX_SEARCH_QUERY_LENGTH:
        return "Search query cannot be longer than 1000 characters.", 400
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    selected_diets = request.args.getlist("diets")
    selected_meal_types = request.args.getlist("meal_types")

    try:
        min_price_value = parse_price_filter(min_price)
        max_price_value = parse_price_filter(max_price)
    except ValueError as error:
        return str(error), 400

    sql, params = build_meal_search_query(
        search_query,
        min_price_value,
        max_price_value,
        selected_diets,
        selected_meal_types,
    )
    meal_rows = db.query(sql, params)
    diets = get_diets()
    return render_template(
        "index.html",
        meals=meal_rows,
        all_diets=diets,
        all_meal_types=db.get_meal_types(),
        selected_diets=selected_diets,
        selected_meal_types=selected_meal_types,
        query=search_query,
        min_price=min_price,
        max_price=max_price,
    )

# Näytetään itse lomake (GET-pyyntö)
@app.route("/messages/new")
@app.route("/form")
def form():
    return render_template("message_form.html")

# Vastaanotetaan lomakkeen tiedot (POST-pyyntö) ja näytetään tulos
@app.route("/messages/success", methods=["POST"])
@app.route("/result", methods=["POST"])
def result():
    user_message = request.form.get("message", "")
    if len(user_message) > MAX_MESSAGE_LENGTH:
        return render_template(
            "message_form.html",
            errors=["Message cannot be longer than 1000 characters."],
            message=user_message,
        ), 400
    return render_template("message_success.html", message=user_message)


@app.route("/meals/new")
@app.route("/meal")
def show_form():
    return render_template("meal.html", diets=get_diets(), meal_types=db.get_meal_types())


@app.route("/meals/<int:meal_id>")
@app.route("/meal/<int:meal_id>")
def meal_detail(meal_id):
    meal = meals.get_meal_by_id(meal_id)
    if not meal:
        return "Meal not found", 404
    comments = db.get_meal_comments(meal_id)
    ratings = db.get_meal_rating_summary(meal_id, session.get("user_id"))
    return render_template("meal_detail.html", meal=meal, comments=comments, comment_error=None, ratings=ratings, rating_error=None, diets=get_diets())


@app.route("/meals/<int:meal_id>/comments", methods=["POST"])
@app.route("/meal/<int:meal_id>/comments", methods=["POST"])
def add_meal_comment(meal_id):
    meal = meals.get_meal_by_id(meal_id)
    if not meal:
        return "Meal not found", 404

    if not session.get("user_id"):
        return redirect("/login")

    comment_body = request.form.get("comment", "").strip()
    if not comment_body:
        return render_template(
            "meal_detail.html",
            meal=meal,
            comments=db.get_meal_comments(meal_id),
            comment_error="Comment cannot be empty.",
            comment_body=comment_body,
            ratings=db.get_meal_rating_summary(meal_id, session.get("user_id")),
            rating_error=None,
            diets=get_diets(),
        )
    if len(comment_body) > 1000:
        return render_template(
            "meal_detail.html",
            meal=meal,
            comments=db.get_meal_comments(meal_id),
            comment_error="Comment cannot be longer than 1000 characters.",
            comment_body=comment_body,
            ratings=db.get_meal_rating_summary(meal_id, session.get("user_id")),
            rating_error=None,
            diets=get_diets(),
        )

    comment_id = db.add_meal_comment(
        meal_id,
        session.get("user_name"),
        comment_body,
        commenter_user_id=session["user_id"],
    )
    db.create_notification(
        meal["user_id"],
        session["user_id"],
        meal_id,
        comment_id,
        "new_comment",
    )
    return redirect(f"/meal/{meal_id}")


@app.route("/meals/<int:meal_id>/comments/<int:comment_id>/reply", methods=["POST"])
@app.route("/meal/<int:meal_id>/comments/<int:comment_id>/reply", methods=["POST"])
def reply_to_meal_comment(meal_id, comment_id):
    meal = meals.get_meal_by_id(meal_id)
    if not meal:
        return "Meal not found", 404

    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")
    if user_id != meal["user_id"]:
        return "Unauthorized", 403

    parent_comments = db.query(
        "SELECT id, commenter_user_id FROM meal_comments WHERE id = ? AND meal_id = ?",
        (comment_id, meal_id),
    )
    if not parent_comments:
        return "Comment not found", 404
    parent_comment = parent_comments[0]

    reply_body = request.form.get("reply", "").strip()
    if not reply_body or len(reply_body) > 1000:
        error = "Reply cannot be empty." if not reply_body else "Reply cannot be longer than 1000 characters."
        return render_template(
            "meal_detail.html",
            meal=meal,
            comments=db.get_meal_comments(meal_id),
            comment_error=None,
            ratings=db.get_meal_rating_summary(meal_id, user_id),
            rating_error=None,
            reply_error=error,
            reply_comment_id=comment_id,
            reply_body=reply_body,
            diets=get_diets(),
        )

    reply_id = db.add_meal_comment(
        meal_id,
        session.get("user_name"),
        reply_body,
        comment_id,
        session["user_id"],
    )
    if parent_comment["commenter_user_id"] is not None:
        db.create_notification(
            parent_comment["commenter_user_id"],
            session["user_id"],
            meal_id,
            reply_id,
            "comment_reply",
        )
    return redirect(f"/meal/{meal_id}")


@app.route("/meals/<int:meal_id>/rating", methods=["POST"])
@app.route("/meal/<int:meal_id>/rating", methods=["POST"])
def rate_meal(meal_id):
    meal = meals.get_meal_by_id(meal_id)
    if not meal:
        return "Meal not found", 404

    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    try:
        rating = int(request.form.get("rating", ""))
        db.save_meal_rating(meal_id, user_id, rating)
    except (TypeError, ValueError):
        return render_template(
            "meal_detail.html",
            meal=meal,
            comments=db.get_meal_comments(meal_id),
            comment_error=None,
            ratings=db.get_meal_rating_summary(meal_id, user_id),
            rating_error="Choose a rating from 1 to 5 stars.",
            diets=get_diets(),
        )

    return redirect(f"/meal/{meal_id}")


@app.route("/meals/<int:meal_id>/edit", methods=["GET", "POST"])
@app.route("/meal/<int:meal_id>/edit", methods=["GET", "POST"])
def edit_meal(meal_id):
    meal = meals.get_meal_by_id(meal_id)
    if not meal:
        return "Meal not found", 404

    if session.get("user_id") != meal["user_id"]:
        return "Unauthorized", 403

    if request.method == "POST":
        name = request.form.get("name", "")
        try:
            meals.update_meal(
                meal_id,
                name=name,
                meal_type=request.form["meal_type"],
                calories=request.form.get("calories", 0),
                protein=request.form.get("protein", 0),
                carbs=request.form.get("carbs", 0),
                fat=request.form.get("fat", 0),
                price=request.form.get("price", 0),
            )
        except ValueError as error:
            return render_template(
                "edit_meal.html",
                meal=meal,
                meal_name=name,
                diets=get_diets(),
                meal_types=db.get_meal_types(),
                errors=[str(error)],
            )
        return redirect("/")

    return render_template("edit_meal.html", meal=meal, diets=get_diets(), meal_types=db.get_meal_types())


@app.route("/meals/<int:meal_id>/delete", methods=["POST"])
@app.route("/meal/<int:meal_id>/delete", methods=["POST"])
def delete_meal(meal_id):
    meal = meals.get_meal_by_id(meal_id)
    if not meal:
        return "Meal not found", 404

    if session.get("user_id") != meal["user_id"]:
        return "Unauthorized", 403

    meals.delete_meal(meal_id)
    return redirect("/")


# 2. POST-reitti: Otetaan lomakkeen tiedot vastaan
@app.route("/meals", methods=["POST"])
@app.route("/add_meal", methods=["POST"])
def add_meal():
    user_id = session.get("user_id")
    if not user_id:
        return render_form_with_errors(
            "meal.html",
            errors=["You must be logged in to add a meal."],
            diets=get_diets(),
            meal_types=db.get_meal_types(),
        )

    name = request.form.get("name", "")
    meal_type = request.form.get("meal_type", "")
    calories = request.form.get("calories", 0)
    protein = request.form.get("protein", 0)
    carbs = request.form.get("carbs", 0)
    fat = request.form.get("fat", 0)
    price = request.form.get("price", 0)
    selected_diets = request.form.getlist("diets")
    diet_tags = ",".join(selected_diets)
    errors = validate_required_fields(
        {"name": name, "meal_type": meal_type},
        {
            "name": "Meal name is required.",
            "meal_type": "Meal type is required.",
        },
    )
    if len(name.strip()) > meals.MAX_MEAL_NAME_LENGTH:
        errors.append("Meal name cannot be longer than 50 characters.")

    if errors:
        return render_form_with_errors(
            "meal.html",
            errors=errors,
            diets=get_diets(),
            meal_types=db.get_meal_types(),
            meal_name=name,
            meal_type_value=meal_type,
            calories_value=calories,
            protein_value=protein,
            carbs_value=carbs,
            fat_value=fat,
            price_value=price,
            selected_diets=selected_diets,
        )

    try:
        meal_id = meals.create_meal(
            user_id=user_id,
            name=name,
            meal_type=meal_type,
            calories=calories,
            protein=protein,
            carbs=carbs,
            fat=fat,
            price=price,
            diet_tags=diet_tags,
        )
    except ValueError as error:
        return render_form_with_errors(
            "meal.html",
            errors=[str(error)],
            diets=get_diets(),
            meal_types=db.get_meal_types(),
            meal_name=name,
            meal_type_value=meal_type,
            calories_value=calories,
            protein_value=protein,
            carbs_value=carbs,
            fat_value=fat,
            price_value=price,
            selected_diets=selected_diets,
        )

    return redirect("/")



if __name__ == "__main__":
    app.run(debug=True)
