import hmac
import math
import secrets
from urllib.parse import urlsplit

from flask import Flask, abort, flash, redirect, render_template, request, session
from werkzeug.exceptions import HTTPException

import config
import db
import meals
import users

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

MAX_TEXT_INPUT_LENGTH = 10000
MAX_SEARCH_QUERY_LENGTH = 1000
MAX_MESSAGE_LENGTH = 1000


def redirect_with_error(message, fallback="/"):
    flash(message, "error")
    referrer = request.referrer
    if referrer:
        referrer_parts = urlsplit(referrer)
        request_host = urlsplit(request.host_url).netloc
        if (
            referrer_parts.scheme in ("http", "https")
            and referrer_parts.netloc == request_host
        ):
            return redirect(referrer)
    return redirect(fallback)


def parse_price_filter(value):
    if not value:
        return None
    try:
        price = float(value)
    except ValueError as error:
        raise ValueError(
            "Price filters must be valid numbers greater than or equal to 0."
        ) from error
    if not math.isfinite(price) or price < 0:
        raise ValueError(
            "Price filters must be valid numbers greater than or equal to 0."
        )
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


def render_meal_form(errors=None, **context):
    return render_form_with_errors(
        "meal.html",
        errors=errors,
        diets=meals.get_diets(),
        meal_types=meals.get_meal_types(),
        **context,
    )


def render_meal_detail(meal, user_id, **context):
    template_context = {
        "meal": meal,
        "comments": meals.get_meal_comments(meal["id"]),
        "comment_error": None,
        "ratings": meals.get_meal_rating_summary(meal["id"], user_id),
        "rating_error": None,
        "diets": meals.get_diets(),
    }
    template_context.update(context)
    return render_template("meal_detail.html", **template_context)


def require_login():
    if not session.get("user_id"):
        return redirect("/login")
    return None


def start_user_session(user_id, username):
    session["user_id"] = user_id
    session["user_name"] = username
    session["csrf_token"] = secrets.token_urlsafe(32)


def clear_user_session():
    session.pop("user_id", None)
    session.pop("user_name", None)


@app.errorhandler(HTTPException)
def handle_http_error(error):
    error_messages = {
        404: "The requested page or item could not be found.",
        405: "That action is not available on this page.",
        413: "The submitted information is too large.",
    }
    return redirect_with_error(error_messages.get(error.code, error.description))


@app.errorhandler(500)
def handle_internal_error(_error):
    return redirect_with_error(
        "An unexpected error occurred. Please try again later.",
        fallback="/",
    )


@app.before_request
def protect_from_csrf():
    if request.method != "POST":
        return None

    submitted_token = request.form.get("csrf_token", "")
    session_token = session.get("csrf_token", "")
    if (
        not session_token
        or not submitted_token
        or not hmac.compare_digest(submitted_token, session_token)
    ):
        return redirect_with_error(
            "Your session could not be verified. Please try again."
        )
    return None


@app.before_request
def limit_input_lengths():
    for values in (request.args, request.form):
        if any(
            len(value) > MAX_TEXT_INPUT_LENGTH
            for value_list in values.listvalues()
            for value in value_list
        ):
            return redirect_with_error(
                "Input values cannot be longer than 10000 characters."
            )
    return None


@app.before_request
def reject_out_of_range_route_ids():
    if request.view_args and any(
        isinstance(value, int) and value > db.MAX_SQLITE_INTEGER
        for value in request.view_args.values()
    ):
        abort(404)


def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


@app.context_processor
def inject_csrf_token():
    user_id = session.get("user_id")
    unread_notifications = meals.get_unread_notification_count(user_id) if user_id else 0
    return {
        "csrf_token": get_csrf_token(),
        "unread_notification_count": unread_notifications,
    }


db.initialize_schema()


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
    diet_names = {str(diet["id"]): diet["name"] for diet in meals.get_diets()}

    def summarize(meal_list):
        count = len(meal_list)
        return {
            "count": count,
            "calories": sum((meal.get("calories") or 0) for meal in meal_list),
            "protein": sum((meal.get("protein") or 0) for meal in meal_list),
            "carbs": sum((meal.get("carbs") or 0) for meal in meal_list),
            "fat": sum((meal.get("fat") or 0) for meal in meal_list),
            "price": sum((meal.get("price") or 0) for meal in meal_list),
            "average_calories": (
                (sum((meal.get("calories") or 0) for meal in meal_list) / count)
                if count
                else 0
            ),
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
        "by_type": [
            (name, summarize(group)) for name, group in sorted(grouped_by_type.items())
        ],
        "by_diet": [
            (name, summarize(group)) for name, group in sorted(grouped_by_diet.items())
        ],
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
        return render_form_with_errors(
            "register.html", errors=errors, username=username
        )

    try:
        user_id = users.create_user(username, password1)
    except ValueError as error:
        return render_form_with_errors(
            "register.html", errors=[str(error)], username=username
        )

    start_user_session(user_id, username)
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
            return render_form_with_errors(
                "login.html", errors=errors, username=username
            )

        user = users.verify_user(username, password)
        if not user:
            return render_form_with_errors(
                "login.html",
                errors=["Invalid username or password."],
                username=username,
            )

        start_user_session(user["id"], user["username"])
        return redirect("/")

    return render_form_with_errors("login.html", errors=[], username="")


@app.route("/logout")
def logout():
    clear_user_session()
    return redirect("/")


@app.route("/profile")
def profile():
    login_redirect = require_login()
    if login_redirect is not None:
        return login_redirect

    user_id = session.get("user_id")
    user = users.get_user_by_id(user_id)
    if not user:
        clear_user_session()
        return redirect("/login")

    context = build_profile_view(user_id, user)
    context["statistics"] = build_meal_statistics(user_id)
    return render_form_with_errors("profile.html", errors=[], **context)


@app.route("/profile/settings")
def profile_settings():
    login_redirect = require_login()
    if login_redirect is not None:
        return login_redirect

    user_id = session.get("user_id")
    user = users.get_user_by_id(user_id)
    if not user:
        clear_user_session()
        return redirect("/login")

    return render_form_with_errors("profile_settings.html", errors=[], user=user)


@app.route("/profile/change-password", methods=["POST"])
def change_password():
    login_redirect = require_login()
    if login_redirect is not None:
        return login_redirect

    user_id = session.get("user_id")
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
        return render_form_with_errors(
            "profile_settings.html", errors=errors, user=user
        )

    users.update_password(user_id, new_password)
    return redirect("/profile")


@app.route("/profile/change-username", methods=["POST"])
def change_username():
    login_redirect = require_login()
    if login_redirect is not None:
        return login_redirect

    user_id = session.get("user_id")
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
        return render_form_with_errors(
            "profile_settings.html",
            errors=errors,
            user=user,
            new_username=new_username,
        )

    try:
        users.update_username(user_id, new_username)
    except ValueError as error:
        return render_form_with_errors(
            "profile_settings.html",
            errors=[str(error)],
            user=user,
            new_username=new_username,
        )

    session["user_name"] = new_username
    return redirect("/profile")


@app.route("/profile/delete-account", methods=["POST"])
def delete_account():
    login_redirect = require_login()
    if login_redirect is not None:
        return login_redirect

    user_id = session.get("user_id")
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
    clear_user_session()
    return redirect("/")


@app.route("/profile/meals")
def profile_meals():
    login_redirect = require_login()
    if login_redirect is not None:
        return login_redirect

    user_id = session.get("user_id")
    if not users.get_user_by_id(user_id):
        clear_user_session()
        return redirect("/login")

    return redirect("/profile")


@app.route("/user/<int:user_id>")
def user_meals(user_id):
    user = users.get_user_by_id(user_id)
    if not user:
        return redirect_with_error(
            "That user's profile could not be found.", fallback="/"
        )

    user_meals = meals.get_meals_by_user(user_id)
    return render_template("user_meals.html", user=user, meals=user_meals)


@app.route("/")
def index():
    search_query = request.args.get("query", "").strip()
    errors = []
    if len(search_query) > MAX_SEARCH_QUERY_LENGTH:
        errors.append("Search query cannot be longer than 1000 characters.")
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    selected_diets = request.args.getlist("diets")
    selected_meal_types = request.args.getlist("meal_types")
    min_price_value = None
    max_price_value = None

    try:
        min_price_value = parse_price_filter(min_price)
        max_price_value = parse_price_filter(max_price)
    except ValueError as error:
        errors.append(str(error))

    if (
        min_price_value is not None
        and max_price_value is not None
        and min_price_value > max_price_value
    ):
        errors.append("Minimum price cannot be greater than maximum price.")

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
    diets = meals.get_diets()
    return render_template(
        "index.html",
        errors=errors,
        meals=meal_rows,
        all_diets=diets,
        all_meal_types=meals.get_meal_types(),
        selected_diets=selected_diets,
        selected_meal_types=selected_meal_types,
        query=search_query,
        min_price=min_price,
        max_price=max_price,
    )


# Display the form for a GET request.
@app.route("/messages/new")
@app.route("/form")
def form():
    return render_template("message_form.html")


# Receive the form submission and display its result.
@app.route("/messages/success", methods=["POST"])
@app.route("/result", methods=["POST"])
def result():
    user_message = request.form.get("message", "")
    errors = []
    if not user_message.strip():
        errors.append("Message cannot be empty.")
    if len(user_message) > MAX_MESSAGE_LENGTH:
        errors.append("Message cannot be longer than 1000 characters.")
    if errors:
        return (
            render_form_with_errors(
                "message_form.html",
                errors=errors,
                message=user_message,
            ),
            400,
        )
    return render_template("message_success.html", message=user_message)


@app.route("/meals/new")
@app.route("/meal")
def show_form():
    return render_template(
        "meal.html", diets=meals.get_diets(), meal_types=meals.get_meal_types()
    )


@app.route("/meals", methods=["POST"])
@app.route("/add_meal", methods=["POST"])
def add_meal():
    login_redirect = require_login()
    if login_redirect is not None:
        return render_meal_form(
            errors=["You must be logged in to add a meal."]
        )

    user_id = session.get("user_id")
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
        return render_meal_form(
            errors=errors,
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
        meals.create_meal(
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
        return render_meal_form(
            errors=[str(error)],
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


@app.route("/meals/<int:meal_id>")
@app.route("/meal/<int:meal_id>")
def meal_detail(meal_id):
    meal = meals.get_meal_by_id(meal_id)
    if not meal:
        return redirect_with_error("That meal could not be found.", fallback="/")
    return render_meal_detail(meal, session.get("user_id"))


@app.route("/meals/<int:meal_id>/edit", methods=["GET", "POST"])
@app.route("/meal/<int:meal_id>/edit", methods=["GET", "POST"])
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
        meal_type = request.form.get("meal_type", "")
        calories = request.form.get("calories", meal["calories"] or 0)
        protein = request.form.get("protein", meal["protein"] or 0)
        carbs = request.form.get("carbs", meal["carbs"] or 0)
        fat = request.form.get("fat", meal["fat"] or 0)
        price = request.form.get("price", meal["price"] or 0)
        selected_diets = request.form.getlist("diets")
        try:
            meals.update_meal(
                meal_id,
                name=name,
                meal_type=meal_type,
                calories=calories,
                protein=protein,
                carbs=carbs,
                fat=fat,
                price=price,
                diet_tags=",".join(selected_diets),
            )
        except ValueError as error:
            return render_template(
                "edit_meal.html",
                meal=meal,
                meal_name=name,
                selected_meal_type=meal_type,
                calories_value=calories,
                protein_value=protein,
                carbs_value=carbs,
                fat_value=fat,
                price_value=price,
                selected_diets=selected_diets,
                diets=meals.get_diets(),
                meal_types=meals.get_meal_types(),
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
        diets=meals.get_diets(),
        meal_types=meals.get_meal_types(),
    )


@app.route("/meals/<int:meal_id>/delete", methods=["POST"])
@app.route("/meal/<int:meal_id>/delete", methods=["POST"])
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


@app.route("/meals/<int:meal_id>/rating", methods=["POST"])
@app.route("/meal/<int:meal_id>/rating", methods=["POST"])
def rate_meal(meal_id):
    meal = meals.get_meal_by_id(meal_id)
    if not meal:
        return redirect_with_error("That meal could not be found.", fallback="/")

    login_redirect = require_login()
    if login_redirect is not None:
        return login_redirect

    user_id = session.get("user_id")

    try:
        rating = int(request.form.get("rating", ""))
        meals.save_meal_rating(meal_id, user_id, rating)
    except (TypeError, ValueError):
        return render_meal_detail(
            meal,
            user_id,
            rating_error="Choose a rating from 1 to 5 stars.",
        )

    return redirect(f"/meal/{meal_id}")


@app.route("/meals/<int:meal_id>/comments", methods=["POST"])
@app.route("/meal/<int:meal_id>/comments", methods=["POST"])
def add_meal_comment(meal_id):
    meal = meals.get_meal_by_id(meal_id)
    if not meal:
        return redirect_with_error("That meal could not be found.", fallback="/")

    login_redirect = require_login()
    if login_redirect is not None:
        return login_redirect

    comment_body = request.form.get("comment", "").strip()
    if not comment_body:
        return render_meal_detail(
            meal,
            session.get("user_id"),
            comment_error="Comment cannot be empty.",
            comment_body=comment_body,
        )
    if len(comment_body) > 1000:
        return render_meal_detail(
            meal,
            session.get("user_id"),
            comment_error="Comment cannot be longer than 1000 characters.",
            comment_body=comment_body,
        )

    comment_id = meals.add_meal_comment(
        meal_id,
        session.get("user_name"),
        comment_body,
        commenter_user_id=session["user_id"],
    )
    meals.create_notification(
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
        return redirect_with_error("That meal could not be found.", fallback="/")

    login_redirect = require_login()
    if login_redirect is not None:
        return login_redirect

    user_id = session.get("user_id")
    if user_id != meal["user_id"]:
        return redirect_with_error(
            "Only the meal owner can reply to comments.",
            fallback=f"/meal/{meal_id}",
        )

    parent_comment = meals.get_meal_comment_target(comment_id, meal_id)
    if not parent_comment:
        return redirect_with_error(
            "That comment could not be found.", fallback=f"/meal/{meal_id}"
        )

    reply_body = request.form.get("reply", "").strip()
    if not reply_body or len(reply_body) > 1000:
        error = (
            "Reply cannot be empty."
            if not reply_body
            else "Reply cannot be longer than 1000 characters."
        )
        return render_meal_detail(
            meal,
            user_id,
            reply_error=error,
            reply_comment_id=comment_id,
            reply_body=reply_body,
        )

    reply_id = meals.add_meal_comment(
        meal_id,
        session.get("user_name"),
        reply_body,
        comment_id,
        session["user_id"],
    )
    if parent_comment["commenter_user_id"] is not None:
        meals.create_notification(
            parent_comment["commenter_user_id"],
            session["user_id"],
            meal_id,
            reply_id,
            "comment_reply",
        )
    return redirect(f"/meal/{meal_id}")


@app.route("/notifications")
@app.route("/messages")
def messages():
    login_redirect = require_login()
    if login_redirect is not None:
        return login_redirect

    user_id = session.get("user_id")
    return render_template(
        "messages.html", notifications=meals.get_notifications(user_id)
    )


@app.route("/notifications/<int:notification_id>/open")
@app.route("/messages/<int:notification_id>/open")
def open_notification(notification_id):
    login_redirect = require_login()
    if login_redirect is not None:
        return login_redirect

    user_id = session.get("user_id")
    notification = meals.get_notification_target(notification_id, user_id)
    if not notification:
        return redirect_with_error(
            "That notification could not be found.", fallback="/messages"
        )

    meals.mark_notification_read(notification_id, user_id)
    return redirect(
        f"/meal/{notification['meal_id']}#comment-{notification['comment_id']}"
    )


if __name__ == "__main__":
    app.run(debug=True)
