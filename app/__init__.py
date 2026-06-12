import os
from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_compress import Compress
from flask_cors import CORS

from config import get_config
from app.models import db, User
import app.analytics.models  # noqa: F401 — register lab tables with SQLAlchemy

migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "warning"

compress = Compress()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def create_app(config=None):
    app = Flask(__name__)
    cfg = config or get_config()
    app.config.from_object(cfg)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    compress.init_app(app)

    # CORS — allow the Vite dev server (localhost:5173) to make credentialled
    # requests to Flask. In production Capacitor and the built React SPA are
    # same-origin, so this only matters in development.
    # Allow any localhost port in dev — Vite sometimes bumps to 5174/5175
    # when 5173 is occupied. In production (Railway + Capacitor) requests are
    # same-origin so CORS is irrelevant there.
    import re as _re
    CORS(app,
         supports_credentials=True,
         origins=_re.compile(r"http://(localhost|127\.0\.0\.1)(:\d+)?$"),
         allow_headers=["Content-Type", "X-Fetch"])

    # Blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.groups import groups_bp
    from app.routes.threads import threads_bp
    from app.routes.public import public_bp
    from app.routes.api import api_bp
    from app.routes.api_react import bp as api_react_bp
    from app.routes.reports import reports_bp
    from app.routes.admin import admin_bp
    from app.routes.legal import legal_bp
    from app.routes.support import support_bp
    from app.routes.friends import friends_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(groups_bp, url_prefix="/groups")
    app.register_blueprint(threads_bp, url_prefix="/threads")
    app.register_blueprint(public_bp, url_prefix="/public")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(api_react_bp)   # prefix /api defined on blueprint
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(legal_bp)
    app.register_blueprint(support_bp, url_prefix="/support")
    app.register_blueprint(friends_bp, url_prefix="/friends")

    # Serve the React SPA for all non-API, non-admin, non-static routes.
    # In production (Railway), Flask serves both the API and the built React bundle.
    # The React build lives at frontend/dist/ relative to the repo root.
    _react_build = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "frontend", "dist"
    )

    @app.route("/app/", defaults={"path": ""})
    @app.route("/app/<path:path>")
    @app.route("/", defaults={"path": ""})
    def serve_react(path):
        """Serve React SPA — root entry point + /app/* catch-all.

        The root "/" route is the Capacitor entry point.  Every subsequent
        navigation is handled client-side by React Router, so the server only
        needs to return index.html for the initial load.  Static build assets
        (JS/CSS chunks) are served by path when they exist on disk.
        """
        if not os.path.exists(_react_build):
            # Build not present (local dev without a Vite build).
            # Let Flask fall through to its own 404 handler; the dev server
            # on port 5173 serves React directly in this case.
            from flask import abort
            abort(404)
        full = os.path.join(_react_build, path)
        if path and os.path.exists(full) and not os.path.isdir(full):
            return send_from_directory(_react_build, path)
        return send_from_directory(_react_build, "index.html")

    # time_ago available in every template
    from app.utils import time_ago
    app.jinja_env.globals["time_ago"] = time_ago

    # Inject nav/sidebar state into every template: notification count,
    # pending friend requests, the user's groups, and unread-thread totals.
    from app.models import (
        Notification as _Notif,
        FriendRequest as _FR,
        GroupMember as _GM,
        GameThread as _GT,
    )
    from sqlalchemy.orm import joinedload as _joinedload

    @app.context_processor
    def _inject_nav_data():
        if not current_user.is_authenticated:
            return {
                "unread_notification_count": 0,
                "pending_friend_request_count": 0,
                "nav_groups": [],
                "nav_unread_total": 0,
                "nav_group_unread": {},
            }

        notif_count = _Notif.query.filter_by(
            user_id=current_user.id, is_read=False
        ).count()
        fr_count = _FR.query.filter_by(
            to_user_id=current_user.id, status="pending"
        ).count()

        memberships = (
            _GM.query
            .options(_joinedload(_GM.group))
            .filter_by(user_id=current_user.id)
            .all()
        )
        nav_groups = [m.group for m in memberships]
        group_ids = [m.group_id for m in memberships]

        nav_unread_total = 0
        nav_group_unread = {}
        if group_ids:
            from app.services.activity import unread_map as _unread_map
            thread_rows = (
                db.session.query(_GT.id, _GT.group_id)
                .filter(_GT.group_id.in_(group_ids), _GT.status == "active")
                .all()
            )
            if thread_rows:
                unread = _unread_map(current_user.id, [t for t, _ in thread_rows])
                group_of = {tid: gid for tid, gid in thread_rows}
                for tid, cnt in unread.items():
                    if cnt > 0:
                        nav_unread_total += 1
                        nav_group_unread[group_of[tid]] = (
                            nav_group_unread.get(group_of[tid], 0) + 1
                        )

        return {
            "unread_notification_count": notif_count,
            "pending_friend_request_count": fr_count,
            "nav_groups": nav_groups,
            "nav_unread_total": nav_unread_total,
            "nav_group_unread": nav_group_unread,
        }

    # Track last_active_at — throttled to one write per 5 minutes per user
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz

    @app.before_request
    def _touch_last_active():
        from flask import request as _req
        if not current_user.is_authenticated:
            return
        # Skip static assets and background polls
        if _req.endpoint == "static" or _req.path.startswith("/static"):
            return
        try:
            now = _dt.now(_tz.utc)
            last = current_user.last_active_at
            if last is not None and last.tzinfo is None:
                last = last.replace(tzinfo=_tz.utc)
            if last is None or (now - last) > _td(minutes=5):
                current_user.last_active_at = now
                db.session.commit()
        except Exception:
            db.session.rollback()

    register_commands(app)

    # Global handler for unhandled SQLAlchemy errors (stale connections, etc.)
    # These manifest as OperationalError or DatabaseError from pg8000/Postgres.
    # Without this, they bubble up as raw 500 pages.
    from sqlalchemy.exc import OperationalError, DatabaseError

    @app.errorhandler(OperationalError)
    @app.errorhandler(DatabaseError)
    def handle_db_error(e):
        db.session.rollback()
        from flask import flash, redirect, request as req, url_for
        import logging
        logging.getLogger(__name__).error("Database error: %s", e)
        flash("Something went wrong. Please try again.", "error")
        # Send back to the page they came from, or home
        referrer = req.referrer
        if referrer and req.host in referrer:
            return redirect(referrer), 302
        return redirect(url_for("auth.index")), 302

    return app


def register_commands(app):
    @app.cli.command("seed")
    def seed_command():
        """Seed teams, users, groups, and mock games."""
        from seed import run_seed
        run_seed()

    @app.cli.command("poll-scores")
    def poll_scores():
        """Advance mock games one tick and fire triggers."""
        from app.models import Game
        from app.services.mock_provider import MockSportsProvider
        from app.services.trigger_engine import process_game

        provider = MockSportsProvider()
        live_games = Game.query.filter_by(status="live").all()
        if not live_games:
            print("No live games found.")
            return
        for game in live_games:
            print(f"Ticking: {game.external_game_id} ({game.league})")
            provider.simulate_tick(game)
            process_game(game)
        print("Poll complete.")

    @app.cli.command("simulate")
    def simulate():
        """Run multiple poll ticks to rapidly advance game state."""
        from app.models import Game
        from app.services.mock_provider import MockSportsProvider
        from app.services.trigger_engine import process_game

        provider = MockSportsProvider()
        live_games = Game.query.filter_by(status="live").all()
        if not live_games:
            print("No live games found.")
            return
        for _ in range(3):
            for game in live_games:
                provider.simulate_tick(game)
                db.session.refresh(game)
                process_game(game)
        print("Simulate complete.")

    @app.cli.command("reset-db")
    def reset_db():
        """Wipe and recreate all tables (dev only)."""
        db.drop_all()
        db.create_all()
        print("Database reset.")
