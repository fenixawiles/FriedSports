"""
api_react.py — JSON API endpoints for the React frontend.

All routes live under /api/ and return JSON.
Auth: Flask-Login session cookies (withCredentials on the React side).
"""
import string, secrets
from datetime import datetime, timezone, timedelta, date
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.orm import joinedload

from ..models import (
    db, User, LoginToken, Group, GroupMember, GameThread, GameThreadMessage,
    MessageReaction, MessageReport, IncidentReport, GameEvent, GroupTrigger, Team,
    UserFavoriteTeam, Notification, FriendRequest, SupportTicket,
    Receipt, DeviceToken, ThreadUserState, BlockedUser, AdminAuditLog,
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
    thread_type = t.thread_type or "incident"
    return {
        "id":            t.id,
        "title":         t.title,
        "thread_type":   thread_type,
        "status":        t.status,
        "group_id":      t.group_id,
        "group_name":    t.group.name if t.group else "",
        "created_by_user_id": t.created_by_user_id,
        "created_by_user_name": t.created_by.shown_name if t.created_by else "",
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


def _has_accepted_friendship(user_id):
    return FriendRequest.query.filter(
        db.or_(
            db.and_(
                FriendRequest.from_user_id == current_user.id,
                FriendRequest.to_user_id == user_id,
                FriendRequest.status == "accepted",
            ),
            db.and_(
                FriendRequest.from_user_id == user_id,
                FriendRequest.to_user_id == current_user.id,
                FriendRequest.status == "accepted",
            ),
        )
    ).first() is not None


def _is_direct_participant(thread):
    return (
        (thread.created_by_user_id == current_user.id and thread.target_user_id)
        or (thread.target_user_id == current_user.id and thread.created_by_user_id)
    )


def _thread_member(thread):
    if not thread.group_id:
        return None
    return GroupMember.query.filter_by(
        group_id=thread.group_id,
        user_id=current_user.id,
    ).first()


def _can_access_thread(thread):
    if (thread.thread_type or "incident") == "direct_chat":
        if not _is_direct_participant(thread):
            return False
        other_id = (
            thread.target_user_id
            if thread.created_by_user_id == current_user.id
            else thread.created_by_user_id
        )
        return other_id not in current_user.hidden_user_ids()
    return _thread_member(thread) is not None


def _other_direct_user(thread):
    if (thread.thread_type or "incident") != "direct_chat":
        return None
    return thread.target_user if thread.created_by_user_id == current_user.id else thread.created_by


def _restore_local_thread_state(thread_id):
    st = ThreadUserState.query.filter_by(
        user_id=current_user.id,
        thread_id=thread_id,
    ).first()
    if st:
        st.deleted = False
        st.deleted_at = None
        st.archived = False
        st.cleared_at = None


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

    # Email verification codes are disabled for now (delivery is unreliable and was
    # stranding real signups). The account is created in a "pending" state
    # (email_verified stays False) and the user is let straight into the app; admins
    # review the pending queue and approve manually in /admin. No code is sent.
    db.session.commit()

    login_user(u, remember=True)
    return ok(user=_serialize_user(u), next="/onboarding"), 201


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


# ── Admin ────────────────────────────────────────────────────────────────────

def _require_admin_json():
    if not current_user.is_authenticated or not current_user.is_admin:
        return err("Admin access required", 403)
    return None


@bp.route("/admin/overview")
@login_required
def admin_overview():
    denied = _require_admin_json()
    if denied:
        return denied

    from app.models import MessageReport
    from app.analytics.models import LabGame, LabPlayer, DerivedGameMetrics

    derived_count = (
        db.session.query(LabGame.id)
        .join(DerivedGameMetrics, DerivedGameMetrics.game_id == LabGame.id)
        .distinct()
        .count()
    )
    recent_games = (
        LabGame.query
        .order_by(LabGame.created_at.desc())
        .limit(5)
        .all()
    )

    return ok(
        stats={
            "users": User.query.count(),
            "groups": Group.query.count(),
            "active_threads": GameThread.query.filter_by(status="active").count(),
            "support_open": SupportTicket.query.filter(SupportTicket.status != "resolved").count(),
            "reports_open": MessageReport.query.filter_by(status="open").count(),
            "pending_verification": User.query.filter_by(email_verified=False).count(),
            "lab_games": LabGame.query.count(),
            "lab_players": LabPlayer.query.count(),
            "derived_games": derived_count,
        },
        recent_games=[
            {
                "id": g.id,
                "date": g.date.isoformat() if g.date else None,
                "status": g.status,
                "league": g.league.abbreviation if g.league else "",
                "home_team": g.home_team.name if g.home_team else "",
                "away_team": g.away_team.name if g.away_team else "",
            }
            for g in recent_games
        ],
    )


def _admin_audit(action, target_user=None, details=None):
    db.session.add(AdminAuditLog(
        admin_id=current_user.id,
        target_user_id=target_user.id if target_user else None,
        action=action,
        details=details,
        ip_address=request.remote_addr,
    ))


def _iso(dt):
    return dt.isoformat() if dt else None


def _date_iso(value):
    return value.isoformat() if value else None


def _team_label(team):
    if not team:
        return ""
    return f"{team.city} {team.name}".strip()


def _admin_user_summary(user):
    return {
        "id": user.id,
        "uid": user.uid,
        "name": user.shown_name,
        "display_name": user.display_name,
        "email": user.email,
        "role": user.role,
        "email_verified": user.email_verified,
        "created_at": _iso(user.created_at),
        "last_active_at": _iso(user.last_active_at),
        "agreed_to_terms_at": _iso(user.agreed_to_terms_at),
    }


@bp.route("/admin/users")
@login_required
def admin_users():
    denied = _require_admin_json()
    if denied:
        return denied

    q = request.args.get("q", "").strip()
    query = User.query.order_by(User.created_at.desc())
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(
            User.display_name.ilike(like),
            User.email.ilike(like),
            User.uid.ilike(like),
            User.first_name.ilike(like),
            User.last_name.ilike(like),
        ))
    # ?pending=1 narrows to accounts still awaiting manual approval
    if request.args.get("pending") in ("1", "true", "yes"):
        query = query.filter_by(email_verified=False)
    users = query.limit(80).all()
    return ok(
        users=[_admin_user_summary(u) for u in users],
        pending_count=User.query.filter_by(email_verified=False).count(),
    )


@bp.route("/admin/users/<int:user_id>/approve", methods=["POST"])
@login_required
def admin_approve_user(user_id):
    """Manually approve a pending account (email verification codes are off)."""
    denied = _require_admin_json()
    if denied:
        return denied
    user = User.query.get_or_404(user_id)
    if not user.email_verified:
        user.email_verified = True
        _admin_audit("approve_user", user, "Manually approved (verification bypassed)")
        db.session.commit()
    return ok(user=_admin_user_summary(user))


@bp.route("/admin/users/<int:user_id>")
@login_required
def admin_user_detail(user_id):
    denied = _require_admin_json()
    if denied:
        return denied

    user = User.query.get_or_404(user_id)
    memberships = (
        GroupMember.query
        .filter_by(user_id=user_id)
        .options(joinedload(GroupMember.group))
        .all()
    )
    fav_teams = (
        UserFavoriteTeam.query
        .filter_by(user_id=user_id)
        .options(joinedload(UserFavoriteTeam.team))
        .all()
    )
    return ok(
        user={
            **_admin_user_summary(user),
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "display_preference": user.display_preference,
            "has_completed_profile": user.has_completed_profile,
        },
        groups=[
            {
                "id": m.group_id,
                "name": m.group.name if m.group else "Deleted group",
                "role": m.role,
                "joined_at": _iso(m.joined_at),
            }
            for m in memberships
        ],
        favorite_teams=[
            {
                "league": ft.league,
                "team": _team_label(ft.team),
                "abbreviation": ft.team.abbreviation if ft.team else "",
            }
            for ft in fav_teams
        ],
    )


@bp.route("/admin/users/<int:user_id>", methods=["PATCH"])
@login_required
def admin_update_user(user_id):
    denied = _require_admin_json()
    if denied:
        return denied

    user = User.query.get_or_404(user_id)
    d = request.get_json(silent=True) or {}
    changed = []

    if "email" in d:
        new_email = (d.get("email") or "").strip().lower()
        if not new_email:
            return err("Email cannot be empty")
        if User.query.filter(User.email == new_email, User.id != user_id).first():
            return err("Email already in use")
        if new_email != user.email:
            old = user.email
            user.email = new_email
            changed.append(f"email {old} -> {new_email}")

    if "role" in d:
        role = d.get("role") or "user"
        if role not in ("user", "admin"):
            return err("Invalid role")
        if user.id == current_user.id and role != user.role:
            return err("You cannot change your own role", 400)
        if role != user.role:
            changed.append(f"role {user.role} -> {role}")
            user.role = role

    password = d.get("password") or ""
    if password:
        if len(password) < 6:
            return err("Password must be at least 6 characters")
        user.set_password(password)
        changed.append("password reset")

    if not changed:
        return ok(user=_admin_user_summary(user), message="No changes")

    _admin_audit("update_user", user, "; ".join(changed))
    db.session.commit()
    return ok(user=_admin_user_summary(user), message="User updated")


@bp.route("/admin/users/<int:user_id>", methods=["DELETE"])
@login_required
def admin_delete_user(user_id):
    denied = _require_admin_json()
    if denied:
        return denied
    if user_id == current_user.id:
        return err("You cannot delete your own account from admin", 400)

    user = User.query.get_or_404(user_id)
    label = f"{user.display_name} <{user.email}>"
    try:
        _admin_audit("delete_user", user, f"Deleted account: {label}")
        db.session.flush()
        from ..routes.admin import _cascade_delete_user
        _cascade_delete_user(user_id)
        user_obj = db.session.get(User, user_id)
        if user_obj:
            db.session.delete(user_obj)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Admin user delete failed for user %s", user_id)
        return err("User deletion failed", 500)
    return ok(message="User deleted")


@bp.route("/admin/users/invite", methods=["POST"])
@login_required
def admin_invite_user():
    denied = _require_admin_json()
    if denied:
        return denied

    d = request.get_json(silent=True) or {}
    email = (d.get("email") or "").strip().lower()
    if not email:
        return err("Email is required")
    if User.query.filter_by(email=email).first():
        return err("A user with that email already exists")

    from flask import url_for
    from app.services.email_service import _send, _wrap
    invite_url = url_for("auth.signup", _external=True)
    text = f"You've been invited to FriedSports. Sign up here: {invite_url}"
    html = _wrap(f"<p>You've been invited to FriedSports.</p><a href=\"{invite_url}\" class=\"btn\">Sign Up</a>")
    sent = _send(email, "You're invited to FriedSports", html, text)
    _admin_audit("invite_user", None, email)
    db.session.commit()
    return ok(sent=bool(sent), invite_url=invite_url)


@bp.route("/admin/users/<int:user_id>/email", methods=["POST"])
@login_required
def admin_email_user(user_id):
    denied = _require_admin_json()
    if denied:
        return denied

    user = User.query.get_or_404(user_id)
    d = request.get_json(silent=True) or {}
    subject = (d.get("subject") or "").strip()
    body = (d.get("body") or "").strip()
    if not subject or not body:
        return err("Subject and body are required")
    from app.services.email_service import _send, _wrap
    sent = _send(user.email, subject, _wrap(f"<p>{body}</p>"), body)
    _admin_audit("send_user_email", user, subject)
    db.session.commit()
    return ok(sent=bool(sent))


@bp.route("/admin/users/<int:user_id>/prompt/<kind>", methods=["POST"])
@login_required
def admin_prompt_user(user_id, kind):
    denied = _require_admin_json()
    if denied:
        return denied
    if kind not in ("password", "username", "email"):
        return err("Unknown prompt type", 404)

    import secrets as _sec
    user = User.query.get_or_404(user_id)
    if kind == "password":
        purpose = "password_reset"
        next_url = None
        expires = timedelta(hours=1)
    else:
        purpose = "magic_link"
        next_url = "/settings"
        expires = timedelta(hours=24)
    tok = LoginToken(
        user_id=user.id,
        token=_sec.token_urlsafe(32),
        purpose=purpose,
        next_url=next_url,
        expires_at=datetime.now(timezone.utc) + expires,
    )
    db.session.add(tok)
    db.session.commit()

    from flask import url_for
    if kind == "password":
        from app.services.email_service import send_admin_password_reset
        link = url_for("auth.reset_password", token=tok.token, _external=True)
        sent = send_admin_password_reset(user, link)
        action = "send_password_reset"
    elif kind == "username":
        from app.services.email_service import send_username_change_prompt
        link = url_for("auth.magic_link", token=tok.token, _external=True)
        sent = send_username_change_prompt(user, link)
        action = "send_username_change"
    else:
        from app.services.email_service import send_email_change_prompt
        link = url_for("auth.magic_link", token=tok.token, _external=True)
        sent = send_email_change_prompt(user, link)
        action = "send_email_change"

    _admin_audit(action, user, f"Admin sent {kind} prompt")
    db.session.commit()
    return ok(sent=bool(sent))


def _serialize_ticket(ticket):
    return {
        "uid": ticket.uid,
        "user_id": ticket.user_id,
        "user_name": ticket.user.shown_name if ticket.user else "",
        "user_email": ticket.user.email if ticket.user else "",
        "subject": ticket.subject,
        "category": ticket.category,
        "description": ticket.description,
        "status": ticket.status,
        "status_label": ticket.status_label,
        "admin_note": ticket.admin_note or "",
        "resolved_at": _iso(ticket.resolved_at),
        "created_at": _iso(ticket.created_at),
        "updated_at": _iso(ticket.updated_at),
        "next_statuses": ticket.NEXT_STATUSES.get(ticket.status, []),
    }


@bp.route("/admin/support")
@login_required
def admin_support():
    denied = _require_admin_json()
    if denied:
        return denied

    status_filter = request.args.get("status", "all")
    query = SupportTicket.query.options(joinedload(SupportTicket.user)).order_by(SupportTicket.created_at.desc())
    if status_filter != "all":
        query = query.filter_by(status=status_filter)
    counts = {
        "all": SupportTicket.query.count(),
        "received": SupportTicket.query.filter_by(status="received").count(),
        "in_progress": SupportTicket.query.filter_by(status="in_progress").count(),
        "resolved": SupportTicket.query.filter_by(status="resolved").count(),
    }
    return ok(tickets=[_serialize_ticket(t) for t in query.limit(100).all()], counts=counts)


@bp.route("/admin/support/<uid>", methods=["PATCH"])
@login_required
def admin_update_support(uid):
    denied = _require_admin_json()
    if denied:
        return denied

    ticket = SupportTicket.query.filter_by(uid=uid).first_or_404()
    if ticket.is_resolved:
        return err("This ticket is already resolved", 400)
    d = request.get_json(silent=True) or {}
    new_status = (d.get("status") or "").strip()
    admin_note = (d.get("admin_note") or "").strip() or None
    if new_status not in ticket.NEXT_STATUSES.get(ticket.status, []):
        return err("Invalid status transition")

    old_status = ticket.status
    ticket.status = new_status
    ticket.admin_note = admin_note
    if new_status == "resolved":
        ticket.resolved_at = datetime.now(timezone.utc)
    _admin_audit("ticket_status_update", ticket.user, f"{ticket.uid}: {old_status} -> {new_status}")
    db.session.commit()

    try:
        from app.services.email_service import send_ticket_status_update
        send_ticket_status_update(ticket)
    except Exception:
        current_app.logger.exception("Ticket status email failed for %s", uid)
    return ok(ticket=_serialize_ticket(ticket))


def _serialize_report(report):
    msg = db.session.get(GameThreadMessage, report.message_id)
    thread = db.session.get(GameThread, msg.thread_id) if msg else None
    author = db.session.get(User, msg.user_id) if msg and msg.user_id else None
    return {
        "id": report.id,
        "message_id": report.message_id,
        "category": report.category,
        "category_label": report.category_label,
        "reason": report.reason or "",
        "status": report.status,
        "resolution": report.resolution or "",
        "reporter": report.reporter.shown_name if report.reporter else "",
        "author": author.shown_name if author else "",
        "thread_id": thread.id if thread else None,
        "thread_title": thread.title if thread else "",
        "body": msg.body if msg else "",
        "message_deleted": bool(msg.is_deleted) if msg else True,
        "reviewed_by": report.reviewed_by.shown_name if report.reviewed_by else "",
        "reviewed_at": _iso(report.reviewed_at),
        "created_at": _iso(report.created_at),
    }


@bp.route("/admin/reports")
@login_required
def admin_reports():
    denied = _require_admin_json()
    if denied:
        return denied

    status_filter = request.args.get("status", "open")
    query = (
        MessageReport.query
        .options(joinedload(MessageReport.reporter), joinedload(MessageReport.reviewed_by))
        .order_by(MessageReport.created_at.desc())
    )
    if status_filter != "all":
        query = query.filter(MessageReport.status == status_filter)
    counts = {
        "open": MessageReport.query.filter_by(status="open").count(),
        "resolved": MessageReport.query.filter_by(status="resolved").count(),
        "dismissed": MessageReport.query.filter_by(status="dismissed").count(),
        "all": MessageReport.query.count(),
    }
    return ok(reports=[_serialize_report(r) for r in query.limit(100).all()], counts=counts)


@bp.route("/admin/reports/<int:report_id>/action", methods=["POST"])
@login_required
def admin_report_action(report_id):
    denied = _require_admin_json()
    if denied:
        return denied

    report = MessageReport.query.get_or_404(report_id)
    d = request.get_json(silent=True) or {}
    action = d.get("action")
    msg = db.session.get(GameThreadMessage, report.message_id)
    if action == "delete_message":
        if msg and not msg.is_deleted:
            msg.is_deleted = True
        report.status = "resolved"
        report.resolution = "message_deleted"
        if msg:
            MessageReport.query.filter(
                MessageReport.message_id == msg.id,
                MessageReport.status == "open",
                MessageReport.id != report.id,
            ).update(
                {
                    "status": "resolved",
                    "resolution": "message_deleted",
                    "reviewed_by_id": current_user.id,
                    "reviewed_at": datetime.now(timezone.utc),
                },
                synchronize_session=False,
            )
        detail = f"Deleted message #{report.message_id} (report #{report.id})"
    elif action == "dismiss":
        report.status = "dismissed"
        report.resolution = "no_action"
        detail = f"Dismissed report #{report.id} (message #{report.message_id})"
    else:
        return err("Unknown moderation action")

    report.reviewed_by_id = current_user.id
    report.reviewed_at = datetime.now(timezone.utc)
    _admin_audit("content_moderation", db.session.get(User, msg.user_id) if msg and msg.user_id else None, detail)
    db.session.commit()
    return ok(report=_serialize_report(report))


@bp.route("/admin/broadcast", methods=["POST"])
@login_required
def admin_broadcast():
    denied = _require_admin_json()
    if denied:
        return denied

    d = request.get_json(silent=True) or {}
    subject = (d.get("subject") or "").strip()
    body_html = (d.get("body_html") or "").strip()
    target = d.get("target") or "all"
    target_email = (d.get("target_email") or "").strip().lower()
    if not subject or not body_html:
        return err("Subject and body are required")

    from app.services.email_service import send_broadcast, _send, _wrap
    if target == "single":
        if not target_email:
            return err("Enter a target email address")
        sent = 1 if _send(target_email, subject, _wrap(body_html)) else 0
        failed = 0 if sent else 1
        detail = f"single: {target_email}"
    else:
        users = User.query.filter(User.email.isnot(None)).all()
        sent, failed = send_broadcast(users, subject, body_html)
        detail = f"all users: sent {sent}, failed {failed}"

    _admin_audit("broadcast", None, f"{subject}; {detail}")
    db.session.commit()
    return ok(sent=sent, failed=failed)


@bp.route("/admin/audit-log")
@login_required
def admin_audit_log():
    denied = _require_admin_json()
    if denied:
        return denied

    logs = (
        AdminAuditLog.query
        .options(joinedload(AdminAuditLog.admin), joinedload(AdminAuditLog.target_user))
        .order_by(AdminAuditLog.created_at.desc())
        .limit(120)
        .all()
    )
    return ok(logs=[
        {
            "id": log.id,
            "admin": log.admin.shown_name if log.admin else "Former admin",
            "target": log.target_user.shown_name if log.target_user else "",
            "action": log.action,
            "details": log.details or "",
            "ip_address": log.ip_address or "",
            "created_at": _iso(log.created_at),
        }
        for log in logs
    ])


TEAM_STAT_FIELDS = [
    "points", "fgm", "fga", "three_pm", "three_pa", "ftm", "fta",
    "off_rebounds", "def_rebounds", "assists", "steals", "blocks",
    "turnovers", "fouls",
]


def _int_value(value, default=0):
    if value in (None, ""):
        return default
    return int(value)


def _serialize_team(team):
    return {
        "id": team.id,
        "league": team.league,
        "name": team.name,
        "city": team.city or "",
        "abbreviation": team.abbreviation,
        "label": _team_label(team),
    }


def _serialize_season(season):
    return {
        "id": season.id,
        "league_id": season.league_id,
        "league": season.league.abbreviation if season.league else "",
        "year": season.year,
        "season_type": season.season_type,
        "label": f"{season.year} {season.season_type.title()}",
    }


def _serialize_stats(stats):
    if not stats:
        return None
    return {
        "team_id": stats.team_id,
        "team": _team_label(stats.team),
        **{field: getattr(stats, field) for field in TEAM_STAT_FIELDS},
        "total_rebounds": stats.total_rebounds,
        "fg_pct": stats.fg_pct,
        "three_pct": stats.three_pct,
        "ft_pct": stats.ft_pct,
    }


def _apply_stats_payload(stats, payload):
    for field in TEAM_STAT_FIELDS:
        if field in payload:
            setattr(stats, field, _int_value(payload.get(field)))
    stats.compute_percentages()


def _serialize_game(game):
    stats = {s.team_id: s for s in game.team_stats.all()}
    derived = {d.team_id: d for d in game.derived_metrics.all()}
    return {
        "id": game.id,
        "league_id": game.league_id,
        "league": game.league.abbreviation if game.league else "",
        "season_id": game.season_id,
        "season": game.season.label() if game.season else "",
        "date": _date_iso(game.date),
        "home_team_id": game.home_team_id,
        "away_team_id": game.away_team_id,
        "home_team": _team_label(game.home_team),
        "away_team": _team_label(game.away_team),
        "home_score": game.home_score,
        "away_score": game.away_score,
        "status": game.status,
        "attendance": game.attendance,
        "venue": game.venue or "",
        "notes": game.notes or "",
        "has_full_stats": game.has_full_stats(),
        "has_derived_metrics": game.has_derived_metrics(),
        "home_stats": _serialize_stats(stats.get(game.home_team_id)),
        "away_stats": _serialize_stats(stats.get(game.away_team_id)),
        "derived": [
            {
                "team_id": row.team_id,
                "team": _team_label(row.team),
                "win": row.win,
                "point_margin": row.point_margin,
                "trb_diff": row.trb_diff,
                "fg_pct_diff": row.fg_pct_diff,
                "turnover_diff": row.turnover_diff,
                "computed_at": _iso(row.computed_at),
            }
            for row in derived.values()
        ],
    }


@bp.route("/admin/lab")
@login_required
def admin_lab_data():
    denied = _require_admin_json()
    if denied:
        return denied

    from app.analytics.models import (
        LabLeague, LabSeason, LabGame, LabPlayer, MetricDefinition,
    )
    games = LabGame.query.order_by(LabGame.date.desc(), LabGame.id.desc()).limit(25).all()
    players = LabPlayer.query.options(joinedload(LabPlayer.team)).order_by(LabPlayer.name).limit(150).all()
    metrics = MetricDefinition.query.order_by(MetricDefinition.name).all()
    teams = Team.query.order_by(Team.league, Team.city, Team.name).all()
    leagues = LabLeague.query.order_by(LabLeague.abbreviation).all()
    seasons = LabSeason.query.options(joinedload(LabSeason.league)).order_by(LabSeason.year.desc()).all()

    return ok(
        teams=[_serialize_team(t) for t in teams],
        leagues=[{"id": l.id, "name": l.name, "abbreviation": l.abbreviation, "sport_type": l.sport_type} for l in leagues],
        seasons=[_serialize_season(s) for s in seasons],
        games=[_serialize_game(g) for g in games],
        players=[
            {
                "id": p.id,
                "name": p.name,
                "position": p.position or "",
                "active": p.active,
                "team_id": p.team_id,
                "team": _team_label(p.team),
            }
            for p in players
        ],
        metrics=[
            {
                "id": m.id,
                "name": m.name,
                "slug": m.slug,
                "description": m.description or "",
                "formula_type": m.formula_type,
                "output_entity": m.output_entity,
                "parameters": m.parameters or "{}",
            }
            for m in metrics
        ],
    )


@bp.route("/admin/lab/seasons", methods=["POST"])
@login_required
def admin_create_season():
    denied = _require_admin_json()
    if denied:
        return denied
    from app.analytics.models import LabSeason
    d = request.get_json(silent=True) or {}
    league_id = _int_value(d.get("league_id"), None)
    year = _int_value(d.get("year"), None)
    season_type = d.get("season_type") or "regular"
    if not league_id or not year:
        return err("League and year are required")
    existing = LabSeason.query.filter_by(league_id=league_id, year=year, season_type=season_type).first()
    if existing:
        return err("Season already exists")
    season = LabSeason(league_id=league_id, year=year, season_type=season_type)
    db.session.add(season)
    _admin_audit("create_lab_season", None, f"{year} {season_type}")
    db.session.commit()
    return ok(season=_serialize_season(season)), 201


@bp.route("/admin/lab/games", methods=["POST"])
@login_required
def admin_create_game():
    denied = _require_admin_json()
    if denied:
        return denied
    from app.analytics.models import LabGame, TeamGameStats
    d = request.get_json(silent=True) or {}
    try:
        league_id = _int_value(d.get("league_id"), None)
        home_team_id = _int_value(d.get("home_team_id"), None)
        away_team_id = _int_value(d.get("away_team_id"), None)
        if not league_id or not home_team_id or not away_team_id:
            return err("League, home team, and away team are required")
        game_date = date.fromisoformat(d.get("date")) if d.get("date") else date.today()
        game = LabGame(
            league_id=league_id,
            season_id=_int_value(d.get("season_id"), None),
            date=game_date,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            home_score=_int_value(d.get("home_score")),
            away_score=_int_value(d.get("away_score")),
            status=d.get("status") or "final",
            attendance=_int_value(d.get("attendance"), None),
            venue=(d.get("venue") or "").strip() or None,
            notes=(d.get("notes") or "").strip() or None,
        )
        if game.home_team_id == game.away_team_id:
            return err("Home and away teams must be different")
        db.session.add(game)
        db.session.flush()
        home_stats = TeamGameStats(game_id=game.id, team_id=game.home_team_id, opponent_id=game.away_team_id, is_home=True)
        away_stats = TeamGameStats(game_id=game.id, team_id=game.away_team_id, opponent_id=game.home_team_id, is_home=False)
        home_stats.points = game.home_score
        away_stats.points = game.away_score
        _apply_stats_payload(home_stats, d.get("home_stats") or {})
        _apply_stats_payload(away_stats, d.get("away_stats") or {})
        db.session.add(home_stats)
        db.session.add(away_stats)
        _admin_audit("create_lab_game", None, f"{game.away_team_id} at {game.home_team_id} on {game.date}")
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Admin lab game create failed")
        return err(f"Game save failed: {exc}", 400)
    return ok(game=_serialize_game(game)), 201


@bp.route("/admin/lab/games/<int:game_id>/stats", methods=["PATCH"])
@login_required
def admin_update_game_stats(game_id):
    denied = _require_admin_json()
    if denied:
        return denied
    from app.analytics.models import LabGame, TeamGameStats
    game = LabGame.query.get_or_404(game_id)
    d = request.get_json(silent=True) or {}
    stats = {s.team_id: s for s in game.team_stats.all()}
    home_stats = stats.get(game.home_team_id) or TeamGameStats(
        game_id=game.id, team_id=game.home_team_id, opponent_id=game.away_team_id, is_home=True
    )
    away_stats = stats.get(game.away_team_id) or TeamGameStats(
        game_id=game.id, team_id=game.away_team_id, opponent_id=game.home_team_id, is_home=False
    )
    _apply_stats_payload(home_stats, d.get("home_stats") or {})
    _apply_stats_payload(away_stats, d.get("away_stats") or {})
    game.home_score = home_stats.points
    game.away_score = away_stats.points
    db.session.add(home_stats)
    db.session.add(away_stats)
    _admin_audit("update_lab_game_stats", None, f"game #{game.id}")
    db.session.commit()
    return ok(game=_serialize_game(game))


@bp.route("/admin/lab/games/<int:game_id>/derive", methods=["POST"])
@login_required
def admin_derive_game(game_id):
    denied = _require_admin_json()
    if denied:
        return denied
    from app.analytics.models import LabGame
    from app.analytics.metric_engine import compute_derived_for_game
    game = LabGame.query.get_or_404(game_id)
    try:
        compute_derived_for_game(game_id)
        _admin_audit("derive_lab_game", None, f"game #{game_id}")
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return err(str(exc), 400)
    return ok(game=_serialize_game(game))


@bp.route("/admin/lab/players", methods=["POST"])
@login_required
def admin_create_player():
    denied = _require_admin_json()
    if denied:
        return denied
    from app.analytics.models import LabPlayer
    d = request.get_json(silent=True) or {}
    team_id = _int_value(d.get("team_id"), None)
    name = (d.get("name") or "").strip()
    position = (d.get("position") or "").strip() or None
    if not team_id or not name:
        return err("Team and player name are required")
    player = LabPlayer(team_id=team_id, name=name, position=position)
    db.session.add(player)
    _admin_audit("create_lab_player", None, name)
    db.session.commit()
    return ok(player={"id": player.id, "name": player.name, "position": player.position or "", "team_id": player.team_id}), 201


@bp.route("/admin/lab/metrics", methods=["POST"])
@login_required
def admin_create_metric():
    denied = _require_admin_json()
    if denied:
        return denied
    from app.analytics.models import MetricDefinition
    d = request.get_json(silent=True) or {}
    name = (d.get("name") or "").strip()
    slug = (d.get("slug") or name).strip().lower().replace(" ", "_")
    if not name or not slug:
        return err("Name and slug are required")
    if MetricDefinition.query.filter_by(slug=slug).first():
        return err("Metric slug already exists")
    metric = MetricDefinition(
        name=name,
        slug=slug,
        description=(d.get("description") or "").strip(),
        formula_type=d.get("formula_type") or "python",
        parameters=(d.get("parameters") or "{}").strip(),
        output_entity=d.get("output_entity") or "game_team",
    )
    db.session.add(metric)
    _admin_audit("create_metric", None, slug)
    db.session.commit()
    return ok(metric={"id": metric.id, "name": metric.name, "slug": metric.slug}), 201


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
    email = d.get("email", "").strip().lower()
    if not email or "@" not in email:
        return err("Enter a valid email address")

    invite_url = f"{request.host_url}groups/join/{g.invite_code}"

    # Use the shared email service (sets the Resend key + verified MAIL_FROM domain
    # + branded HTML). Returns False when RESEND_API_KEY isn't configured.
    sent = False
    try:
        from app.services.email_service import send_invite_email
        sent = send_invite_email(email, current_user, g, invite_url)
    except Exception as e:
        current_app.logger.error(f"Invite email failed: {e}")

    # Fallback: if the invitee already has an account, drop an in-app notification
    # so the invite lands even when email delivery is down.
    existing = User.query.filter_by(email=email).first()
    if existing and existing.id != current_user.id:
        db.session.add(Notification(
            user_id=existing.id,
            type="group_invite",
            message=f"{current_user.shown_name} invited you to join {g.name}",
            link_url=f"/groups/join/{g.invite_code}",
        ))
        db.session.commit()

    return ok(sent=bool(sent))


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
    try:
        _cascade_delete_group(group_id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Group deletion failed for group %s", group_id)
        return err("Group deletion failed. Please try again or contact support.", 500)
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
    group_ids = [m.group_id for m in memberships] or [-1]
    groups    = [{"id": m.group_id, "name": m.group.name} for m in memberships if m.group]

    # Query 2 — all active thread data + last message in one CTE. Includes
    # incident/group chats from the user's groups plus direct chats where the
    # current user is one of the two participants.
    # Replaces: threads query (deep 3-level joinedload) + last-msg subquery +
    #           last-msg fetch + redundant Group query  =  was 4 separate round trips.
    rows = db.session.execute(text("""
        WITH candidate_threads AS (
            SELECT id
            FROM game_threads
            WHERE status = 'active'
              AND (
                group_id = ANY(:gids)
                OR (
                  thread_type = 'direct_chat'
                  AND (created_by_user_id = :uid OR target_user_id = :uid)
                )
              )
        ),
        last_msgs AS (
            SELECT DISTINCT ON (thread_id)
                thread_id, body, created_at, user_id
            FROM game_thread_messages
            WHERE thread_id IN (SELECT id FROM candidate_threads)
            AND is_deleted = false
            ORDER BY thread_id, id DESC
        )
        SELECT
            gt.id,
            gt.title,
            gt.thread_type,
            gt.status,
            gt.group_id,
            gt.created_by_user_id,
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
            CASE
                WHEN cu.display_preference = 'real_name'
                     AND cu.first_name IS NOT NULL
                     AND cu.last_name  IS NOT NULL
                THEN cu.first_name || ' ' || cu.last_name
                ELSE cu.display_name
            END             AS creator_user_name,
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
        LEFT JOIN users  cu             ON cu.id = gt.created_by_user_id
        LEFT JOIN group_triggers  gtr   ON gtr.id = gt.group_trigger_id
        LEFT JOIN game_events     ge    ON ge.id  = gtr.game_event_id
        LEFT JOIN incident_reports ir   ON ir.id  = ge.incident_report_id
        LEFT JOIN last_msgs        lm   ON lm.thread_id = gt.id
        LEFT JOIN users            lmu  ON lmu.id = lm.user_id
        WHERE gt.id IN (SELECT id FROM candidate_threads)
        ORDER BY gt.updated_at DESC
    """), {"gids": group_ids, "uid": uid}).fetchall()

    thread_ids = [r.id for r in rows]
    from app.services import thread_state
    last_msg_at = {
        r.id: (r.last_msg_at if r.last_msg_at else r.created_at)
        for r in rows
    }
    categories = thread_state.categorize(
        thread_state.states_for(uid, thread_ids),
        thread_ids,
        last_msg_at,
    )
    rows = [r for r in rows if categories.get(r.id) != "purged"]
    thread_ids = [r.id for r in rows]
    cat_counts = {"active": 0, "archived": 0, "deleted": 0}
    for r in rows:
        cat = categories.get(r.id, "active")
        if cat in cat_counts:
            cat_counts[cat] += 1

    from app.services.activity import unread_map, message_counts, vote_count_map
    unread = unread_map(uid, thread_ids)
    counts = message_counts(thread_ids)
    votes  = vote_count_map(thread_ids)

    threads   = []
    last_msgs = {}
    for r in rows:
        thread_type = r.thread_type or "incident"
        direct_other_name = (
            r.target_user_name if r.created_by_user_id == uid else r.creator_user_name
        )
        display_title = r.title or r.group_name or ""
        avatar_label = (r.team_abbr or "?")[:3]
        avatar_color = r.team_color or "#333"
        if thread_type == "group_chat":
            display_title = r.group_name or r.title or "Group Chat"
            avatar_label = "".join(part[:1] for part in display_title.split()[:2]).upper() or "GC"
            avatar_color = "#d93348"
        elif thread_type == "direct_chat":
            display_title = direct_other_name or "Direct Chat"
            avatar_label = "".join(part[:1] for part in display_title.split()[:2]).upper() or "DM"
            avatar_color = "#d93348"

        threads.append({
            "id":               r.id,
            "title":            r.title,
            "display_title":    display_title,
            "thread_type":      thread_type,
            "category":         categories.get(r.id, "active"),
            "status":           r.status,
            "group_id":         r.group_id,
            "group_name":       r.group_name   or "",
            "created_by_user_id": r.created_by_user_id,
            "created_by_user_name": r.creator_user_name or "",
            "target_user_id":   r.target_user_id,
            "target_user_name": r.target_user_name or "",
            "team_abbr":        r.team_abbr    or "",
            "team_name":        r.team_name    or "",
            "team_color":       r.team_color   or "#333",
            "avatar_label":     avatar_label,
            "avatar_color":     avatar_color,
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

    return ok(threads=threads, last_msgs=last_msgs, groups=groups, cat_counts=cat_counts)


@bp.route("/threads", methods=["POST"])
@login_required
def create_chat_thread():
    d = request.get_json(silent=True) or {}
    chat_type = d.get("type")

    if chat_type == "group":
        group_id = d.get("group_id")
        if not group_id:
            return err("Group is required")
        group = Group.query.get_or_404(int(group_id))
        if not group.is_member(current_user.id):
            return err("Not a member of this group", 403)

        thread = GameThread.query.filter_by(
            thread_type="group_chat",
            group_id=group.id,
            status="active",
        ).first()
        created = False
        if not thread:
            thread = GameThread(
                thread_type="group_chat",
                group_id=group.id,
                created_by_user_id=current_user.id,
                title=group.name,
                status="active",
            )
            db.session.add(thread)
            db.session.flush()
            created = True
        else:
            _restore_local_thread_state(thread.id)
        db.session.commit()
        return ok(thread_id=thread.id, created=created), 201

    if chat_type == "direct":
        user_id = d.get("user_id")
        if not user_id:
            return err("User is required")
        other_id = int(user_id)
        if other_id == current_user.id:
            return err("You can't start a chat with yourself", 400)
        other = User.query.get_or_404(other_id)
        if other_id in current_user.hidden_user_ids():
            return err("You can't start a chat with this user", 403)
        if not _has_accepted_friendship(other_id):
            return err("You can only message friends", 403)

        thread = GameThread.query.filter(
            GameThread.thread_type == "direct_chat",
            db.or_(
                db.and_(
                    GameThread.created_by_user_id == current_user.id,
                    GameThread.target_user_id == other_id,
                ),
                db.and_(
                    GameThread.created_by_user_id == other_id,
                    GameThread.target_user_id == current_user.id,
                ),
            ),
            GameThread.status == "active",
        ).first()
        created = False
        if not thread:
            thread = GameThread(
                thread_type="direct_chat",
                created_by_user_id=current_user.id,
                target_user_id=other.id,
                title=other.shown_name,
                status="active",
            )
            db.session.add(thread)
            db.session.flush()
            created = True
        else:
            _restore_local_thread_state(thread.id)
        db.session.commit()
        return ok(thread_id=thread.id, created=created), 201

    return err("Choose a group or friend")


@bp.route("/threads/<int:thread_id>")
@login_required
def get_thread(thread_id):
    thread = GameThread.query.get_or_404(thread_id)
    if not _can_access_thread(thread):
        return err("Not authorized", 403)
    member = _thread_member(thread)

    _mq = (
        GameThreadMessage.query
        .filter_by(thread_id=thread_id, is_deleted=False)
        .options(
            joinedload(GameThreadMessage.author),
            joinedload(GameThreadMessage.reactions),
        )
    )
    _hidden = current_user.hidden_user_ids()
    if _hidden:
        _mq = _mq.filter(GameThreadMessage.user_id.notin_(_hidden))
    from app.services.thread_state import cleared_at_for
    cleared = cleared_at_for(current_user.id, thread_id)
    if cleared:
        _mq = _mq.filter(GameThreadMessage.created_at > cleared)
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
    from app.services.activity import mark_thread_read
    mark_thread_read(current_user.id, thread_id)
    db.session.commit()

    thread_type = thread.thread_type or "incident"
    other = _other_direct_user(thread)
    display_title = thread.title or ""
    if thread_type == "group_chat":
        display_title = thread.group.name if thread.group else (thread.title or "Group Chat")
    elif thread_type == "direct_chat":
        display_title = other.shown_name if other else "Direct Chat"

    return ok(
        thread={
            "id":               thread.id,
            "title":            display_title,
            "raw_title":        thread.title,
            "thread_type":      thread_type,
            "status":           thread.status,
            "group_name":       thread.group.name if thread.group else "",
            "group_id":         thread.group_id,
            "created_by_user_id": thread.created_by_user_id,
            "created_by_user_name": thread.created_by.shown_name if thread.created_by else "",
            "target_user_id":   thread.target_user_id,
            "target_user_name": thread.target_user.shown_name if thread.target_user else "",
            "team_abbr":        thread.target_team.abbreviation if thread.target_team else "",
            "team_name":        thread.target_team.name if thread.target_team else "",
            "team_color":       thread.target_team.primary_color if thread.target_team else "#333",
            "votes":            thread.vote_counts() if thread_type == "incident" else {"confirm": 0, "dismiss": 0, "redeem": 0},
            "user_vote":        thread.user_vote(current_user.id) if thread_type == "incident" else None,
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
    if not _can_access_thread(thread):
        return err("Not authorized", 403)

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
    if thread.group_id:
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
    if (thread.thread_type or "incident") != "incident":
        return err("Voting is only available on report threads", 400)
    member = _thread_member(thread)
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
    if not _can_access_thread(thread):
        return err("Not authorized", 403)
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


@bp.route("/blocked-users")
@login_required
def blocked_users():
    rows = (
        BlockedUser.query
        .filter_by(blocker_id=current_user.id)
        .options(joinedload(BlockedUser.blocked))
        .order_by(BlockedUser.created_at.desc())
        .all()
    )
    users = []
    for row in rows:
        if not row.blocked:
            continue
        users.append({
            "id": row.blocked_id,
            "name": row.blocked.shown_name,
            "uid": row.blocked.uid,
            "blocked_at": row.created_at.isoformat() if row.created_at else None,
        })
    return ok(blocked_users=users)


@bp.route("/blocked-users/<int:user_id>", methods=["DELETE"])
@login_required
def unblock_user(user_id):
    BlockedUser.query.filter_by(
        blocker_id=current_user.id,
        blocked_id=user_id,
    ).delete(synchronize_session=False)
    db.session.commit()
    return ok()


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


@bp.route("/friends/<int:user_id>/block", methods=["POST"])
@login_required
def block_user(user_id):
    """Block a user: severs friendship + pending requests and hides each user's
    content from the other (enforced via User.hidden_user_ids)."""
    if user_id == current_user.id:
        return err("You can't block yourself", 400)
    target = db.session.get(User, user_id)
    if not target:
        return err("User not found", 404)
    if not BlockedUser.query.filter_by(blocker_id=current_user.id, blocked_id=user_id).first():
        db.session.add(BlockedUser(blocker_id=current_user.id, blocked_id=user_id))
    FriendRequest.query.filter(
        db.or_(
            db.and_(FriendRequest.from_user_id == current_user.id, FriendRequest.to_user_id == user_id),
            db.and_(FriendRequest.from_user_id == user_id, FriendRequest.to_user_id == current_user.id),
        )
    ).delete(synchronize_session=False)
    db.session.commit()
    return ok(blocked=True)


@bp.route("/users/<int:user_id>/report", methods=["POST"])
@login_required
def report_user(user_id):
    """Report a user for moderation. There's no dedicated user-report table, so
    file it as a support ticket — it lands in the admin queue (/admin/support)."""
    if user_id == current_user.id:
        return err("You can't report yourself", 400)
    target = db.session.get(User, user_id)
    if not target:
        return err("User not found", 404)
    d = request.get_json(silent=True) or {}
    reason = (d.get("reason") or "").strip()
    ticket = SupportTicket(
        user_id=current_user.id,
        subject=f"User report: @{target.uid}",
        category="report",
        description=(
            f"Reported user: {target.shown_name} (@{target.uid}, id {target.id}).\n\n"
            f"Reason: {reason or 'No reason provided.'}"
        ),
        status="received",
    )
    db.session.add(ticket)
    db.session.commit()
    return ok(reported=True)


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
