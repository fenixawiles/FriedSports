"""
Email service — FriedSports
All functions fail gracefully if RESEND_API_KEY is not set.
"""

import random
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app


# ── Core send helper ────────────────────────────────────────────────────────

def _send(to, subject, html, text=None):
    """Send via Resend. Returns True on success, False on failure/skip."""
    import resend

    api_key = current_app.config.get("RESEND_API_KEY", "")
    if not api_key:
        current_app.logger.info(f"[email skipped — RESEND_API_KEY not set] To: {to} | {subject}")
        return False

    resend.api_key = api_key
    from_addr = current_app.config.get("MAIL_FROM", "noreply@friedsports.com")

    try:
        resend.Emails.send({
            "from": from_addr,
            "to": to if isinstance(to, list) else [to],
            "subject": subject,
            "html": html,
            "text": text or "",
        })
        return True
    except Exception as e:
        current_app.logger.error(f"Resend error: {e}")
        return False


# ── HTML wrapper ─────────────────────────────────────────────────────────────

def _wrap(body_html):
    """Wrap content in a minimal dark-themed email shell."""
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body {{ margin:0; padding:0; background:#0f0f17; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }}
  .shell {{ max-width:520px; margin:0 auto; padding:32px 24px; }}
  .logo {{ font-size:13px; font-weight:700; letter-spacing:.1em; text-transform:uppercase; color:#d93348; margin-bottom:28px; }}
  .logo-dot {{ display:inline-block; width:6px; height:6px; border-radius:50%; background:#d93348; margin-right:6px; vertical-align:middle; }}
  p {{ font-size:15px; line-height:1.65; color:#c8c8d8; margin:0 0 16px; }}
  .btn {{ display:inline-block; background:#d93348; color:#fff !important; text-decoration:none; padding:12px 24px; border-radius:6px; font-weight:600; font-size:14px; margin:8px 0 24px; }}
  .muted {{ font-size:12px; color:#72728a; margin-top:24px; }}
  .divider {{ border:none; border-top:1px solid #2a2a3a; margin:24px 0; }}
  .code-box {{ background:#1a1a2e; border:1px solid #2a2a3a; border-radius:6px; padding:20px; text-align:center; margin:16px 0 24px; }}
  .code-box span {{ font-size:36px; font-weight:700; letter-spacing:.3em; color:#fff; font-family:monospace; }}
</style>
</head>
<body>
<div class="shell">
  <div class="logo"><span class="logo-dot"></span>FriedSports</div>
  {body_html}
  <p class="muted">This email was sent by FriedSports. If you didn't expect it, ignore it.</p>
</div>
</body>
</html>"""


# ── Welcome email ────────────────────────────────────────────────────────────

def send_welcome_email(user):
    subject = "Welcome to FriedSports 🔥"
    html = _wrap(f"""
<p>Hey <strong style="color:#fff">{user.display_name}</strong>,</p>
<p>Welcome to FriedSports — where your team's disasters become your group's entertainment.</p>
<p>Find your friends, start a group, and start holding each other accountable.</p>
<a href="https://friedsports.com/dashboard" class="btn">Go to Dashboard →</a>
<hr class="divider">
<p class="muted">You're receiving this because you just created a FriedSports account.</p>
""")
    text = f"Hey {user.display_name}, welcome to FriedSports. https://friedsports.com"
    return _send(user.email, subject, html, text)


# ── Sign-in code ─────────────────────────────────────────────────────────────

def send_signin_code(user, code):
    subject = "Your FriedSports sign-in code"
    html = _wrap(f"""
<p>Here's your sign-in code for FriedSports. It expires in 15 minutes.</p>
<div class="code-box"><span>{code}</span></div>
<p style="font-size:13px;color:#72728a">If you didn't request this, you can safely ignore this email.</p>
""")
    text = f"Your FriedSports sign-in code is: {code}. It expires in 15 minutes."
    return _send(user.email, subject, html, text)


# ── Thread notification (magic-link CTA) ─────────────────────────────────────

_THREAD_SUBJECTS = [
    "{reporter} is putting your {team} on trial in {group} 👀",
    "Your {team} has been formally accused in {group}",
    "{reporter} opened a case against your {team} — respond or forfeit",
    "Breaking: {reporter} has filed allegations about your {team}",
    "The {group} jury is assembling — your {team} is on the docket",
    "{reporter} started a thread. Your {team} is the defendant.",
    "New evidence against your {team} has been submitted in {group}",
]


def send_thread_notification(target_user, reporter, team, incident_type, group,
                             thread_id=None, description=None):
    """Notify a user when someone starts a thread targeting them.
    Generates a magic-link so they can tap the CTA and land directly on the thread.
    """
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

    subject_tmpl = random.choice(_THREAD_SUBJECTS)
    subject = subject_tmpl.format(
        reporter=reporter.display_name,
        team=team.abbreviation,
        group=group.name,
    )

    # Build CTA URL — magic link if thread_id provided, else direct URL
    base_url = "https://friedsports.com"
    if thread_id:
        token = _make_magic_link(target_user.id, f"/threads/{thread_id}")
        cta_url = f"{base_url}/auth/magic/{token}"
    else:
        cta_url = f"{base_url}/dashboard"

    desc_block = ""
    if description:
        desc_block = f'<p style="background:#1a1a2e;border-left:3px solid #d93348;padding:10px 14px;border-radius:0 4px 4px 0;font-style:italic;color:#c8c8d8;margin:0 0 20px">{description}</p>'

    html = _wrap(f"""
<p>Hey <strong style="color:#fff">{target_user.display_name}</strong>,</p>
<p><strong style="color:#fff">{reporter.display_name}</strong> just filed a
<strong style="color:#d93348">{label}</strong> thread on your
<strong style="color:#fff">{team.city} {team.name}</strong>
in <strong style="color:#fff">{group.name}</strong>.</p>
{desc_block}
<p>The group is watching. Go defend yourself.</p>
<a href="{cta_url}" class="btn">View Thread &amp; Respond →</a>
<hr class="divider">
<p class="muted">You're getting this because someone started a thread about your team in a group you're in.</p>
""")
    text = (
        f"{reporter.display_name} filed a {label} thread on your "
        f"{team.city} {team.name} in {group.name}. "
        f"View it: {cta_url}"
    )
    return _send(target_user.email, subject, html, text)


# ── Keep old name as alias for callers in incident_service ───────────────────
send_incident_notification = send_thread_notification


# ── Group invite ──────────────────────────────────────────────────────────────

def send_invite_email(to_email, from_user, group, invite_url):
    subject = f"{from_user.display_name} invited you to {group.name} on FriedSports"
    html = _wrap(f"""
<p>Hey,</p>
<p><strong style="color:#fff">{from_user.display_name}</strong> invited you to join
<strong style="color:#fff">{group.name}</strong> on FriedSports.</p>
<p>FriedSports is where sports fans hold each other accountable for their team's L's.
Threads, trash talk, and permanent receipts.</p>
<a href="{invite_url}" class="btn">Join {group.name} →</a>
<hr class="divider">
<p class="muted">Don't have an account? The link above will walk you through signup.</p>
""")
    text = (
        f"{from_user.display_name} invited you to {group.name} on FriedSports. "
        f"Join here: {invite_url}"
    )
    return _send(to_email, subject, html, text)


# ── Admin broadcast ───────────────────────────────────────────────────────────

def send_broadcast(users, subject, body_html):
    """Send an email to a list of User objects.
    Sends individually so each email has the user's address in To:.
    Returns (sent_count, failed_count).
    """
    sent = 0
    failed = 0
    html = _wrap(body_html)
    for user in users:
        if user.email:
            ok = _send(user.email, subject, html)
            if ok:
                sent += 1
            else:
                failed += 1
    return sent, failed


# ── Password reset ────────────────────────────────────────────────────────────

def send_password_reset_email(user, reset_url):
    subject = "FriedSports — Reset your password"
    html = _wrap(f"""
<p>Hey <strong style="color:#fff">{user.display_name}</strong>,</p>
<p>A password reset was requested for your FriedSports account.</p>
<a href="{reset_url}" class="btn">Reset Password →</a>
<p style="font-size:13px;color:#72728a">This link expires in 1 hour. If you didn't request a reset, ignore this.</p>
""")
    text = f"Reset your FriedSports password: {reset_url}"
    return _send(user.email, subject, html, text)


# ── Admin notification ────────────────────────────────────────────────────────

def send_admin_notification(subject, body):
    admin_email = current_app.config.get("ADMIN_EMAIL")
    if not admin_email:
        return False
    html = _wrap(f"<p>{body}</p>")
    return _send(admin_email, f"[FriedSports Admin] {subject}", html, body)


# ── Magic link helper (used internally + by routes) ──────────────────────────

def _make_magic_link(user_id, next_url, expires_minutes=60 * 24):
    """Create a LoginToken for magic-link auth. Returns the token string.
    Caller must ensure db.session.commit() is called before the token is used.
    """
    from app.models import db, LoginToken
    tok = LoginToken(
        user_id=user_id,
        token=secrets.token_urlsafe(32),
        purpose="magic_link",
        next_url=next_url,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
    )
    db.session.add(tok)
    db.session.flush()
    return tok.token
