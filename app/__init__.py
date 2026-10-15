import os
from datetime import date, datetime

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from config import Config

from .extensions import csrf, db, login_manager, mail
from .models import User
from .services import RuleError


def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)
    if os.environ.get("APP_ENV") == "production":  # no dev defaults in production: fail loudly if missing
        app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
        app.config["ADMIN_PASSWORD"] = os.environ["ADMIN_PASSWORD"]
    for extension in (db, login_manager, csrf, mail):
        extension.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    from .blueprints import admin, api, auth, examiner, student

    for module in (auth, admin, examiner, student, api):
        app.register_blueprint(module.bp)
    # Browsers ask for /favicon.ico on pages without an icon tag (PDFs, JSON)
    app.add_url_rule("/favicon.ico", "favicon", redirect_to="/static/img/favicon.ico")

    @app.errorhandler(RuleError)
    def rule_error(error):
        """A broken rule shows a message and sends the user back where they came from."""
        if request.blueprint == "api":
            return jsonify(error=str(error)), 400
        flash(str(error), "danger")
        return redirect(request.referrer or url_for("auth.home"))

    @app.errorhandler(403)
    @app.errorhandler(404)
    def http_error(error):
        if request.blueprint == "api":
            return jsonify(error=error.name), error.code
        return render_template("error.html", error=error), error.code

    register_template_helpers(app)

    with app.app_context():
        db.create_all()  # tables are created from the models, never by hand
        create_admin(app)

    from .cli import seed_command

    app.cli.add_command(seed_command)
    return app


def register_template_helpers(app):
    """Small helpers the page templates use."""

    @app.template_filter("initials")
    def initials(name):
        words = [w for w in name.split() if not w.endswith(".")] or name.split()
        return (words[0][0] + (words[-1][0] if len(words) > 1 else "")).upper()

    @app.template_filter("num")
    def num(value):
        """70.0 -> 70, 72.5 -> 72.5"""
        return f"{value:g}"

    def greeting():
        hour = datetime.now().hour
        return "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"

    app.jinja_env.globals.update(today=date.today, greeting=greeting)


def create_admin(app):
    if not User.query.filter_by(role="admin").first():
        admin = User(name="Admin", email=app.config["ADMIN_EMAIL"], role="admin")
        admin.set_password(app.config["ADMIN_PASSWORD"])
        db.session.add(admin)
        db.session.commit()
