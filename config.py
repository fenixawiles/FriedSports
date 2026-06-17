import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── "Stay logged in" / session persistence ────────────────────────────────
    # Closing the native app (which tears down the WKWebView process) must NOT
    # log the user out. Flask-Login's remember cookie is a persistent,
    # HMAC-signed (with SECRET_KEY) token that survives app restarts. Because
    # it's signed, any tampering invalidates it — the user is only logged out by
    # an explicit logout (which clears the cookie) or a corrupted/expired token.
    # login_user(..., remember=True) at every login site sets this cookie.
    REMEMBER_COOKIE_DURATION = timedelta(days=365)
    REMEMBER_COOKIE_HTTPONLY = True          # JS can't read it (XSS hardening)
    REMEMBER_COOKIE_SAMESITE = "Lax"
    # Server-side session cookie hardening + a long lifetime so the signed
    # session itself also persists rather than expiring at "browser close".
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(days=365)

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
    # HTTPS-only cookies in production (friedsports.com is TLS). Left off in dev
    # so cookies still flow over http://localhost.
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)
