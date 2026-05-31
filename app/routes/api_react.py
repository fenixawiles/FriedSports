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

    if User.query.filter_by(email=d["email"].lower().strip()).first():
        return err("An account with that email already exists")

    u = User(
        first_name=d["first_name"].strip(),
        last_name=d["last_name"].strip(),
        display_name=d["display_name"].strip(),
        display_preference=d.get("display_preference", "username"),
        email=d["email"].lower().strip(),
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
    return ok(next="verify-code")


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
    memberships = (
        GroupMember.query
        .filter_by(user_id=current_user.id)
        .options(joinedload(GroupMember.group))
        .all()
    )
    groups = [
        {"group": {"id": m.group.id, "name": m.group.name, "league_scope": m.group.league_scope},
         "member": {"role": m.role}}
        for m in memberships if m.group
    ]
    group_ids = [m.group_id for m in memberships]

    active_threads = (
        GameThread.query
        .filter(GameThread.group_id.in_(group_ids), GameThread.status == "active")
        .options(joinedload(GameThread.group))
        .all()
    ) if group_ids else []

    msg_counts = {}
    if active_threads:
        from sqlalchemy import func
        counts = (
            db.session.query(
                GameThreadMessage.thread_id,
                func.count(GameThreadMessage.id).label("cnt")
            )
            .filter(
                GameThreadMessage.thread_id.in_([t.id for t in active_threads]),
                GameThreadMessage.message_type == "user",
                GameThreadMessage.is_deleted == False,
            )
            .group_by(GameThreadMessage.thread_id)
            .all()
        )
        msg_counts = {row.thread_id: row.cnt for row in counts}

    return ok(
        groups=groups,
        active_threads=[
            {"id": t.id, "title": t.title, "group_name": t.group.name if t.group else ""}
            for t in active_threads
        ],
        msg_counts=msg_counts,
    )


@bp.route("/onboarding")
@login_required
def onboarding_get():
    leagues = ["NBA", "NFL", "MLB", "NHL", "EPL", "FIFA", "F1", "PGA"]
    league_labels = {
        "NBA": "Basketball (NBA)", "NFL": "Football (NFL)", "MLB": "Baseball (MLB)",
        "NHL": "Hockey (NHL)", "EPL": "Premier League", "FIFA": "International Soccer",
        "F1": "Formula 1", "PGA": "Golf (PGA)",
    }
    teams_by_league = {}
    for league in leagues:
        teams = Team.query.filter_by(league=league).order_by(Team.name).all()
        teams_by_league[league] = [
            {"id": t.id, "name": t.name, "city": t.city or "",
             "abbreviation": t.abbreviation, "primary_color": t.primary_color}
            for t in teams
        ]
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
    leagues = ["NBA", "NFL", "MLB", "NHL", "EPL", "FIFA", "F1", "PGA"]
    league_labels = {
        "NBA": "Basketball (NBA)", "NFL": "Football (NFL)", "MLB": "Baseball (MLB)",
        "NHL": "Hockey (NHL)", "EPL": "Premier League", "FIFA": "International Soccer",
        "F1": "Formula 1", "PGA": "Golf (PGA)",
    }
    teams_by_league = {}
    for league in leagues:
        teams = Team.query.filter_by(league=league).order_by(Team.name).all()
        teams_by_league[league] = [
            {"id": t.id, "name": t.name, "city": t.city or "",
             "abbreviation": t.abbreviation, "primary_color": t.primary_color}
            for t in teams
        ]
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
    return ok(user=_serialize_user(current_user))


@bp.route("/settings/delete-account", methods=["POST"])
@login_required
def delete_account():
    d = request.get_json(silent=True) or {}
    if not current_user.check_password(d.get("password", "")):
        return err("Incorrect password", 401)
    from ..routes.admin import _cascade_delete_user
    _cascade_delete_user(current_user.id)
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


@bp.route("/groups/join/<code>")
def join_info(code):
    g = Group.query.filter_by(invite_code=code.upper()).first()
    if not g:
        return err("Invalid invite code", 404)
    already = g.is_member(current_user.id) if current_user.is_authenticated else False
    return ok(
        group={"id": g.id, "name": g.name, "league_scope": g.league_scope},
        member_count=g.members.count(),
        already_member=already,
    )


@bp.route("/groups/join/<code>", methods=["POST"])
@login_required
def join_group(code):
    g = Group.query.filter_by(invite_code=code.upper()).first()
    if not g:
        return err("Invalid invite code", 404)
    if g.is_member(current_user.id):
        return ok(group_id=g.id)
    db.session.add(GroupMember(group_id=g.id, user_id=current_user.id, role="member"))
    db.session.commit()
    return ok(group_id=g.id)


@bp.route("/groups/<int:group_id>")
@login_required
def get_group(group_id):
    g = Group.query.get_or_404(group_id)
    member = g.get_member(current_user.id)
    receipts = g.receipts if hasattr(g, 'receipts') else []
    try:
        receipts = (
            Receipt.query.filter_by(group_id=group_id)
            .order_by(Receipt.created_at.desc()).limit(5).all()
        )
    except Exception:
        receipts = []

    return ok(
        group={
            "id": g.id, "name": g.name,
            "league_scope": g.league_scope,
            "invite_code": g.invite_code,
            "member_count": g.members.count(),
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
    leagues = ["NBA", "NFL", "MLB", "NHL", "EPL", "FIFA", "F1", "PGA"]
    teams_by_league = {}
    team_colors = {}
    for league in leagues:
        teams = Team.query.filter_by(league=league).order_by(Team.name).all()
        teams_by_league[league] = [
            {"id": t.id, "name": t.name, "city": t.city or "",
             "abbreviation": t.abbreviation, "primary_color": t.primary_color}
            for t in teams
        ]
        for t in teams:
            team_colors[str(t.id)] = {"primary": t.primary_color, "abbr": t.abbreviation}

    user_fav_teams = {}
    for mem in members:
        if not mem.user: continue
        for uft in mem.user.favorite_teams:
            if uft.league not in [l.lower() for l in leagues]:
                continue
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
    from sqlalchemy import func
    memberships = GroupMember.query.filter_by(user_id=current_user.id).all()
    group_ids = [m.group_id for m in memberships]
    if not group_ids:
        return ok(threads=[], groups=[], last_msgs={})

    threads = (
        GameThread.query
        .filter(GameThread.group_id.in_(group_ids), GameThread.status == "active")
        .options(
            joinedload(GameThread.group),
            joinedload(GameThread.target_team),
            joinedload(GameThread.target_user),
            joinedload(GameThread.group_trigger).joinedload(GroupTrigger.game_event)
            .joinedload(GameEvent.incident_report),
        )
        .order_by(GameThread.updated_at.desc())
        .all()
    )

    # Last message per thread (single query)
    thread_ids = [t.id for t in threads]
    last_msgs = {}
    if thread_ids:
        subq = (
            db.session.query(
                GameThreadMessage.thread_id,
                func.max(GameThreadMessage.id).label("max_id")
            )
            .filter(
                GameThreadMessage.thread_id.in_(thread_ids),
                GameThreadMessage.is_deleted == False,
            )
            .group_by(GameThreadMessage.thread_id)
            .subquery()
        )
        rows = (
            db.session.query(GameThreadMessage)
            .join(subq, GameThreadMessage.id == subq.c.max_id)
            .all()
        )
        last_msgs = {m.thread_id: m for m in rows}

    groups = Group.query.filter(Group.id.in_(group_ids)).all()

    return ok(
        threads=[_serialize_thread(t, last_msgs.get(t.id)) for t in threads],
        last_msgs={
            tid: {"body": m.body, "created_at": m.created_at.isoformat() if m.created_at else None}
            for tid, m in last_msgs.items()
        },
        groups=[{"id": g.id, "name": g.name} for g in groups],
    )


@bp.route("/threads/<int:thread_id>")
@login_required
def get_thread(thread_id):
    thread = GameThread.query.get_or_404(thread_id)
    member = GroupMember.query.filter_by(
        group_id=thread.group_id, user_id=current_user.id
    ).first()

    messages = (
        GameThreadMessage.query
        .filter_by(thread_id=thread_id)
        .options(
            joinedload(GameThreadMessage.author),
            joinedload(GameThreadMessage.reactions),
        )
        .order_by(GameThreadMessage.created_at)
        .all()
    )

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

    msg = GameThreadMessage(
        thread_id=thread_id,
        user_id=current_user.id,
        message_type="user",
        body=body,
    )
    db.session.add(msg)
    thread.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return ok(id=msg.id, created_at=msg.created_at.isoformat() if msg.created_at else None)


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

    friends = []
    for fr in accepted:
        other = fr.to_user if fr.from_user_id == current_user.id else fr.from_user
        friends.append({"id": other.id, "name": other.shown_name, "uid": other.uid})

    return ok(friends=friends)


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
    return ok(receipt={
        "title": r.title, "summary": r.summary,
        "final_score": r.final_score, "shame_points": r.shame_points,
        "target_team": r.target_team.name if r.target_team else "",
        "target_user": r.target_user.shown_name if r.target_user else "",
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
    # Add system message to thread
    thread = GameThread.query.filter_by(
        group_trigger_id=ir.id if hasattr(ir, 'group_trigger') else None
    ).first()
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
