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
# Uses table + inline styles so the dark background survives Gmail's style-strip.
# bgcolor="#0f0f17" is the Outlook-compatible fallback; inline style covers everything else.

def _wrap(body_html):
    """Wrap content in a dark-themed email shell (table layout, all inline styles)."""
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background-color:#0f0f17;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#0f0f17"
       style="background-color:#0f0f17;border-collapse:collapse;">
  <tr>
    <td align="center" style="padding:32px 16px;background-color:#0f0f17;">
      <table width="520" cellpadding="0" cellspacing="0" border="0"
             style="max-width:520px;width:100%;border-collapse:collapse;">
        <tr>
          <td style="padding:0 0 28px;">
            <span style="font-size:13px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#d93348;">
              <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background-color:#d93348;margin-right:5px;vertical-align:middle;"></span>FRIEDSPORTS
            </span>
          </td>
        </tr>
        <tr>
          <td style="font-size:15px;line-height:1.65;color:#c8c8d8;">
            {body_html}
            <p style="font-size:12px;color:#72728a;margin:24px 0 0;line-height:1.5;">This email was sent by FriedSports. If you didn't expect it, ignore it.</p>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


# ── Welcome email ────────────────────────────────────────────────────────────

def send_welcome_email(user):
    subject = "Welcome to FriedSports 🔥"
    html = _wrap(f"""
<p>Hey <strong style="color:#fff">{user.display_name}</strong>,</p>
<p>Welcome to FriedSports — where your team's disasters become your group's entertainment.</p>
<p>Find your friends, start a group, and start holding each other accountable.</p>
<a href="https://friedsports.com/dashboard" style="display:inline-block;background:#d93348;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:600;font-size:14px;margin:8px 0 24px;line-height:1;">Go to Dashboard →</a>
<hr style="border:none;border-top:1px solid #2a2a3a;margin:24px 0;">
<p style="font-size:12px;color:#72728a;margin:16px 0 0;line-height:1.5;">You're receiving this because you just created a FriedSports account.</p>
""")
    text = f"Hey {user.display_name}, welcome to FriedSports. https://friedsports.com"
    return _send(user.email, subject, html, text)


# ── Sign-in code ─────────────────────────────────────────────────────────────

def send_signin_code(user, code):
    subject = "Your FriedSports sign-in code"
    html = _wrap(f"""
<p>Here's your sign-in code for FriedSports. It expires in 15 minutes.</p>
<div style="background:#1a1a2e;border:1px solid #2a2a3a;border-radius:6px;padding:20px;text-align:center;margin:16px 0 24px;"><span style="font-size:36px;font-weight:700;letter-spacing:.3em;color:#ffffff;font-family:monospace;display:block;">{code}</span></div>
<p style="font-size:13px;color:#72728a">If you didn't request this, you can safely ignore this email.</p>
""")
    text = f"Your FriedSports sign-in code is: {code}. It expires in 15 minutes."
    return _send(user.email, subject, html, text)


def send_signup_code(user, code):
    """Sent after sign-up form submission to verify the new account's email."""
    subject = "Verify your FriedSports account"
    html = _wrap(f"""
<p>Hey <strong style="color:#fff">{user.display_name}</strong>,</p>
<p>You're almost in. Enter the code below to verify your email and finish creating your account.</p>
<div style="background:#1a1a2e;border:1px solid #2a2a3a;border-radius:6px;padding:20px;text-align:center;margin:16px 0 24px;"><span style="font-size:36px;font-weight:700;letter-spacing:.3em;color:#ffffff;font-family:monospace;display:block;">{code}</span></div>
<p style="font-size:13px;color:#72728a">This code expires in 15 minutes. If you didn't sign up for FriedSports, ignore this.</p>
""")
    text = f"Your FriedSports verification code is: {code}. Expires in 15 minutes."
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
<a href="{cta_url}" style="display:inline-block;background:#d93348;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:600;font-size:14px;margin:8px 0 24px;line-height:1;">View Thread &amp; Respond →</a>
<hr style="border:none;border-top:1px solid #2a2a3a;margin:24px 0;">
<p style="font-size:12px;color:#72728a;margin:16px 0 0;line-height:1.5;">You're getting this because someone started a thread about your team in a group you're in.</p>
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
    subject = f"{from_user.display_name} wants you in on FriedSports — your teams deserve better"
    html = _wrap(f"""
<p>Hey,</p>
<p><strong style="color:#fff">{from_user.display_name}</strong> wants you in
<strong style="color:#fff">{group.name}</strong> on FriedSports — and honestly, your teams have earned this.</p>
<hr style="border:none;border-top:1px solid #2a2a3a;margin:24px 0;">
<p style="font-size:1rem;font-weight:700;color:#fff;margin-bottom:8px">What is FriedSports?</p>
<p>FriedSports is the sports accountability app your group chat was always trying to be.
When your team blows a 20-point lead, gets blown out, or just embarrasses you — someone in your group
files a <em>formal report</em>. A thread opens. The receipts start piling up.</p>
<p>It's trash talk with structure. Evidence-based slander. Permanent receipts that follow your
team's worst performances forever.</p>
<p style="color:#fff;font-weight:600">Think: a courtroom for sports takes. Everyone's a prosecutor. Your teams are always the defendant.</p>
<hr style="border:none;border-top:1px solid #2a2a3a;margin:24px 0;">
<p>Join <strong style="color:#fff">{group.name}</strong> and find out what your friends already know about your team.</p>
<a href="{invite_url}" style="display:inline-block;background:#d93348;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:600;font-size:14px;margin:8px 0 24px;line-height:1;">Accept the Charges →</a>
<p style="font-size:12px;color:#72728a;margin:16px 0 0;line-height:1.5;">No account yet? The link above will get you set up in under a minute. Requires an email address and a willingness to face the truth about your team.</p>
""")
    text = (
        f"{from_user.display_name} invited you to {group.name} on FriedSports — "
        f"the sports accountability app. Join here: {invite_url}"
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
<a href="{reset_url}" style="display:inline-block;background:#d93348;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:600;font-size:14px;margin:8px 0 24px;line-height:1;">Reset Password →</a>
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


# ── Support ticket emails ─────────────────────────────────────────────────────

def send_ticket_received_user(ticket):
    """Confirm to the user that their ticket was received."""
    base_url = "https://friedsports.com"
    token = _make_magic_link(ticket.user_id, f"/support/{ticket.uid}")
    cta_url = f"{base_url}/auth/magic/{token}"
    html = _wrap(f"""
<p>Hey <strong style="color:#fff">{ticket.user.display_name}</strong>,</p>
<p>We got your report. Here's your reference number:</p>
<div style="background:#1a1a2e;border:1px solid #2a2a3a;border-radius:6px;padding:20px;text-align:center;margin:16px 0 24px;"><span style="font-size:1.4rem;font-weight:700;letter-spacing:.15em;color:#ffffff;font-family:monospace;display:block;">{ticket.uid}</span></div>
<p><strong style="color:#fff">Subject:</strong> {ticket.subject}</p>
<p>We'll look into it and keep you posted. You'll get an email when the status changes.</p>
<a href="{cta_url}" style="display:inline-block;background:#d93348;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:600;font-size:14px;margin:8px 0 24px;line-height:1;">View Your Ticket →</a>
<hr style="border:none;border-top:1px solid #2a2a3a;margin:24px 0;">
<p style="font-size:12px;color:#72728a;margin:16px 0 0;line-height:1.5;">Keep this email for your reference number.</p>
""")
    text = f"Support ticket {ticket.uid} received: {ticket.subject}. View it: {cta_url}"
    return _send(ticket.user.email, f"Got it — {ticket.uid} received", html, text)


def send_ticket_received_admin(ticket):
    """Notify admin that a new support ticket was submitted."""
    admin_email = current_app.config.get("ADMIN_EMAIL")
    if not admin_email:
        current_app.logger.info(f"[admin email skipped — ADMIN_EMAIL not set] ticket {ticket.uid}")
        return False
    base_url = "https://friedsports.com"
    cta_url = f"{base_url}/admin-tools"
    html = _wrap(f"""
<p>New support ticket submitted.</p>
<p>
  <strong style="color:#fff">Ref:</strong> {ticket.uid}<br>
  <strong style="color:#fff">From:</strong> {ticket.user.display_name} ({ticket.user.email})<br>
  <strong style="color:#fff">Category:</strong> {ticket.category.replace('_', ' ').title()}<br>
  <strong style="color:#fff">Subject:</strong> {ticket.subject}
</p>
<div style="background:#1a1a2e;border-left:3px solid #d93348;padding:10px 14px;border-radius:0 4px 4px 0;margin:0 0 20px">
  <p style="margin:0;color:#c8c8d8;font-style:italic">{ticket.description}</p>
</div>
<a href="{cta_url}" style="display:inline-block;background:#d93348;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:600;font-size:14px;margin:8px 0 24px;line-height:1;">Manage Ticket →</a>
""")
    text = f"New ticket {ticket.uid} from {ticket.user.display_name}: {ticket.subject}"
    return _send(admin_email, f"[Support] {ticket.uid} — {ticket.subject}", html, text)


def send_ticket_status_update(ticket):
    """Notify user of a status change (in_progress or resolved)."""
    base_url = "https://friedsports.com"
    token = _make_magic_link(ticket.user_id, f"/support/{ticket.uid}")
    cta_url = f"{base_url}/auth/magic/{token}"

    if ticket.status == "in_progress":
        subject = f"We're on it — {ticket.uid} is being investigated"
        status_line = "Your issue is currently <strong style=\"color:#f0a500\">In Progress</strong>."
    else:  # resolved
        subject = f"Resolved — your issue {ticket.uid} has been closed"
        status_line = "Your issue has been marked <strong style=\"color:#34c77b\">Resolved</strong>."

    note_block = ""
    if ticket.admin_note:
        note_block = f"""
<p style="margin:0 0 8px;font-size:0.8rem;color:#72728a;text-transform:uppercase;letter-spacing:.06em;">Response from FriedSports</p>
<div style="background:#1a1a2e;border-left:3px solid #34c77b;padding:10px 14px;border-radius:0 4px 4px 0;margin:0 0 20px">
  <p style="margin:0;color:#c8c8d8">{ticket.admin_note}</p>
</div>"""

    html = _wrap(f"""
<p>Hey <strong style="color:#fff">{ticket.user.display_name}</strong>,</p>
<p>Update on your support ticket <strong style="color:#fff">{ticket.uid}</strong> — {ticket.subject}</p>
<p>{status_line}</p>
{note_block}
<a href="{cta_url}" style="display:inline-block;background:#d93348;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:600;font-size:14px;margin:8px 0 24px;line-height:1;">View Ticket →</a>
""")
    text = f"Update on {ticket.uid}: {ticket.status_label}. View: {cta_url}"
    return _send(ticket.user.email, subject, html, text)


# ── Missed notifications email ───────────────────────────────────────────────

def send_missed_notifications_email(user, count):
    """Sent when a user accumulates 10 unread in-app notifications."""
    base_url = "https://friedsports.com"
    token = _make_magic_link(user.id, "/notifications")
    cta_url = f"{base_url}/auth/magic/{token}"
    subject = f"👀 You've got {count} things waiting for you on FriedSports"
    html = _wrap(f"""
<p>Hey <strong style="color:#fff">{user.display_name}</strong>,</p>
<p>While you were out living your best life, your groups have been <em>busy</em>.</p>
<p>You've got <strong style="color:#d93348;font-size:1.1rem">{count} unread notifications</strong>
waiting for you — and if history is any guide, at least one of them involves your team doing
something embarrassing.</p>
<p>Come see what you missed before the receipts get worse.</p>
<a href="{cta_url}" style="display:inline-block;background:#d93348;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:600;font-size:14px;margin:8px 0 24px;line-height:1;">Check Your Notifications →</a>
<hr style="border:none;border-top:1px solid #2a2a3a;margin:24px 0;">
<p style="font-size:12px;color:#72728a;margin:16px 0 0;line-height:1.5;">You're getting this because you haven't logged in while your groups have been active. Tap the button above to go straight in.</p>
""")
    text = (
        f"Hey {user.display_name}, you have {count} unread notifications on FriedSports. "
        f"Check them here: {cta_url}"
    )
    return _send(user.email, subject, html, text)


# ── Friend request email ─────────────────────────────────────────────────────

def send_friend_request_email(from_user, to_user):
    """Notify a user when they receive a new friend request."""
    cta_url = "https://friedsports.com/notifications"
    subject = f"{from_user.shown_name} wants to connect on FriedSports"
    html = _wrap(f"""
<p>Hey <strong style="color:#fff">{to_user.shown_name}</strong>,</p>
<p><strong style="color:#fff">{from_user.shown_name}</strong> sent you a friend request on FriedSports.</p>
<p>Accept to see each other's activity and add each other to groups.</p>
<a href="{cta_url}" style="display:inline-block;background:#d93348;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:600;font-size:14px;margin:8px 0 24px;line-height:1;">View Request →</a>
<p style="font-size:12px;color:#72728a;margin:16px 0 0;line-height:1.5;">You're getting this because someone on FriedSports wants to connect with you.</p>
""")
    text = f"{from_user.shown_name} sent you a friend request on FriedSports. View it: {cta_url}"
    return _send(to_user.email, subject, html, text)


# ── Admin-initiated user email actions ───────────────────────────────────────

def send_admin_password_reset(user, reset_url):
    """Admin-initiated password reset link sent to user."""
    subject = "Reset your FriedSports password"
    html = _wrap(f"""
<p>Hey <strong style="color:#fff">{user.display_name}</strong>,</p>
<p>A password reset link has been created for your FriedSports account by an admin.</p>
<a href="{reset_url}" style="display:inline-block;background:#d93348;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:600;font-size:14px;margin:8px 0 24px;line-height:1;">Set New Password →</a>
<p style="font-size:13px;color:#72728a">This link expires in 1 hour. If you didn't expect this, you can safely ignore it.</p>
""")
    text = f"Reset your FriedSports password: {reset_url}. Expires in 1 hour."
    return _send(user.email, subject, html, text)


def send_username_change_prompt(user, settings_url):
    """Admin-initiated prompt to update username."""
    subject = "Action needed — update your FriedSports username"
    html = _wrap(f"""
<p>Hey <strong style="color:#fff">{user.display_name}</strong>,</p>
<p>You've been asked to update your username on FriedSports. Tap below to go to your settings and make the change.</p>
<a href="{settings_url}" style="display:inline-block;background:#d93348;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:600;font-size:14px;margin:8px 0 24px;line-height:1;">Go to Settings →</a>
<p style="font-size:13px;color:#72728a">This link logs you in automatically. If you have questions, reply to this email.</p>
""")
    text = f"Please update your FriedSports username at: {settings_url}"
    return _send(user.email, subject, html, text)


def send_email_change_prompt(user, settings_url):
    """Admin-initiated prompt to update email address."""
    subject = "Action needed — update your FriedSports email address"
    html = _wrap(f"""
<p>Hey <strong style="color:#fff">{user.display_name}</strong>,</p>
<p>You've been asked to update the email address on your FriedSports account. Tap below to go to your settings.</p>
<a href="{settings_url}" style="display:inline-block;background:#d93348;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:600;font-size:14px;margin:8px 0 24px;line-height:1;">Go to Settings →</a>
<p style="font-size:13px;color:#72728a">This link logs you in automatically. If you have questions, reply to this email.</p>
""")
    text = f"Please update your FriedSports email address at: {settings_url}"
    return _send(user.email, subject, html, text)


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
