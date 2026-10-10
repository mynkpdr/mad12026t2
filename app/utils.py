from datetime import date, time

from flask import abort, redirect, url_for
from flask_login import current_user

from .extensions import login_manager
from .services import RuleError


def parse_date(text):
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise RuleError("Please enter a valid date.") from None


def parse_time(text):
    try:
        return time.fromisoformat(text)
    except ValueError:
        raise RuleError("Please enter a valid time.") from None


def form_int(form, name, minimum=1):
    try:
        value = int(form[name])
    except ValueError:
        raise RuleError(f"{name.replace('_', ' ').capitalize()} must be a whole number.") from None
    if value < minimum:
        raise RuleError(f"{name.replace('_', ' ').capitalize()} must be at least {minimum}.")
    return value


def restrict_to(blueprint, role):
    """Every route in the blueprint is now only for this role (cannot be forgotten per route)."""

    @blueprint.before_request
    def check_role():
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if current_user.role != role:
            abort(403)
        if role == "examiner" and not current_user.approved:
            return redirect(url_for("auth.pending"))
