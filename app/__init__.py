from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail

from config import get_config
from app.models import db, User
import app.analytics.models  # noqa: F401 — register lab tables with SQLAlchemy

migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "warning"

mail = Mail()


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
    mail.init_app(app)

    # Blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.groups import groups_bp
    from app.routes.threads import threads_bp
    from app.routes.public import public_bp
    from app.routes.api import api_bp
    from app.routes.reports import reports_bp
    from app.routes.admin import admin_bp
    from app.routes.legal import legal_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(groups_bp, url_prefix="/groups")
    app.register_blueprint(threads_bp, url_prefix="/threads")
    app.register_blueprint(public_bp, url_prefix="/public")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(legal_bp)

    register_commands(app)

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
