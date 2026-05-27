from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User

auth_bp = Blueprint("auth", __name__)


def _maybe_elevate_admin(user):
    """Auto-elevate to admin if email matches ADMIN_EMAIL env var."""
    admin_email = current_app.config.get("ADMIN_EMAIL", "").strip().lower()
    if admin_email and user.email.lower() == admin_email and user.role != "admin":
        user.role = "admin"
        db.session.commit()


@auth_bp.route("/")
def index():
    return render_template("index.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard"))

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        display_name = request.form.get("display_name", "").strip()
        display_preference = request.form.get("display_preference", "username")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []
        if not first_name:
            errors.append("First name is required.")
        if not last_name:
            errors.append("Last name is required.")
        if not display_name:
            errors.append("Username is required.")
        if not email:
            errors.append("Email is required.")
        if not password:
            errors.append("Password is required.")
        if password and len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password and password != confirm:
            errors.append("Passwords do not match.")
        if email and User.query.filter_by(email=email).first():
            errors.append("An account with that email already exists.")
        if display_preference not in ("username", "real_name"):
            display_preference = "username"

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("auth/signup.html")

        user = User(
            first_name=first_name,
            last_name=last_name,
            display_name=display_name,
            display_preference=display_preference,
            email=email,
            has_completed_profile=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        _maybe_elevate_admin(user)
        login_user(user)
        flash(f"Welcome to FriedSports, {user.shown_name}!", "success")
        return redirect(url_for("dashboard.onboarding"))

    return render_template("auth/signup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html")

        _maybe_elevate_admin(user)
        login_user(user)
        next_page = request.args.get("next")
        return redirect(next_page or url_for("dashboard.dashboard"))

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.index"))
