from functools import wraps
from datetime import datetime, timezone
from flask import abort
from flask_login import current_user


def time_ago(dt):
    """Compact relative timestamp: 'just now', '4m ago', '3h ago', '2d ago'."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    s = (datetime.now(timezone.utc) - dt).total_seconds()
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{int(s // 60)}m ago"
    if s < 86400:
        return f"{int(s // 3600)}h ago"
    if s < 604800:
        return f"{int(s // 86400)}d ago"
    return dt.strftime("%-m/%-d")


def admin_required(f):
    """Decorator: requires User.role == 'admin'. 403 otherwise."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated
