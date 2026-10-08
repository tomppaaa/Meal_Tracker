from urllib.parse import urlsplit

from flask import flash, redirect, request
from werkzeug.exceptions import HTTPException


def redirect_with_error(message, fallback="/"):
    flash(message, "error")
    referrer = request.referrer
    if referrer:
        referrer_parts = urlsplit(referrer)
        request_host = urlsplit(request.host_url).netloc
        if referrer_parts.scheme in ("http", "https") and referrer_parts.netloc == request_host:
            return redirect(referrer)
    return redirect(fallback)


def register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        messages = {
            404: "The requested page or item could not be found.",
            405: "That action is not available on this page.",
            413: "The submitted information is too large.",
        }
        return redirect_with_error(messages.get(error.code, error.description))

    @app.errorhandler(500)
    def handle_internal_error(_error):
        return redirect_with_error(
            "An unexpected error occurred. Please try again later.",
            fallback="/",
        )
