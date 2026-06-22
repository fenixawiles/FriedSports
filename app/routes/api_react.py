"""
api_react.py — JSON API endpoints for the React frontend.

All routes live under /api/ and return JSON.
Auth: Flask-Login session cookies (withCredentials on the React side).
"""
import string, secrets
from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.orm import joinedload

from ..models import (
    db, User, LoginToken, Group, GroupMember, GameThread, GameThreadMessage,
    MessageReaction, IncidentReport, GameEvent, GroupTrigger, Team,
    UserFavoriteTeam, Notification, FriendRequest, SupportTicket,
    Receipt, DeviceToken,
)

bp = Blueprint("api_react", __name__, url_prefix="/api")


# ── Helpers ──────────────────────────────────────────────────────────────────

def ok(**kwargs):
    return jsonify({"ok": True, **kwargs})

def err(msg, status=400):
    return jsonify({"error": msg}), status

def _serialize_user(u):
    return {
        "id":                  u.id,
        "uid":                 u.uid,
        "name":                u.shown_name,
        "display_name":        u.display_name,
        "first_name":          u.first_name or "",
        "last_name":           u.last_name  or "",
        "display_preference":  u.display_preference,
        "has_completed_profile": u.has_completed_profile,
        "email":               u.email,
        "avatar_url":          u.avatar_url or "",
        "is_admin":            u.is_admin,
    }

def _serialize_thread(t, last_msg=None):
    ir = None
    if t.group_trigger and t.group_trigger.game_event:
        ir_obj = t.group_trigger.game_event.incident_report
        if ir_obj:
            ir = ir_obj.incident_type
    return {
        "id":            t.id,
        "title":         t.title,
        "status":        t.status,
        "group_id":      t.group_id,
        "group_name":    t.group.name if t.group else "",
        "target_user_id":   t.target_user_id,
        "target_user_name": t.target_user.shown_name if t.target_user else "",
        "team_abbr":     t.target_team.abbreviation if t.target_team else "",
        "team_name":     t.target_team.name if t.target_team else "",
        "team_color":    t.target_team.primary_color if t.target_team else "#333",
        "incident_type": ir,
        "created_at":    t.created_at.isoformat() if t.created_at else None,
        "last_msg":      {
            "body":       last_msg.body if last_msg else None,
            "created_at": last_msg.created_at.isoformat() if last_msg and last_msg.created_at else None,
        } if last_msg else None,
    }

def _serialize_message(msg, current_user_id):
    if msg.is_deleted:
        return {
            "id": msg.id, "message_type": "system",
            "body": "This message was deleted.",
            "author": None, "is_mine": False,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
            "reactions": {}, "user_reactions": [], "can_delete": False,
        }
    return {
        "id":            msg.id,
        "message_type":  msg.message_type,
        "body":          msg.body,
        "author":        msg.author.shown_name if msg.author else None,
        "author_id":     msg.user_id,
        "is_mine":       msg.user_id == current_user_id,
        "created_at":    msg.created_at.isoformat() if msg.created_at else None,
        "reactions":     msg.reaction_counts(),
        "user_reactions": msg.user_reaction(current_user_id),
        "can_delete":    msg.user_id == current_user_id,
    }


# ── Auth ─────────────────────────────────────────────────────────────────────

@bp.route("/auth/me")
def auth_me():
    if not current_user.is_authenticated:
        return err("Unauthorized", 401)
    return ok(user=_serialize_user(current_user))


@bp.route("/auth/signup", methods=["POST"])
def auth_signup():
    d = request.get_json(silent=True) or {}
    required = ["first_name", "last_name", "display_name", "email", "password"]
    for f in required:
        if not d.get(f, "").strip():
            return err(f"{f} is required")

    if not d.get("agree_terms"):
        return err("You must agree to the Terms and community guidelines to sign up.")

    if User.query.filter_by(email=d["email"].lower().strip()).first():
        return err("An account with that email already exists")

    u = User(
        first_name=d["first_name"].strip(),
        last_name=d["last_name"].strip(),
        display_name=d["display_name"].strip(),
        display_preference=d.get("display_preference", "username"),
        email=d["email"].lower().strip(),
        agreed_to_terms_at=datetime.now(timezone.utc),
    )
    u.set_password(d["password"])
    db.session.add(u)
    db.session.flush()

    # Check admin
    admin_email = current_app.config.get("ADMIN_EMAIL", "")
    if admin_email and u.email == admin_email.lower():
        u.role = "admin"

    # Send OTP
    token = LoginToken(
        user_id=u.id,
        token=secrets.token_urlsafe(16),
        purpose="signup_code",
        code="".join(secrets.choice(string.digits) for _ in range(8)),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.session.add(token)
    db.session.commit()

    _send_code_email(u.email, token.code)
    return ok(next="verify-code"), 201


@bp.route("/auth/login", methods=["POST"])
def auth_login():
    d = request.get_json(silent=True) or {}
    email = d.get("email", "").lower().strip()
    password = d.get("password", "")
    u = User.query.filter_by(email=email).first()
    if not u or not u.check_password(password):
        return err("Invalid email or password", 401)

    admin_email = current_app.config.get("ADMIN_EMAIL", "").strip().lower()
    if admin_email and u.email == admin_email:
        u.role = "admin"
        db.session.commit()

    login_user(u, remember=True)
    next_url = "/onboarding" if not u.has_completed_profile else "/dashboard"
    return ok(user=_serialize_user(u), next=next_url)


@bp.route("/auth/send-code", methods=["POST"])
def auth_send_code():
    d = request.get_json(silent=True) or {}
    email = d.get("email", "").lower().strip()
    u = User.query.filter_by(email=email).first()
    if not u:
        # Don't reveal whether the email exists
        return ok()
    token = LoginToken(
        user_id=u.id,
        token=secrets.token_urlsafe(16),
        purpose="signin_code",
        code="".join(secrets.choice(string.digits) for _ in range(8)),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.session.add(token)
    db.session.commit()
    _send_code_email(email, token.code)
    return ok()


@bp.route("/auth/verify-code", methods=["POST"])
def auth_verify_code():
    d = request.get_json(silent=True) or {}
    email = d.get("email", "").lower().strip()
    code  = d.get("code", "").strip()
    u = User.query.filter_by(email=email).first()
    if not u:
        return err("Invalid code", 401)

    token = LoginToken.query.filter_by(
        user_id=u.id, code=code, used_at=None
    ).filter(LoginToken.expires_at > datetime.now(timezone.utc)).first()

    if not token:
        return err("Invalid or expired code", 401)

    token.used_at = datetime.now(timezone.utc)
    u.email_verified = True
    db.session.commit()

    login_user(u, remember=True)
    next_url = "/onboarding" if not u.has_completed_profile else "/dashboard"
    return ok(user=_serialize_user(u), next=next_url)


@bp.route("/auth/logout", methods=["POST"])
@login_required
def auth_logout():
    logout_user()
    return ok()


@bp.route("/auth/reset-password/<token>", methods=["POST"])
def auth_reset_password(token):
    d = request.get_json(silent=True) or {}
    password = d.get("password", "")
    if len(password) < 6:
        return err("Password must be at least 6 characters")

    tok = LoginToken.query.filter_by(
        token=token, purpose="password_reset", used_at=None
    ).filter(LoginToken.expires_at > datetime.now(timezone.utc)).first()

    if not tok:
        return err("Invalid or expired reset link", 400)

    u = User.query.get(tok.user_id)
    if not u:
        return err("User not found", 404)

    u.set_password(password)
    tok.used_at = datetime.now(timezone.utc)
    db.session.commit()
    login_user(u, remember=True)
    return ok(user=_serialize_user(u))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@bp.route("/dashboard")
@login_required
def dashboard():
    from sqlalchemy import text
    uid = current_user.id

    # Query 1 — groups + member role (single JOIN, one round trip)
    memberships = (
        GroupMember.query
        .filter_by(user_id=uid)
        .options(joinedload(GroupMember.group))
        .all()
    )
    if not memberships:
        return ok(groups=[], active_threads=[], msg_counts={})

    group_ids = [m.group_id for m in memberships]
    groups = [
        {"group": {"id": m.group.id, "name": m.group.name, "league_scope": m.group.league_scope},
         "member": {"role": m.role}}
        for m in memberships if m.group
    ]

    # Query 2 — active threads + message counts in one shot (was 2 separate queries)
    rows = db.session.execute(text("""
        SELECT
            gt.id,
            gt.title,
            g.name  AS group_name,
            COUNT(msg.id) FILTER (
                WHERE msg.message_type = 'user' AND msg.is_deleted = false
            ) AS msg_count
        FROM game_threads gt
        LEFT JOIN groups g              ON g.id = gt.group_id
        LEFT JOIN game_thread_messages msg ON msg.thread_id = gt.id
        WHERE gt.group_id = ANY(:gids) AND gt.status = 'active'
        GROUP BY gt.id, gt.title, g.name
        ORDER BY gt.updated_at DESC
    """), {"gids": group_ids}).fetchall()

    return ok(
        groups=groups,
        active_threads=[{"id": r.id, "title": r.title, "group_name": r.group_name or ""} for r in rows],
        msg_counts={r.id: r.msg_count for r in rows},
    )


@bp.route("/onboarding")
@login_required
def onboarding_get():
    league_labels = {
        "NBA": "Basketball (NBA)", "NFL": "Football (NFL)", "MLB": "Baseball (MLB)",
        "NHL": "Hockey (NHL)", "EPL": "Premier League", "FIFA": "International Soccer",
        "F1": "Formula 1", "PGA": "Golf (PGA)",
    }
    # One query instead of 8 separate per-league queries (~1.2 s saved on Neon).
    all_teams = Team.query.order_by(Team.name).all()
    teams_by_league = {}
    for t in all_teams:
        teams_by_league.setdefault(t.league, []).append(
            {"id": t.id, "name": t.name, "city": t.city or "",
             "abbreviation": t.abbreviation, "primary_color": t.primary_color}
        )
    return ok(teams_by_league=teams_by_league, league_labels=league_labels)


@bp.route("/onboarding", methods=["POST"])
@login_required
def onboarding_post():
    d = request.get_json(silent=True) or {}
    leagues = ["NBA", "NFL", "MLB", "NHL", "EPL", "FIFA", "F1", "PGA"]
    for league in leagues:
        key = f"{league.lower()}_team_id"
        team_id = d.get(key)
        if team_id:
            uft = UserFavoriteTeam.query.filter_by(
                user_id=current_user.id, league=league
            ).first()
            if uft:
                uft.team_id = int(team_id)
            else:
                uft = UserFavoriteTeam(
                    user_id=current_user.id, league=league, team_id=int(team_id)
                )
                db.session.add(uft)
    current_user.has_completed_profile = True
    db.session.commit()
    return ok(user=_serialize_user(current_user))


@bp.route("/profile/complete", methods=["POST"])
@login_required
def profile_complete():
    d = request.get_json(silent=True) or {}
    if d.get("first_name"): current_user.first_name = d["first_name"].strip()
    if d.get("last_name"):  current_user.last_name  = d["last_name"].strip()
    if d.get("display_preference"): current_user.display_preference = d["display_preference"]
    current_user.has_completed_profile = True
    db.session.commit()
    return ok(user=_serialize_user(current_user))


@bp.route("/settings")
@login_required
def settings_get():
    league_labels = {
        "NBA": "Basketball (NBA)", "NFL": "Football (NFL)", "MLB": "Baseball (MLB)",
        "NHL": "Hockey (NHL)", "EPL": "Premier League", "FIFA": "International Soccer",
        "F1": "Formula 1", "PGA": "Golf (PGA)",
    }
    # One query instead of 8 separate per-league queries (~1.2 s saved on Neon).
    all_teams = Team.query.order_by(Team.name).all()
    teams_by_league = {}
    for t in all_teams:
        teams_by_league.setdefault(t.league, []).append(
            {"id": t.id, "name": t.name, "city": t.city or "",
             "abbreviation": t.abbreviation, "primary_color": t.primary_color}
        )
    fav_teams = {}
    for uft in current_user.favorite_teams:
        fav_teams[uft.league] = {"id": uft.team_id, "abbreviation": uft.team.abbreviation if uft.team else ""}

    return ok(
        user=_serialize_user(current_user),
        teams_by_league=teams_by_league,
        league_labels=league_labels,
        fav_teams=fav_teams,
    )


@bp.route("/settings", methods=["POST"])
@login_required
def settings_post():
    d = request.get_json(silent=True) or {}
    if d.get("first_name"):  current_user.first_name = d["first_name"].strip()
    if d.get("last_name"):   current_user.last_name  = d["last_name"].strip()
    if d.get("display_name"): current_user.display_name = d["display_name"].strip()
    if d.get("display_preference"): current_user.display_preference = d["display_preference"]
    if d.get("avatar_url") is not None: current_user.avatar_url = d["avatar_url"].strip() or None

    # Password change
    password_changed = False
    if d.get("new_password"):
        if not d.get("current_password"):
            return err("Current password is required to change password")
        if not current_user.check_password(d["current_password"]):
            return err("Current password is incorrect")
        if d["new_password"] != d.get("confirm_password", ""):
            return err("New passwords do not match")
        if len(d["new_password"]) < 6:
            return err("Password must be at least 6 characters")
        current_user.set_password(d["new_password"])
        password_changed = True

    # Which devices stay signed in after a password change. Rotating the session
    # token invalidates every other device's cookie (see User.get_id/load_user).
    session_scope = d.get("session_scope", "")
    if password_changed and session_scope in ("this_device", "sign_out_all"):
        current_user.session_token = secrets.token_hex(16)

    # Team preferences
    leagues = ["NBA", "NFL", "MLB", "NHL", "EPL", "FIFA", "F1", "PGA"]
    for league in leagues:
        key = f"{league.lower()}_team_id"
        if key in d:
            team_id = d[key]
            uft = UserFavoriteTeam.query.filter_by(
                user_id=current_user.id, league=league
            ).first()
            if team_id:
                if uft:
                    uft.team_id = int(team_id)
                else:
                    db.session.add(UserFavoriteTeam(
                        user_id=current_user.id, league=league, team_id=int(team_id)
                    ))
            elif uft:
                db.session.delete(uft)

    db.session.commit()

    if password_changed and session_scope == "sign_out_all":
        logout_user()
        return ok(signed_out=True)
    if password_changed and session_scope == "this_device":
        # Re-issue this device's cookie with the new token so only it survives.
        login_user(current_user, remember=True)

    return ok(user=_serialize_user(current_user))


@bp.route("/settings/delete-account", methods=["POST"])
@login_required
def delete_account():
    d = request.get_json(silent=True) or {}
    if not current_user.check_password(d.get("password", "")):
        return err("Incorrect password", 401)
    from ..routes.admin import _cascade_delete_user
    user_id = current_user.id
    # The cascade only clears child rows + flushes; we must delete the user row
    # AND commit, or the whole transaction is rolled back on teardown and the
    # account (email included) silently survives.
    try:
        _cascade_delete_user(user_id)
        u = db.session.get(User, user_id)
        if u:
            db.session.delete(u)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Account deletion failed for user %s", user_id)
        return err("Account deletion failed. Please contact support.", 500)
    if db.session.get(User, user_id) is not None:
        return err("Account deletion did not complete. Please contact support.", 500)
    logout_user()
    return ok()


# ── Notifications ─────────────────────────────────────────────────────────────

@bp.route("/notifications")
@login_required
def notifications():
    all_notifs = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(100)
        .all()
    )
    messages = []
    invites  = []
    for n in all_notifs:
        item = {
            "id": n.id,
            "message": n.message,
            "link_url": n.link_url or "/dashboard",
            "is_read":  n.is_read,
            "created_at": n.created_at.strftime("%-d %b at %-I:%M %p") if n.created_at else "",
        }
        if n.type in ("group_invite",):
            invites.append(item)
        else:
            messages.append(item)

    pending_fr = (
        FriendRequest.query
        .filter_by(to_user_id=current_user.id, status="pending")
        .options(joinedload(FriendRequest.from_user))
        .all()
    )
    fr_list = [
        {"id": fr.id, "from_user": {"id": fr.from_user.id, "name": fr.from_user.shown_name, "uid": fr.from_user.uid}}
        for fr in pending_fr
    ]

    unread = sum(1 for n in all_notifs if not n.is_read)
    return ok(messages=messages, invites=invites, pending_fr=fr_list, unread_count=unread)


@bp.route("/notifications/mark-read", methods=["POST"])
@login_required
def notifications_mark_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return ok()


# ── Groups ────────────────────────────────────────────────────────────────────

@bp.route("/groups", methods=["POST"])
@login_required
def create_group():
    d = request.get_json(silent=True) or {}
    name = d.get("name", "").strip()
    if not name:
        return err("Group name is required")
    if len(name) > 100:
        return err("Group name is too long")

    code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    g = Group(
        name=name,
        owner_id=current_user.id,
        league_scope=d.get("league_scope", "MULTI"),
        privacy=d.get("privacy", "private"),
        invite_code=code,
    )
    db.session.add(g)
    db.session.flush()
    db.session.add(GroupMember(group_id=g.id, user_id=current_user.id, role="owner"))
    db.session.commit()
    return ok(group={"id": g.id, "name": g.name}), 201


def _find_group_by_code(code):
    """Case-insensitive invite code lookup — handles both old mixed-case codes
    (generated by secrets.token_urlsafe) and new uppercase-only codes."""
    return Group.query.filter(
        db.func.upper(Group.invite_code) == code.upper()
    ).first()


@bp.route("/groups/join/<code>")
def join_info(code):
    g = _find_group_by_code(code)
    if not g:
        return err("Invalid invite code", 404)
    from sqlalchemy import text as _text
    member_count = db.session.execute(
        _text("SELECT COUNT(*) FROM group_members WHERE group_id = :gid"),
        {"gid": g.id},
    ).scalar()
    already = g.is_member(current_user.id) if current_user.is_authenticated else False
    return ok(
        group={"id": g.id, "name": g.name, "league_scope": g.league_scope},
        member_count=member_count,
        already_member=already,
    )


@bp.route("/groups/join/<code>", methods=["POST"])
@login_required
def join_group(code):
    g = _find_group_by_code(code)
    if not g:
        return err("Invalid invite code", 404)
    if g.is_member(current_user.id):
        return ok(group_id=g.id)
    db.session.add(GroupMember(group_id=g.id, user_id=current_user.id, role="member"))
    from app.services.activity import record_event
    record_event(g.id, current_user.id, "member_joined")
    db.session.commit()
    return ok(group_id=g.id)


@bp.route("/groups/<int:group_id>")
@login_required
def get_group(group_id):
    from sqlalchemy import text as _text
    g = Group.query.get_or_404(group_id)
    member = g.get_member(current_user.id)

    # Fetch receipts and member count in parallel without extra ORM traversals.
    receipts = (
        Receipt.query.filter_by(group_id=group_id)
        .order_by(Receipt.created_at.desc()).limit(5).all()
    )
    member_count = db.session.execute(
        _text("SELECT COUNT(*) FROM group_members WHERE group_id = :gid"),
        {"gid": group_id},
    ).scalar()

    return ok(
        group={
            "id": g.id, "name": g.name,
            "league_scope": g.league_scope,
            "invite_code": g.invite_code,
            "member_count": member_count,
        },
        member={"role": member.role, "mute_notifications": member.mute_notifications} if member else None,
        receipts=[
            {"public_slug": r.public_slug, "title": r.title, "shame_points": r.shame_points}
            for r in receipts
        ],
    )


@bp.route("/groups/<int:group_id>/invite-email", methods=["POST"])
@login_required
def group_invite_email(group_id):
    g = Group.query.get_or_404(group_id)
    if not g.is_member(current_user.id):
        return err("Not a member", 403)
    d = request.get_json(silent=True) or {}
    email = d.get("email", "").strip()
    if not email:
        return err("Email is required")
    invite_url = f"{request.host_url.rstrip('/')}/groups/join/{g.invite_code}"
    try:
        import resend
        resend.Emails.send({
            "from": "FriedSports <noreply@friedsports.app>",
            "to": [email],
            "subject": f"{current_user.shown_name} invited you to {g.name}",
            "text": f"Join {g.name} on FriedSports: {invite_url}",
        })
    except Exception:
        pass
    return ok()


@bp.route("/groups/<int:group_id>/regenerate-invite", methods=["POST"])
@login_required
def regenerate_invite(group_id):
    g = Group.query.get_or_404(group_id)
    m = g.get_member(current_user.id)
    if not m or m.role not in ("owner", "admin"):
        return err("Not authorized", 403)
    g.invite_code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    db.session.commit()
    return ok(invite_code=g.invite_code)


@bp.route("/groups/<int:group_id>/mute", methods=["POST"])
@login_required
def mute_group(group_id):
    g = Group.query.get_or_404(group_id)
    m = g.get_member(current_user.id)
    if not m:
        return err("Not a member", 403)
    m.mute_notifications = not m.mute_notifications
    db.session.commit()
    return ok(muted=m.mute_notifications)


@bp.route("/groups/<int:group_id>/leave", methods=["POST"])
@login_required
def leave_group(group_id):
    g = Group.query.get_or_404(group_id)
    m = g.get_member(current_user.id)
    if not m:
        return err("Not a member", 403)
    if m.role == "owner":
        return err("Transfer ownership before leaving", 400)
    db.session.delete(m)
    db.session.commit()
    return ok()


@bp.route("/groups/<int:group_id>", methods=["DELETE"])
@login_required
def delete_group(group_id):
    g = Group.query.get_or_404(group_id)
    m = g.get_member(current_user.id)
    if not m or m.role != "owner":
        return err("Not authorized", 403)
    from ..routes.groups import _cascade_delete_group
    _cascade_delete_group(group_id)
    return ok()


@bp.route("/groups/<int:group_id>/remove/<int:user_id>", methods=["POST"])
@login_required
def remove_member(group_id, user_id):
    g = Group.query.get_or_404(group_id)
    m = g.get_member(current_user.id)
    if not m or m.role not in ("owner", "admin"):
        return err("Not authorized", 403)
    target = g.get_member(user_id)
    if not target:
        return err("Member not found", 404)
    db.session.delete(target)
    db.session.commit()
    return ok()


@bp.route("/groups/<int:group_id>/transfer-owner/<int:user_id>", methods=["POST"])
@login_required
def transfer_owner(group_id, user_id):
    g = Group.query.get_or_404(group_id)
    m = g.get_member(current_user.id)
    if not m or m.role != "owner":
        return err("Not authorized", 403)
    target = g.get_member(user_id)
    if not target:
        return err("Member not found", 404)
    m.role = "admin"
    target.role = "owner"
    g.owner_id = user_id
    db.session.commit()
    return ok()


@bp.route("/groups/<int:group_id>/report")
@login_required
def report_form(group_id):
    g = Group.query.get_or_404(group_id)
    m = g.get_member(current_user.id)
    if not m:
        return err("Not a member", 403)

    members = (
        GroupMember.query
        .filter_by(group_id=group_id)
        .options(joinedload(GroupMember.user))
        .all()
    )
    # One query instead of 8 separate per-league queries (~1.2 s saved on Neon).
    all_teams = Team.query.order_by(Team.name).all()
    teams_by_league = {}
    team_colors    = {}
    for t in all_teams:
        teams_by_league.setdefault(t.league, []).append(
            {"id": t.id, "name": t.name, "city": t.city or "",
             "abbreviation": t.abbreviation, "primary_color": t.primary_color}
        )
        team_colors[str(t.id)] = {"primary": t.primary_color, "abbr": t.abbreviation}

    user_fav_teams = {}
    for mem in members:
        if not mem.user: continue
        for uft in mem.user.favorite_teams:
            user_fav_teams.setdefault(str(mem.user_id), uft.team_id)

    return ok(
        group_name=g.name,
        members=[
            {"user_id": mem.user_id, "display_name": mem.user.shown_name}
            for mem in members if mem.user and mem.user_id != current_user.id
        ],
        teams_by_league=teams_by_league,
        team_colors=team_colors,
        user_fav_teams=user_fav_teams,
    )


@bp.route("/groups/<int:group_id>/report", methods=["POST"])
@login_required
def create_report(group_id):
    g = Group.query.get_or_404(group_id)
    m = g.get_member(current_user.id)
    if not m:
        return err("Not a member", 403)

    d = request.get_json(silent=True) or {}
    required = ["target_user_id", "target_team_id", "incident_type"]
    for f in required:
        if not d.get(f):
            return err(f"{f} is required")

    target_team = Team.query.get(int(d["target_team_id"]))
    if not target_team:
        return err("Team not found", 404)

    # Import and call the existing service
    from ..services.incident_service import create_incident_thread
    ir = IncidentReport(
        reporter_user_id=current_user.id,
        group_id=group_id,
        target_user_id=int(d["target_user_id"]),
        target_team_id=int(d["target_team_id"]),
        league=target_team.league,
        incident_type=d["incident_type"],
        severity=int(d.get("severity", 3)),
        reported_score_text=d.get("reported_score_text", "").strip() or None,
        description=d.get("description", "").strip() or None,
    )
    db.session.add(ir)
    db.session.flush()

    thread = create_incident_thread(ir)
    db.session.commit()
    return ok(thread_id=thread.id), 201


# ── Threads ───────────────────────────────────────────────────────────────────

@bp.route("/threads")
@login_required
def threads_list():
    from sqlalchemy import text
    uid = current_user.id

    # Query 1 — groups the user is in (for filter dropdown)
    memberships = (
        GroupMember.query
        .filter_by(user_id=uid)
        .options(joinedload(GroupMember.group))
        .all()
    )
    if not memberships:
        return ok(threads=[], groups=[], last_msgs={})

    group_ids = [m.group_id for m in memberships]
    groups    = [{"id": m.group_id, "name": m.group.name} for m in memberships if m.group]

    # Query 2 — all active thread data + last message in one CTE.
    # Replaces: threads query (deep 3-level joinedload) + last-msg subquery +
    #           last-msg fetch + redundant Group query  =  was 4 separate round trips.
    rows = db.session.execute(text("""
        WITH last_msgs AS (
            SELECT DISTINCT ON (thread_id)
                thread_id, body, created_at, user_id
            FROM game_thread_messages
            WHERE thread_id IN (
                SELECT id FROM game_threads
                WHERE group_id = ANY(:gids) AND status = 'active'
            )
            AND is_deleted = false
            ORDER BY thread_id, id DESC
        )
        SELECT
            gt.id,
            gt.title,
            gt.status,
            gt.group_id,
            gt.target_user_id,
            gt.created_at,
            gt.hot_score,
            g.name          AS group_name,
            te.abbreviation AS team_abbr,
            te.name         AS team_name,
            te.primary_color AS team_color,
            CASE
                WHEN u.display_preference = 'real_name'
                     AND u.first_name IS NOT NULL
                     AND u.last_name  IS NOT NULL
                THEN u.first_name || ' ' || u.last_name
                ELSE u.display_name
            END             AS target_user_name,
            ir.incident_type,
            lm.body         AS last_msg_body,
            lm.created_at   AS last_msg_at,
            CASE
                WHEN lmu.display_preference = 'real_name'
                     AND lmu.first_name IS NOT NULL
                     AND lmu.last_name  IS NOT NULL
                THEN lmu.first_name || ' ' || lmu.last_name
                ELSE lmu.display_name
            END             AS last_msg_author
        FROM game_threads gt
        LEFT JOIN groups g              ON g.id  = gt.group_id
        LEFT JOIN teams  te             ON te.id = gt.target_team_id
        LEFT JOIN users  u              ON u.id  = gt.target_user_id
        LEFT JOIN group_triggers  gtr   ON gtr.id = gt.group_trigger_id
        LEFT JOIN game_events     ge    ON ge.id  = gtr.game_event_id
        LEFT JOIN incident_reports ir   ON ir.id  = ge.incident_report_id
        LEFT JOIN last_msgs        lm   ON lm.thread_id = gt.id
        LEFT JOIN users            lmu  ON lmu.id = lm.user_id
        WHERE gt.group_id = ANY(:gids) AND gt.status = 'active'
        ORDER BY gt.updated_at DESC
    """), {"gids": group_ids}).fetchall()

    thread_ids = [r.id for r in rows]
    from app.services.activity import unread_map, message_counts, vote_count_map
    unread = unread_map(uid, thread_ids)
    counts = message_counts(thread_ids)
    votes  = vote_count_map(thread_ids)

    threads   = []
    last_msgs = {}
    for r in rows:
        threads.append({
            "id":               r.id,
            "title":            r.title,
            "status":           r.status,
            "group_id":         r.group_id,
            "group_name":       r.group_name   or "",
            "target_user_id":   r.target_user_id,
            "target_user_name": r.target_user_name or "",
            "team_abbr":        r.team_abbr    or "",
            "team_name":        r.team_name    or "",
            "team_color":       r.team_color   or "#333",
            "incident_type":    r.incident_type,
            "created_at":       r.created_at.isoformat() if r.created_at else None,
            "hot_score":        r.hot_score or 0,
            "reply_count":      counts.get(r.id, 0),
            "unread_count":     unread.get(r.id, 0),
            "votes":            votes.get(r.id, {"confirm": 0, "dismiss": 0, "redeem": 0}),
            "last_msg": {
                "body":       r.last_msg_body,
                "created_at": r.last_msg_at.isoformat() if r.last_msg_at else None,
                "author":     r.last_msg_author,
            } if r.last_msg_body else None,
        })
        if r.last_msg_body:
            last_msgs[r.id] = {
                "body":       r.last_msg_body,
                "created_at": r.last_msg_at.isoformat() if r.last_msg_at else None,
                "author":     r.last_msg_author,
            }

    return ok(threads=threads, last_msgs=last_msgs, groups=groups)


@bp.route("/threads/<int:thread_id>")
@login_required
def get_thread(thread_id):
    thread = GameThread.query.get_or_404(thread_id)
    member = GroupMember.query.filter_by(
        group_id=thread.group_id, user_id=current_user.id
    ).first()

    _mq = (
        GameThreadMessage.query
        .filter_by(thread_id=thread_id)
        .options(
            joinedload(GameThreadMessage.author),
            joinedload(GameThreadMessage.reactions),
        )
    )
    _hidden = current_user.hidden_user_ids()
    if _hidden:
        _mq = _mq.filter(GameThreadMessage.user_id.notin_(_hidden))
    messages = _mq.order_by(GameThreadMessage.created_at).all()

    ir = None
    if thread.group_trigger and thread.group_trigger.game_event:
        ir_obj = thread.group_trigger.game_event.incident_report
        if ir_obj:
            ir = {
                "id":                ir_obj.id,
                "incident_type":     ir_obj.incident_type,
                "severity":          ir_obj.severity,
                "status":            ir_obj.status,
                "reporter_name":     ir_obj.reporter.shown_name if ir_obj.reporter else "",
                "reported_score_text": ir_obj.reported_score_text or "",
            }

    # Opening a thread clears its unread state
    if member:
        from app.services.activity import mark_thread_read
        mark_thread_read(current_user.id, thread_id)
        db.session.commit()

    return ok(
        thread={
            "id":               thread.id,
            "title":            thread.title,
            "status":           thread.status,
            "group_name":       thread.group.name if thread.group else "",
            "group_id":         thread.group_id,
            "target_user_id":   thread.target_user_id,
            "target_user_name": thread.target_user.shown_name if thread.target_user else "",
            "team_abbr":        thread.target_team.abbreviation if thread.target_team else "",
            "team_name":        thread.target_team.name if thread.target_team else "",
            "team_color":       thread.target_team.primary_color if thread.target_team else "#333",
            "votes":            thread.vote_counts(),
            "user_vote":        thread.user_vote(current_user.id),
        },
        messages=[_serialize_message(m, current_user.id) for m in messages],
        member={"role": member.role} if member else None,
        incident_report=ir,
    )


@bp.route("/threads/<int:thread_id>/messages", methods=["POST"])
@login_required
def post_message(thread_id):
    thread = GameThread.query.get_or_404(thread_id)
    if thread.status != "active":
        return err("Thread is closed", 400)
    member = GroupMember.query.filter_by(
        group_id=thread.group_id, user_id=current_user.id
    ).first()
    if not member:
        return err("Not a member of this group", 403)

    d = request.get_json(silent=True) or {}
    body = d.get("body", "").strip()
    if not body:
        return err("Message cannot be empty")
    if len(body) > 1000:
        return err("Message too long")

    from app.services.moderation import screen_text
    _ok, _reason = screen_text(body)
    if not _ok:
        return err(_reason, 422)

    msg = GameThreadMessage(
        thread_id=thread_id,
        user_id=current_user.id,
        message_type="user",
        body=body,
    )
    db.session.add(msg)
    thread.updated_at = datetime.now(timezone.utc)
    from app.services.activity import refresh_hot_score, record_event, mark_thread_read
    db.session.flush()
    refresh_hot_score(thread)
    record_event(thread.group_id, current_user.id, "reply", thread_id)
    mark_thread_read(current_user.id, thread_id)
    db.session.commit()
    return ok(id=msg.id, created_at=msg.created_at.isoformat() if msg.created_at else None)


@bp.route("/threads/<int:thread_id>/vote", methods=["POST"])
@login_required
def vote_thread(thread_id):
    """Group-member verdict on a thread. Same vote toggles off; a different
    vote switches. Open to every member — not an admin action."""
    thread = GameThread.query.get_or_404(thread_id)
    member = GroupMember.query.filter_by(
        group_id=thread.group_id, user_id=current_user.id
    ).first()
    if not member:
        return err("Not a member of this group", 403)

    d = request.get_json(silent=True) or {}
    vote_type = d.get("vote_type")
    if vote_type not in ("confirm", "dismiss", "redeem"):
        return err("Invalid vote type")

    from app.models import ThreadVote
    from app.services.activity import refresh_hot_score, record_event

    existing = ThreadVote.query.filter_by(
        thread_id=thread_id, user_id=current_user.id
    ).first()
    if existing and existing.vote_type == vote_type:
        db.session.delete(existing)
        user_vote = None
    elif existing:
        existing.vote_type = vote_type
        user_vote = vote_type
    else:
        db.session.add(ThreadVote(
            thread_id=thread_id, user_id=current_user.id, vote_type=vote_type
        ))
        record_event(thread.group_id, current_user.id, "vote", thread_id)
        user_vote = vote_type
    db.session.flush()
    refresh_hot_score(thread)
    db.session.commit()
    return ok(votes=thread.vote_counts(), user_vote=user_vote)


@bp.route("/threads/<int:thread_id>/read", methods=["POST"])
@login_required
def mark_read(thread_id):
    """Move the caller's read watermark to now — clears unread badges."""
    thread = GameThread.query.get_or_404(thread_id)
    member = GroupMember.query.filter_by(
        group_id=thread.group_id, user_id=current_user.id
    ).first()
    if not member:
        return err("Not a member of this group", 403)
    from app.services.activity import mark_thread_read
    mark_thread_read(current_user.id, thread_id)
    db.session.commit()
    return ok()


# ── Friends ───────────────────────────────────────────────────────────────────

@bp.route("/friends")
@login_required
def friends_list():
    accepted = FriendRequest.query.filter(
        db.or_(
            db.and_(FriendRequest.from_user_id == current_user.id, FriendRequest.status == "accepted"),
            db.and_(FriendRequest.to_user_id   == current_user.id, FriendRequest.status == "accepted"),
        )
    ).options(joinedload(FriendRequest.from_user), joinedload(FriendRequest.to_user)).all()

    others = [fr.to_user if fr.from_user_id == current_user.id else fr.from_user
              for fr in accepted]

    # Shared-group counts in one query
    shared_counts = {}
    if others:
        my_group_ids = [
            gid for (gid,) in db.session.query(GroupMember.group_id)
            .filter_by(user_id=current_user.id).all()
        ]
        if my_group_ids:
            rows = (
                db.session.query(GroupMember.user_id, db.func.count(GroupMember.id))
                .filter(
                    GroupMember.user_id.in_([o.id for o in others]),
                    GroupMember.group_id.in_(my_group_ids),
                )
                .group_by(GroupMember.user_id)
                .all()
            )
            shared_counts = {uid_: cnt for uid_, cnt in rows}

    friends = []
    for other in others:
        friends.append({
            "id":   other.id,
            "name": other.shown_name,
            "uid":  other.uid,
            "shared_group_count": shared_counts.get(other.id, 0),
            "last_active_at": other.last_active_at.isoformat() if other.last_active_at else None,
        })

    return ok(friends=friends)


@bp.route("/friends/request/<int:user_id>", methods=["POST"])
@login_required
def send_friend_request(user_id):
    if user_id == current_user.id:
        return err("You can't add yourself", 400)
    target = User.query.get_or_404(user_id)
    existing = FriendRequest.query.filter(
        db.or_(
            db.and_(FriendRequest.from_user_id == current_user.id, FriendRequest.to_user_id == user_id),
            db.and_(FriendRequest.from_user_id == user_id,         FriendRequest.to_user_id == current_user.id),
        )
    ).first()
    if existing:
        if existing.status == "accepted":
            return err("Already friends", 400)
        if existing.status == "pending":
            return ok(status="pending_sent")
        # Declined — allow retry
        existing.status = "pending"
        existing.from_user_id = current_user.id
        existing.to_user_id   = user_id
        db.session.commit()
        return ok(status="pending_sent")

    fr = FriendRequest(from_user_id=current_user.id, to_user_id=user_id)
    db.session.add(fr)
    db.session.flush()
    db.session.add(Notification(
        user_id=user_id,
        type="friend_request",
        message=f"{current_user.shown_name} sent you a friend request",
        link_url="/notifications",
    ))
    db.session.commit()
    try:
        from ..services.email_service import send_friend_request_email
        send_friend_request_email(current_user, target)
    except Exception:
        pass
    return ok(status="pending_sent")


@bp.route("/friends/accept/<int:request_id>", methods=["POST"])
@login_required
def accept_friend_request(request_id):
    fr = FriendRequest.query.get_or_404(request_id)
    if fr.to_user_id != current_user.id:
        return err("Not authorized", 403)
    fr.status = "accepted"
    db.session.add(Notification(
        user_id=fr.from_user_id,
        type="friend_accepted",
        message=f"{current_user.shown_name} accepted your friend request",
        link_url="/friends",
    ))
    db.session.commit()
    return ok(name=fr.from_user.shown_name if fr.from_user else "")


@bp.route("/friends/decline/<int:request_id>", methods=["POST"])
@login_required
def decline_friend_request(request_id):
    fr = FriendRequest.query.get_or_404(request_id)
    if fr.to_user_id != current_user.id:
        return err("Not authorized", 403)
    db.session.delete(fr)
    db.session.commit()
    return ok()


@bp.route("/friends/<int:user_id>", methods=["DELETE"])
@login_required
def remove_friend(user_id):
    FriendRequest.query.filter(
        db.or_(
            db.and_(FriendRequest.from_user_id == current_user.id, FriendRequest.to_user_id == user_id),
            db.and_(FriendRequest.from_user_id == user_id, FriendRequest.to_user_id == current_user.id),
        )
    ).delete(synchronize_session=False)
    db.session.commit()
    return ok()


# ── Support ───────────────────────────────────────────────────────────────────

@bp.route("/support/tickets")
@login_required
def support_tickets():
    tickets = (
        SupportTicket.query
        .filter_by(user_id=current_user.id)
        .order_by(SupportTicket.created_at.desc())
        .all()
    )
    return ok(tickets=[
        {"uid": t.uid, "subject": t.subject, "status": t.status,
         "category": t.category, "created_at": t.created_at.strftime("%-d %b %Y") if t.created_at else ""}
        for t in tickets
    ])


@bp.route("/support/tickets", methods=["POST"])
@login_required
def create_ticket():
    d = request.get_json(silent=True) or {}
    if not d.get("subject") or not d.get("description"):
        return err("Subject and description are required")

    def gen_uid():
        import random
        return "FS-" + "".join(random.choices("0123456789", k=6))

    t = SupportTicket(
        uid=gen_uid(),
        user_id=current_user.id,
        subject=d["subject"].strip()[:200],
        category=d.get("category", "other"),
        description=d["description"].strip(),
    )
    db.session.add(t)
    db.session.commit()
    return ok(uid=t.uid), 201


@bp.route("/support/tickets/<uid>")
@login_required
def get_ticket(uid):
    t = SupportTicket.query.filter_by(uid=uid, user_id=current_user.id).first_or_404()
    return ok(ticket={
        "uid": t.uid, "subject": t.subject, "status": t.status,
        "category": t.category, "description": t.description,
        "admin_note": t.admin_note or "",
        "created_at": t.created_at.strftime("%-d %b %Y") if t.created_at else "",
        "resolved_at": t.resolved_at.strftime("%-d %b %Y") if t.resolved_at else "",
    })


# ── Public ────────────────────────────────────────────────────────────────────

@bp.route("/public/receipts/<slug>")
def public_receipt(slug):
    r = Receipt.query.filter_by(public_slug=slug).first_or_404()
    # Public receipts are anonymized — never name the individual.
    from app.routes.public import _anonymize
    names = []
    if r.target_user:
        names += [r.target_user.display_name, r.target_user.first_name, r.target_user.last_name]
    if r.top_hater:
        names += [r.top_hater.display_name, r.top_hater.first_name, r.top_hater.last_name]
    team_name = r.target_team.name if r.target_team else ""
    return ok(receipt={
        "title": _anonymize(r.title, names),
        "summary": _anonymize(r.summary, names),
        "final_score": r.final_score, "shame_points": r.shame_points,
        "target_team": team_name,
        "target_user": (f"A {team_name} fan" if team_name else "A fan"),
        "created_at": r.created_at.strftime("%-d %b %Y") if r.created_at else "",
    })


# ── Reports ───────────────────────────────────────────────────────────────────

@bp.route("/reports/<int:report_id>/confirm", methods=["POST"])
@login_required
def confirm_report(report_id):
    ir = IncidentReport.query.get_or_404(report_id)
    m = GroupMember.query.filter_by(group_id=ir.group_id, user_id=current_user.id).first()
    if not m or m.role not in ("owner", "admin"):
        return err("Not authorized", 403)
    ir.status = "confirmed"
    db.session.commit()
    return ok()


@bp.route("/reports/<int:report_id>/dismiss", methods=["POST"])
@login_required
def dismiss_report(report_id):
    ir = IncidentReport.query.get_or_404(report_id)
    m = GroupMember.query.filter_by(group_id=ir.group_id, user_id=current_user.id).first()
    if not m or m.role not in ("owner", "admin"):
        return err("Not authorized", 403)
    ir.status = "dismissed"
    # Penalise reporter
    reporter_member = GroupMember.query.filter_by(
        group_id=ir.group_id, user_id=ir.reporter_user_id
    ).first()
    if reporter_member:
        reporter_member.reporter_score = max(0, reporter_member.reporter_score - 5)
    db.session.commit()
    return ok()


@bp.route("/reports/<int:report_id>/redeem", methods=["POST"])
@login_required
def redeem_report(report_id):
    ir = IncidentReport.query.get_or_404(report_id)
    m = GroupMember.query.filter_by(group_id=ir.group_id, user_id=current_user.id).first()
    if not m and current_user.id != ir.target_user_id:
        return err("Not authorized", 403)
    ir.status = "redeemed"
    db.session.commit()
    return ok()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _send_code_email(email, code):
    try:
        import resend
        resend.Emails.send({
            "from": "FriedSports <noreply@friedsports.app>",
            "to": [email],
            "subject": "Your FriedSports sign-in code",
            "text": f"Your code is: {code}\n\nThis code expires in 15 minutes.",
        })
    except Exception:
        pass
