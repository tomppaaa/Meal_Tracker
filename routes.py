import math
import secrets

from flask import Blueprint, request, redirect, session, render_template
import db, users, meals
from errors import redirect_with_error

bp = Blueprint("main", __name__)

MAX_SEARCH_QUERY_LENGTH = 1000
MAX_MESSAGE_LENGTH = 1000


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
    user_meals = meals.get_meals_by_user(user_id)
    return {
        "user": user,
        "user_meals": user_meals,
        "meal_count": len(user_meals),
        "total_calories": sum((meal.get("calories") or 0) for meal in user_meals),
        "total_price": sum((meal.get("price") or 0) for meal in user_meals),
    }


def build_meal_statistics(user_id):
    user_meals = meals.get_meals_by_user(user_id)
    diet_names = {str(diet["id"]): diet["name"] for diet in db.get_diets()}

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


@bp.route("/register")
def register():
    return render_template("register.html", errors=[], username="")

@bp.route("/create", methods=["POST"])
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

@bp.route("/login", methods=["GET", "POST"])
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

@bp.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    return redirect("/")

@bp.route("/profile")
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
    context["statistics"] = build_meal_statistics(user_id)
    return render_form_with_errors("profile.html", errors=[], **context)


@bp.route("/profile/settings")
def profile_settings():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    user = users.get_user_by_id(user_id)
    if not user:
        session.pop("user_id", None)
        session.pop("user_name", None)
        return redirect("/login")

    return render_form_with_errors("profile_settings.html", errors=[], user=user)


@bp.route("/profile/meals")
def profile_meals():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    if not users.get_user_by_id(user_id):
        session.pop("user_id", None)
        session.pop("user_name", None)
        return redirect("/login")

    return redirect("/profile")


@bp.route("/notifications")
@bp.route("/messages")
def messages():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")
    return render_template("messages.html", notifications=db.get_notifications(user_id))


@bp.route("/notifications/<int:notification_id>/open")
@bp.route("/messages/<int:notification_id>/open")
def open_notification(notification_id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    notification = db.get_notification_target(notification_id, user_id)
    if not notification:
        return redirect_with_error("That notification could not be found.", fallback="/messages")

    db.mark_notification_read(notification_id, user_id)
    return redirect(
        f"/meal/{notification['meal_id']}#comment-{notification['comment_id']}"
    )


@bp.route("/user/<int:user_id>")
def user_meals(user_id):
    user = users.get_user_by_id(user_id)
    if not user:
        return redirect_with_error("That user's profile could not be found.", fallback="/")

    user_meals = meals.get_meals_by_user(user_id)
    return render_template("user_meals.html", user=user, meals=user_meals)


@bp.route("/profile/change-password", methods=["POST"])
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
        return render_form_with_errors("profile_settings.html", errors=errors, user=user)

    users.update_password(user_id, new_password)
    return redirect("/profile")


@bp.route("/profile/change-username", methods=["POST"])
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
        return render_form_with_errors("profile_settings.html", errors=errors, user=user)

    try:
        users.update_username(user_id, new_username)
    except ValueError as error:
        return render_form_with_errors("profile_settings.html", errors=[str(error)], user=user)

    session["user_name"] = new_username
    return redirect("/profile")


@bp.route("/profile/delete-account", methods=["POST"])
def delete_account():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    password = request.form.get("password", "")
    user = users.get_user_by_id(user_id)
    if not user:
        return redirect("/login")

    if not users.verify_user(user["username"], password):
        return render_form_with_errors(
            "profile_settings.html",
            errors=["Password is incorrect."],
            user=user,
        )

    users.delete_user(user_id)
    session.pop("user_id", None)
    session.pop("user_name", None)
    return redirect("/")


@bp.route("/")
def index():
    search_query = request.args.get("query", "").strip()
    errors = []
    if len(search_query) > MAX_SEARCH_QUERY_LENGTH:
        errors.append("Search query cannot be longer than 1000 characters.")
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    selected_diets = request.args.getlist("diets")
    selected_meal_types = request.args.getlist("meal_types")

    try:
        min_price_value = parse_price_filter(min_price)
        max_price_value = parse_price_filter(max_price)
    except ValueError as error:
        errors.append(str(error))

    if errors:
        meal_rows = []
    else:
        meal_rows = meals.search_meals(
            search_query,
            min_price_value,
            max_price_value,
            selected_diets,
            selected_meal_types,
        )
    diets = db.get_diets()
    return render_template(
        "index.html",
        errors=errors,
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
@bp.route("/messages/new")
@bp.route("/form")
def form():
    return render_template("message_form.html")

# Vastaanotetaan lomakkeen tiedot (POST-pyyntö) ja näytetään tulos
@bp.route("/messages/success", methods=["POST"])
@bp.route("/result", methods=["POST"])
def result():
    user_message = request.form.get("message", "")
    if len(user_message) > MAX_MESSAGE_LENGTH:
        return render_form_with_errors(
            "message_form.html",
            errors=["Message cannot be longer than 1000 characters."],
            message=user_message,
        ), 400
    return render_template("message_success.html", message=user_message)


@bp.route("/meals/new")
@bp.route("/meal")
def show_form():
    return render_template("meal.html", diets=db.get_diets(), meal_types=db.get_meal_types())


@bp.route("/meals/<int:meal_id>")
@bp.route("/meal/<int:meal_id>")
def meal_detail(meal_id):
    meal = meals.get_meal_by_id(meal_id)
    if not meal:
        return redirect_with_error("That meal could not be found.", fallback="/")
    comments = db.get_meal_comments(meal_id)
    ratings = db.get_meal_rating_summary(meal_id, session.get("user_id"))
    return render_template("meal_detail.html", meal=meal, comments=comments, comment_error=None, ratings=ratings, rating_error=None, diets=db.get_diets())


@bp.route("/meals/<int:meal_id>/comments", methods=["POST"])
@bp.route("/meal/<int:meal_id>/comments", methods=["POST"])
def add_meal_comment(meal_id):
    meal = meals.get_meal_by_id(meal_id)
    if not meal:
        return redirect_with_error("That meal could not be found.", fallback="/")

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
            diets=db.get_diets(),
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
            diets=db.get_diets(),
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


@bp.route("/meals/<int:meal_id>/comments/<int:comment_id>/reply", methods=["POST"])
@bp.route("/meal/<int:meal_id>/comments/<int:comment_id>/reply", methods=["POST"])
def reply_to_meal_comment(meal_id, comment_id):
    meal = meals.get_meal_by_id(meal_id)
    if not meal:
        return redirect_with_error("That meal could not be found.", fallback="/")

    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")
    if user_id != meal["user_id"]:
        return redirect_with_error(
            "Only the meal owner can reply to comments.",
            fallback=f"/meal/{meal_id}",
        )

    parent_comment = db.get_meal_comment_target(comment_id, meal_id)
    if not parent_comment:
        return redirect_with_error("That comment could not be found.", fallback=f"/meal/{meal_id}")

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
            diets=db.get_diets(),
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


@bp.route("/meals/<int:meal_id>/rating", methods=["POST"])
@bp.route("/meal/<int:meal_id>/rating", methods=["POST"])
def rate_meal(meal_id):
    meal = meals.get_meal_by_id(meal_id)
    if not meal:
        return redirect_with_error("That meal could not be found.", fallback="/")

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
            diets=db.get_diets(),
        )

    return redirect(f"/meal/{meal_id}")


@bp.route("/meals/<int:meal_id>/edit", methods=["GET", "POST"])
@bp.route("/meal/<int:meal_id>/edit", methods=["GET", "POST"])
def edit_meal(meal_id):
    meal = meals.get_meal_by_id(meal_id)
    if not meal:
        return redirect_with_error("That meal could not be found.", fallback="/")

    if session.get("user_id") != meal["user_id"]:
        return redirect_with_error(
            "Only the meal owner can edit this meal.",
            fallback=f"/meal/{meal_id}",
        )

    if request.method == "POST":
        name = request.form.get("name", "")
        selected_diets = request.form.getlist("diets")
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
                diet_tags=",".join(selected_diets),
            )
        except ValueError as error:
            return render_template(
                "edit_meal.html",
                meal=meal,
                meal_name=name,
                selected_diets=selected_diets,
                diets=db.get_diets(),
                meal_types=db.get_meal_types(),
                errors=[str(error)],
            )
        return redirect("/")

    selected_diets = [
        diet_id.strip()
        for diet_id in (meal.get("diet_tags") or "").split(",")
        if diet_id.strip()
    ]
    return render_template(
        "edit_meal.html",
        meal=meal,
        selected_diets=selected_diets,
        diets=db.get_diets(),
        meal_types=db.get_meal_types(),
    )


@bp.route("/meals/<int:meal_id>/delete", methods=["POST"])
@bp.route("/meal/<int:meal_id>/delete", methods=["POST"])
def delete_meal(meal_id):
    meal = meals.get_meal_by_id(meal_id)
    if not meal:
        return redirect_with_error("That meal could not be found.", fallback="/")

    if session.get("user_id") != meal["user_id"]:
        return redirect_with_error(
            "Only the meal owner can delete this meal.",
            fallback=f"/meal/{meal_id}",
        )

    meals.delete_meal(meal_id)
    return redirect("/")


# 2. POST-reitti: Otetaan lomakkeen tiedot vastaan
@bp.route("/meals", methods=["POST"])
@bp.route("/add_meal", methods=["POST"])
def add_meal():
    user_id = session.get("user_id")
    if not user_id:
        return render_form_with_errors(
            "meal.html",
            errors=["You must be logged in to add a meal."],
            diets=db.get_diets(),
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
            diets=db.get_diets(),
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
            diets=db.get_diets(),
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

