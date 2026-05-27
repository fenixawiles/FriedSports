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


def _get_apns_host():
    env = os.environ.get("APNS_ENV", "sandbox").lower()
    return _APNS_HOST_PROD if env == "production" else _APNS_HOST_SANDBOX


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


def send_push(user_id: int, title: str, body: str, data: dict = None):
    """
    Send a push notification to all registered iOS devices for a user.
    Fails silently if APNs is not configured — safe to call in all environments.
    """
    try:
        _send_push_inner(user_id, title, body, data or {})
    except Exception as e:
        logger.warning(f"Push notification failed for user {user_id}: {e}")


def _send_push_inner(user_id: int, title: str, body: str, data: dict):
    from app.models import DeviceToken

    bundle_id = os.environ.get("APNS_BUNDLE_ID", "com.friedsports.app")
    jwt_token = _make_jwt()
    if not jwt_token:
        return  # APNs not configured — skip silently

    tokens = DeviceToken.query.filter_by(user_id=user_id, platform="ios").all()
    if not tokens:
        return

    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed — push notifications unavailable")
        return

    host = _get_apns_host()
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
    with httpx.Client(http2=True) as client:
        for dt in tokens:
            url = f"https://{host}/3/device/{dt.token}"
            try:
                resp = client.post(url, content=payload, headers=headers)
                if resp.status_code == 410:
                    # Token is no longer valid
                    stale_tokens.append(dt.token)
                elif resp.status_code not in (200, 201):
                    logger.warning(f"APNs error {resp.status_code} for token {dt.token[:8]}…: {resp.text}")
            except Exception as e:
                logger.warning(f"APNs request failed: {e}")

    # Clean up stale tokens
    if stale_tokens:
        from app.models import db
        DeviceToken.query.filter(DeviceToken.token.in_(stale_tokens)).delete(synchronize_session=False)
        db.session.commit()
