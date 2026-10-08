import hmac
import secrets

from flask import Flask, render_template, request, session

import config
import db
from errors import redirect_with_error, register_error_handlers
from routes import bp

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

db.ensure_meals_schema()

MAX_TEXT_INPUT_LENGTH = 10000

register_error_handlers(app)


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
    if (
        not session_token
        or not submitted_token
        or not hmac.compare_digest(submitted_token, session_token)
    ):
        return redirect_with_error("Your session could not be verified. Please try again.")
    return None


@app.before_request
def limit_input_lengths():
    for values in (request.args, request.form):
        if any(
            len(value) > MAX_TEXT_INPUT_LENGTH
            for value_list in values.listvalues()
            for value in value_list
        ):
            return redirect_with_error("Input values cannot be longer than 10000 characters.")
    return None


app.register_blueprint(bp)


if __name__ == "__main__":
    app.run(debug=True)
