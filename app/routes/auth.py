import random
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError
from app.models import db, User, LoginToken

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
        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("An account with that email or username already exists.", "error")
            return render_template("auth/signup.html")
        _maybe_elevate_admin(user)
        login_user(user)
        # Fire welcome email in background so it doesn't block the redirect
        try:
            import threading
            _app = current_app._get_current_object()
            _uid = user.id
            def _welcome_bg(app, uid):
                with app.app_context():
                    try:
                        from app.models import User as _User
                        from app.services.email_service import send_welcome_email
                        u = db.session.get(_User, uid)
                        if u:
                            send_welcome_email(u)
                    except Exception:
                        pass
            threading.Thread(target=_welcome_bg, args=(_app, _uid), daemon=True).start()
        except Exception:
            pass
        flash(f"Welcome to FriedSports, {user.shown_name}!", "success")
        next_page = request.form.get("next") or request.args.get("next")
        return redirect(next_page or url_for("dashboard.onboarding"))

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


# ── Email OTP sign-in ────────────────────────────────────────────────────────

@auth_bp.route("/send-code", methods=["GET", "POST"])
def send_code():
    """Show email input form (GET) or send a 6-digit OTP (POST)."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Enter your email address.", "error")
            return render_template("auth/send_code.html")

        user = User.query.filter_by(email=email).first()
        if not user:
            # Don't reveal whether the email exists
            flash("If that email is registered, a code is on its way.", "info")
            return redirect(url_for("auth.verify_code", email=email))

        # Generate a 6-digit code and store it
        code = str(random.randint(100000, 999999))
        tok = LoginToken(
            user_id=user.id,
            token=secrets.token_urlsafe(16),
            purpose="signin_code",
            code=code,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        db.session.add(tok)
        db.session.commit()

        try:
            from app.services.email_service import send_signin_code
            send_signin_code(user, code)
        except Exception as e:
            current_app.logger.error(f"Failed to send OTP: {e}")

        flash("If that email is registered, a code is on its way.", "info")
        return redirect(url_for("auth.verify_code", email=email))

    return render_template("auth/send_code.html")


@auth_bp.route("/verify-code", methods=["GET", "POST"])
def verify_code():
    """Accept the 6-digit OTP and log the user in."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard"))

    email = request.args.get("email", "") or request.form.get("email", "")

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        code = request.form.get("code", "").strip()

        user = User.query.filter_by(email=email).first()
        if not user:
            flash("Invalid code.", "error")
            return render_template("auth/verify_code.html", email=email)

        tok = (
            LoginToken.query
            .filter_by(user_id=user.id, purpose="signin_code", code=code)
            .filter(LoginToken.used_at.is_(None))
            .filter(LoginToken.expires_at > datetime.now(timezone.utc))
            .order_by(LoginToken.created_at.desc())
            .first()
        )
        if not tok:
            flash("That code is invalid or has expired.", "error")
            return render_template("auth/verify_code.html", email=email)

        tok.used_at = datetime.now(timezone.utc)
        db.session.commit()

        _maybe_elevate_admin(user)
        login_user(user)
        next_page = request.form.get("next") or request.args.get("next")
        return redirect(next_page or url_for("dashboard.dashboard"))

    return render_template("auth/verify_code.html", email=email)


# ── Magic link (one-click login from email CTA) ──────────────────────────────

@auth_bp.route("/magic/<token>")
def magic_link(token):
    """Validate a magic-link token, log the user in, redirect to next_url."""
    tok = LoginToken.query.filter_by(token=token, purpose="magic_link").first()

    if not tok or not tok.is_valid:
        flash("This link has expired or already been used. Log in below.", "warning")
        return redirect(url_for("auth.login"))

    tok.used_at = datetime.now(timezone.utc)
    db.session.commit()

    user = tok.user
    if not user:
        flash("Account not found.", "error")
        return redirect(url_for("auth.login"))

    _maybe_elevate_admin(user)
    login_user(user)

    next_url = tok.next_url or url_for("dashboard.dashboard")
    return redirect(next_url)
