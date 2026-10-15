from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import User
from ..services import RuleError

bp = Blueprint("auth", __name__)


@bp.route("/")
def home():
    """Send each visitor to the right place for their role."""
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    return redirect(url_for(f"{current_user.role}.dashboard"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"].strip().lower()).first()
        if not user or not user.check_password(request.form["password"]):
            raise RuleError("Wrong email or password.")
        if not login_user(user):  # refuses deactivated accounts
            raise RuleError("This account has been deactivated. Please contact the admin.")
        return redirect(url_for("auth.home"))
    return render_template("auth/login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        form = request.form
        email, role = form["email"].strip().lower(), form["role"]
        if role not in ("student", "examiner"):
            raise RuleError("Choose student or examiner.")
        if len(form["password"]) < 8:
            raise RuleError("Password must have at least 8 characters.")
        if User.query.filter_by(email=email).first():
            raise RuleError("This email is already registered.")
        if role == "examiner" and not form["department"].strip():
            raise RuleError("Examiners must enter their department.")
        user = User(name=form["name"].strip(), email=email, role=role, phone=form["phone"].strip(),
                    department=form["department"].strip(), approved=(role == "student"))
        user.set_password(form["password"])
        db.session.add(user)
        db.session.commit()
        flash("Registered! " + ("Please log in." if role == "student" else "You can log in once the admin approves you."), "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/pending")
@login_required
def pending():
    if current_user.role != "examiner" or current_user.approved:
        return redirect(url_for("auth.home"))
    return render_template("auth/pending.html")


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """Edit own profile (all roles)."""
    if request.method == "POST":
        form = request.form
        current_user.name = form["name"].strip()
        current_user.phone = form["phone"].strip()
        current_user.department = form["department"].strip()
        if form["new_password"]:
            if not current_user.check_password(form["current_password"]):
                raise RuleError("Current password is wrong.")
            if len(form["new_password"]) < 8:
                raise RuleError("Password must have at least 8 characters.")
            current_user.set_password(form["new_password"])
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html")
