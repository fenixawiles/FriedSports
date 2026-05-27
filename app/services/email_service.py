"""
Email service — FriedSports notification infrastructure.
All functions fail gracefully if mail is not configured.
"""

from flask import current_app
from flask_mail import Message


def _get_mail():
    """Lazy-import mail to avoid circular imports."""
    from app import mail
    return mail


def _send(subject, recipients, body_text, body_html=None):
    """Core send helper. Silently skips if MAIL_USERNAME is not set."""
    if not current_app.config.get("MAIL_USERNAME"):
        current_app.logger.info(f"[email skipped — not configured] To: {recipients} | {subject}")
        return False
    try:
        mail = _get_mail()
        msg = Message(
            subject=subject,
            recipients=recipients if isinstance(recipients, list) else [recipients],
            body=body_text,
            html=body_html,
        )
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Email send failed: {e}")
        return False


def send_welcome_email(user):
    """Send a welcome email to a new user."""
    subject = "Welcome to FriedSports 🔥"
    body = f"""Hey {user.display_name},

Welcome to FriedSports — where your team's disasters become your group's entertainment.

You've joined the roast. Pick your teams, invite your friends, and get ready to be held accountable.

friedsports.com

— The FriedSports crew
"""
    html = f"""
<p>Hey <strong>{user.display_name}</strong>,</p>
<p>Welcome to <strong>FriedSports</strong> — where your team's disasters become your group's entertainment.</p>
<p>You've joined the roast. Pick your teams, invite your friends, and get ready to be held accountable.</p>
<p><a href="https://friedsports.com">friedsports.com</a></p>
<p>— The FriedSports crew</p>
"""
    return _send(subject, user.email, body, html)


def send_invite_email(to_email, from_user, group, invite_url):
    """Send a group invite email."""
    subject = f"{from_user.display_name} invited you to {group.name} on FriedSports"
    body = f"""Hey,

{from_user.display_name} invited you to join "{group.name}" on FriedSports.

Click here to join: {invite_url}

FriedSports is a sports trash-talk platform where your team's losses become group threads. Pile in.

— The FriedSports crew
"""
    return _send(subject, to_email, body)


def send_admin_notification(subject, body):
    """Send an internal admin notification."""
    from flask import current_app
    admin_email = current_app.config.get("ADMIN_EMAIL")
    if not admin_email:
        return False
    return _send(f"[FriedSports Admin] {subject}", admin_email, body)


def send_password_reset_email(user, reset_url):
    """Send a password reset link (placeholder — needs token system)."""
    subject = "FriedSports — Password Reset"
    body = f"""Hey {user.display_name},

A password reset was requested for your FriedSports account.

Reset here: {reset_url}

If you didn't request this, ignore this email.

— FriedSports
"""
    return _send(subject, user.email, body)


def send_incident_notification(target_user, reporter, team, incident_type, group):
    """Notify a user when they've been reported."""
    type_labels = {
        "BLOWOUT_ALERT": "Getting Blown Out",
        "CHOKED_LEAD": "Choked a Lead",
        "FRAUD_WATCH": "Fraud Watch",
        "UPSET_ALERT": "Upset Loss",
        "DISASTER_QUARTER": "Disaster Quarter",
        "PLAYOFF_COLLAPSE": "Playoff Collapse",
        "SHUTOUT_RISK": "Shutout Risk",
        "FINAL_LOSS": "Final Loss",
        "RIVAL_LOSS": "Rival Loss",
        "PREMATURE_SLANDER": "Premature Slander",
    }
    label = type_labels.get(incident_type, incident_type)
    subject = f"[{group.name}] {reporter.display_name} started a thread on your {team.abbreviation}"
    body = f"""Hey {target_user.display_name},

{reporter.display_name} just started a "{label}" thread on your {team.city} {team.name} in {group.name}.

The thread is open. Go defend yourself.

friedsports.com

— FriedSports
"""
    return _send(subject, target_user.email, body)
