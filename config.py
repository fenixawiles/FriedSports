import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    _db_url = os.environ.get("DATABASE_URL", "sqlite:///friedsports.db")
    # Normalize legacy postgres:// to postgresql://
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    # Use pg8000 driver for postgresql:// URLs (pure Python, works on Python 3.13)
    _use_ssl = False
    if _db_url.startswith("postgresql://") and "+pg8000" not in _db_url:
        _use_ssl = "sslmode=require" in _db_url
        _db_url = _db_url.replace("postgresql://", "postgresql+pg8000://", 1)
        # Strip libpq-only query params (pg8000 ignores sslmode, channel_binding, etc.)
        if "?" in _db_url:
            _db_url = _db_url.split("?")[0]
    SQLALCHEMY_DATABASE_URI = _db_url
    # pool_pre_ping: SQLAlchemy checks the connection is alive before using it.
    # This is the primary fix for "stale connection" 500s when Neon's pooler
    # drops an idle connection and the next request tries to reuse it.
    # pool_recycle: proactively recycle connections every 5 minutes so they
    # never outlive Neon's idle timeout.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        **({"connect_args": {"ssl_context": True}} if _use_ssl else {}),
    }

    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")

    # Flask-Mail
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_FROM", "noreply@friedsports.com")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)
