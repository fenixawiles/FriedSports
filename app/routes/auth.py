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
        display_name = request.form.get("display_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not display_name or not email or not password:
            flash("All fields are required.", "error")
            return render_template("auth/signup.html")
        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("auth/signup.html")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("auth/signup.html")
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return render_template("auth/signup.html")

        user = User(display_name=display_name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        _maybe_elevate_admin(user)
        login_user(user)
        flash(f"Welcome to FriedSports, {display_name}!", "success")
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
