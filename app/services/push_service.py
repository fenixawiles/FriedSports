"""
APNs push notification service for FriedSports iOS app.

Requires env vars (set in Railway + local .env):
  APNS_KEY_ID    — 10-char key ID from Apple Developer portal
  APNS_TEAM_ID   — 10-char Team ID from Apple Developer portal
  APNS_KEY_PATH  — path to the .p8 key file (or set APNS_KEY_CONTENT for Railway)
  APNS_BUNDLE_ID — com.friedsports.app
  APNS_ENV       — "production" or "sandbox" (default: "sandbox" for dev)

None of these are required for the web app — the service fails silently
if not configured, so Railway deployment is unaffected until you're ready.
"""

import os
import time
import json
import logging

logger = logging.getLogger(__name__)

_APNS_HOST_SANDBOX = "api.sandbox.push.apple.com"
_APNS_HOST_PROD = "api.push.apple.com"


def normalize_environment(environment=None):
    env = (environment or os.environ.get("APNS_ENV", "sandbox")).strip().lower()
    if env in ("prod", "production"):
        return "production"
    return "sandbox"


def _get_apns_host(environment=None):
    env = normalize_environment(environment)
    return _APNS_HOST_PROD if env == "production" else _APNS_HOST_SANDBOX


def mask_token(token):
    token = token or ""
    if len(token) <= 16:
        return token
    return f"{token[:8]}…{token[-8:]}"


def _has_es256_support():
    try:
        import jwt
        return "ES256" in jwt.algorithms.get_default_algorithms()
    except Exception:
        return False


def apns_config_status(environment=None):
    key_path = os.environ.get("APNS_KEY_PATH", "")
    has_key_path = bool(key_path and os.path.exists(key_path))
    pyjwt_available = True
    cryptography_available = True
    httpx_available = True
    try:
        import jwt  # noqa: F401
    except ImportError:
        pyjwt_available = False
    try:
        import cryptography  # noqa: F401
    except ImportError:
        cryptography_available = False
    try:
        import httpx  # noqa: F401
    except ImportError:
        httpx_available = False
    es256_available = pyjwt_available and _has_es256_support()

    env = normalize_environment(environment)
    has_key_content = bool(os.environ.get("APNS_KEY_CONTENT", ""))
    has_key_id = bool(os.environ.get("APNS_KEY_ID", ""))
    has_team_id = bool(os.environ.get("APNS_TEAM_ID", ""))
    bundle_id = os.environ.get("APNS_BUNDLE_ID", "com.friedsports.app")
    configured = all([
        has_key_id,
        has_team_id,
        bool(has_key_content or has_key_path),
        bool(bundle_id),
        pyjwt_available,
        cryptography_available,
        es256_available,
        httpx_available,
    ])
    return {
        "configured": configured,
        "environment": env,
        "host": _get_apns_host(env),
        "bundle_id": bundle_id,
        "key_id_configured": has_key_id,
        "team_id_configured": has_team_id,
        "key_content_configured": has_key_content,
        "key_path_configured": has_key_path,
        "pyjwt_available": pyjwt_available,
        "cryptography_available": cryptography_available,
        "es256_available": es256_available,
        "httpx_available": httpx_available,
    }


def _make_jwt():
    """Generate a short-lived JWT signed with the APNs .p8 key."""
    import jwt as pyjwt  # PyJWT

    key_id = os.environ.get("APNS_KEY_ID", "")
    team_id = os.environ.get("APNS_TEAM_ID", "")
    key_content = os.environ.get("APNS_KEY_CONTENT", "")
    key_path = os.environ.get("APNS_KEY_PATH", "")

    if not (key_id and team_id):
        return None

    if key_content:
        private_key = key_content.replace("\\n", "\n")
    elif key_path and os.path.exists(key_path):
        with open(key_path, "r") as f:
            private_key = f.read()
    else:
        return None

    token = pyjwt.encode(
        {"iss": team_id, "iat": int(time.time())},
        private_key,
        algorithm="ES256",
        headers={"kid": key_id},
    )
    return token


def send_push(user_id: int, title: str, body: str, data: dict = None, environment: str = None):
    """
    Send a push notification to all registered iOS devices for a user.
    Fails silently if APNs is not configured — safe to call in all environments.
    Returns structured delivery data for admin diagnostics; callers that do not
    need it can ignore the return value.
    """
    try:
        return _send_push_inner(user_id, title, body, data or {}, environment=environment)
    except Exception as e:
        try:
            from app.models import db
            db.session.rollback()
        except Exception:
            pass
        logger.warning(f"Push notification failed for user {user_id}: {e}")
        env = normalize_environment(environment)
        return {
            "ok": False,
            "configured": False,
            "environment": env,
            "host": _get_apns_host(env),
            "bundle_id": os.environ.get("APNS_BUNDLE_ID", "com.friedsports.app"),
            "reason": str(e),
            "token_count": 0,
            "accepted_count": 0,
            "failed_count": 1,
            "stale_count": 0,
            "results": [],
        }


def _send_push_inner(user_id: int, title: str, body: str, data: dict, environment: str = None):
    from app.models import DeviceToken

    env = normalize_environment(environment)
    bundle_id = os.environ.get("APNS_BUNDLE_ID", "com.friedsports.app")
    config = apns_config_status(env)
    base = {
        "ok": False,
        "configured": config["configured"],
        "environment": env,
        "host": config["host"],
        "bundle_id": bundle_id,
        "reason": "",
        "token_count": 0,
        "accepted_count": 0,
        "failed_count": 0,
        "stale_count": 0,
        "results": [],
    }
    if not config["configured"]:
        return {**base, "reason": "apns_not_configured"}

    jwt_token = _make_jwt()
    if not jwt_token:
        return {**base, "reason": "apns_jwt_unavailable"}

    tokens = (
        DeviceToken.query
        .filter_by(user_id=user_id, platform="ios", environment=env)
        .order_by(DeviceToken.updated_at.desc())
        .all()
    )
    if not tokens:
        return {**base, "reason": "no_device_tokens"}

    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed — push notifications unavailable")
        return {**base, "reason": "httpx_unavailable"}

    host = _get_apns_host(env)
    headers = {
        "authorization": f"bearer {jwt_token}",
        "apns-topic": bundle_id,
        "apns-push-type": "alert",
        "apns-priority": "10",
        "content-type": "application/json",
    }
    payload = json.dumps({
        "aps": {
            "alert": {"title": title, "body": body},
            "badge": 1,
            "sound": "default",
        },
        **data,
    })

    stale_tokens = []
    results = []
    with httpx.Client(http2=True, timeout=10.0) as client:
        for dt in tokens:
            url = f"https://{host}/3/device/{dt.token}"
            item = {
                "token_id": dt.id,
                "token": mask_token(dt.token),
                "environment": dt.environment,
                "accepted": False,
                "stale": False,
                "status_code": None,
                "reason": "",
                "apns_id": "",
            }
            try:
                resp = client.post(url, content=payload, headers=headers)
                item["status_code"] = resp.status_code
                item["apns_id"] = resp.headers.get("apns-id", "")
                try:
                    response_json = resp.json()
                    item["reason"] = response_json.get("reason", "") or resp.text[:240]
                except Exception:
                    item["reason"] = resp.text[:240]
                if resp.status_code == 410:
                    # Token is no longer valid
                    item["stale"] = True
                    stale_tokens.append(dt.token)
                elif resp.status_code in (200, 201):
                    item["accepted"] = True
                else:
                    logger.warning(f"APNs error {resp.status_code} for token {dt.token[:8]}…: {resp.text}")
            except Exception as e:
                item["reason"] = str(e)
                logger.warning(f"APNs request failed: {e}")
            results.append(item)

    # Clean up stale tokens
    if stale_tokens:
        from app.models import db
        DeviceToken.query.filter(DeviceToken.token.in_(stale_tokens)).delete(synchronize_session=False)
        db.session.commit()

    accepted_count = sum(1 for item in results if item["accepted"])
    stale_count = sum(1 for item in results if item["stale"])
    failed_count = len(results) - accepted_count
    return {
        **base,
        "ok": accepted_count > 0 and failed_count == 0,
        "reason": "" if accepted_count else "no_pushes_accepted",
        "token_count": len(results),
        "accepted_count": accepted_count,
        "failed_count": failed_count,
        "stale_count": stale_count,
        "results": results,
    }
