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
    # Use psycopg v3 (C/libpq) for Postgres — much faster connection + query
    # handling than the pure-Python pg8000 driver, especially the TLS handshake
    # that dominates Neon connection setup. libpq reads sslmode / channel_binding
    # straight from the URL query string, so we keep the params intact.
    _is_pg = _db_url.startswith("postgresql://")
    if _is_pg and "+" not in _db_url.split("://", 1)[0]:
        _db_url = _db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url

    # Connection-pool tuning for a remote (Neon) DB behind gunicorn workers.
    #   pool_pre_ping  — drop dead connections (Neon's pooler closes idle ones)
    #                    before handing them out, avoiding stale-connection 500s.
    #   pool_recycle   — recycle before Neon's idle timeout would kill them.
    #   pool_size/overflow — per-worker; with 2 workers x 4 threads this keeps a
    #                    small warm set of reusable connections so most requests
    #                    skip the expensive TLS reconnect.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": 5,
        "max_overflow": 5,
    }
    if _is_pg:
        # 10s connect timeout so a Neon cold-start can't hang a worker forever;
        # keepalives hold the TCP/TLS session open to avoid needless reconnects.
        SQLALCHEMY_ENGINE_OPTIONS["connect_args"] = {
            "connect_timeout": 10,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
        }

    # Static file caching — 1 year in production, disabled in development
    # so CSS/JS changes are visible immediately without hard-refreshing.
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 1 year in seconds

    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")

    # Resend email
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "noreply@friedsports.com")


class DevelopmentConfig(Config):
    DEBUG = True
    SEND_FILE_MAX_AGE_DEFAULT = 0  # no caching in dev — CSS/JS changes appear immediately


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)
