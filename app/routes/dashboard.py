import secrets

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user, logout_user, login_user
from sqlalchemy import func
from app.models import db, Team, UserFavoriteTeam, GroupMember, GameThread, GameThreadMessage

dashboard_bp = Blueprint("dashboard", __name__)

ALL_LEAGUES = ["NBA", "NFL", "MLB", "NHL", "EPL", "FIFA", "F1", "PGA"]

LEAGUE_LABELS = {
    "NBA": "NBA",
    "NFL": "NFL",
    "MLB": "MLB",
    "NHL": "NHL",
    "EPL": "Premier League",
    "FIFA": "FIFA / International",
    "F1": "Formula 1",
    "PGA": "PGA Tour",
}


def _get_teams_by_league():
    all_teams = Team.query.order_by(Team.league, Team.city, Team.name).all()
    by_league = {}
    for team in all_teams:
        by_league.setdefault(team.league, []).append(team)
    return by_league


def _upsert_fav(user_id, league, team_id):
    uft = UserFavoriteTeam.query.filter_by(user_id=user_id, league=league).first()
    if uft:
        uft.team_id = team_id
    else:
        uft = UserFavoriteTeam(user_id=user_id, league=league, team_id=team_id)
        db.session.add(uft)


@dashboard_bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    teams_by_league = _get_teams_by_league()

    if request.method == "POST":
        selected = 0
        for league in ALL_LEAGUES:
            team_id = request.form.get(f"{league.lower()}_team_id")
            if team_id:
                _upsert_fav(current_user.id, league, int(team_id))
                selected += 1

        if selected == 0:
            flash("Pick at least one team to follow.", "error")
            return render_template(
                "onboarding.html",
                teams_by_league=teams_by_league,
                league_labels=LEAGUE_LABELS,
                all_leagues=ALL_LEAGUES,
            )

        db.session.commit()
        flash("Teams saved! Now create or join a group.", "success")
        return redirect(url_for("dashboard.dashboard"))

    return render_template(
        "onboarding.html",
        teams_by_league=teams_by_league,
        league_labels=LEAGUE_LABELS,
        all_leagues=ALL_LEAGUES,
    )


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    from sqlalchemy.orm import joinedload
    from app.services.activity import unread_map, message_counts, latest_messages

    memberships = (
        GroupMember.query
        .options(joinedload(GroupMember.group))
        .filter_by(user_id=current_user.id)
        .all()
    )
    group_ids = [m.group_id for m in memberships]

    active_threads = []
    msg_counts = {}
    unread_counts = {}
    member_counts = {}
    latest_by_group = {}   # group_id -> latest active GameThread
    group_unread = {}      # group_id -> total unread messages in active threads
    last_msgs = {}         # thread_id -> last GameThreadMessage

    if group_ids:
        # Member counts per group — one query
        rows = (
            db.session.query(GroupMember.group_id, func.count(GroupMember.id))
            .filter(GroupMember.group_id.in_(group_ids))
            .group_by(GroupMember.group_id)
            .all()
        )
        member_counts = {gid: cnt for gid, cnt in rows}

        # All active threads, newest activity first — one query.
        # First seen per group = that group's latest thread.
        all_active = (
            GameThread.query
            .options(joinedload(GameThread.group))
            .filter(
                GameThread.group_id.in_(group_ids),
                GameThread.status == "active",
            )
            .order_by(GameThread.updated_at.desc())
            .all()
        )
        for t in all_active:
            latest_by_group.setdefault(t.group_id, t)
        active_threads = all_active[:10]

        if all_active:
            thread_ids = [t.id for t in all_active]
            msg_counts = message_counts(thread_ids)
            unread_counts = unread_map(current_user.id, thread_ids)
            for t in all_active:
                if unread_counts.get(t.id, 0) > 0:
                    group_unread[t.group_id] = (
                        group_unread.get(t.group_id, 0) + unread_counts[t.id]
                    )
            last_msgs = latest_messages([t.id for t in latest_by_group.values()])

    fav_teams = {uft.league: uft.team for uft in current_user.favorite_teams.all()}

    groups = [{"group": m.group, "member": m} for m in memberships]

    # Desktop side panel: hottest threads + recent group activity
    hot_threads = sorted(
        active_threads, key=lambda t: t.hot_score or 0, reverse=True
    )[:3]
    recent_events = []
    if group_ids:
        from sqlalchemy.orm import joinedload as _jl
        from app.models import ActivityEvent
        recent_events = (
            ActivityEvent.query
            .options(_jl(ActivityEvent.actor))
            .filter(ActivityEvent.group_id.in_(group_ids))
            .order_by(ActivityEvent.created_at.desc())
            .limit(6)
            .all()
        )

    # Header stats
    unread_thread_count = sum(1 for c in unread_counts.values() if c > 0)
    stats = {
        "groups": len(groups),
        "unread_threads": unread_thread_count,
        "active_threads": len(active_threads),
    }

    # Show profile completion prompt for existing users who haven't set names yet
    show_profile_prompt = (
        not current_user.has_completed_profile
        and not (current_user.first_name and current_user.last_name)
    )

    return render_template(
        "dashboard.html",
        groups=groups,
        active_threads=active_threads,
        msg_counts=msg_counts,
        unread_counts=unread_counts,
        member_counts=member_counts,
        latest_by_group=latest_by_group,
        group_unread=group_unread,
        last_msgs=last_msgs,
        stats=stats,
        hot_threads=hot_threads,
        recent_events=recent_events,
        fav_teams=fav_teams,
        fav_nba=fav_teams.get("NBA"),
        fav_nfl=fav_teams.get("NFL"),
        show_profile_prompt=show_profile_prompt,
    )


@dashboard_bp.route("/profile/complete", methods=["POST"])
@login_required
def complete_profile():
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    display_preference = request.form.get("display_preference", "username")

    if first_name:
        current_user.first_name = first_name
    if last_name:
        current_user.last_name = last_name
    if display_preference in ("username", "real_name"):
        current_user.display_preference = display_preference

    current_user.has_completed_profile = True
    db.session.commit()
    flash("Profile updated.", "success")
    return redirect(url_for("dashboard.dashboard"))


@dashboard_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    teams_by_league = _get_teams_by_league()
    fav_teams = {uft.league: uft.team for uft in current_user.favorite_teams.all()}

    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        display_preference = request.form.get("display_preference", "username")
        avatar_url = request.form.get("avatar_url", "").strip()

        if display_name:
            current_user.display_name = display_name
        if first_name:
            current_user.first_name = first_name
        if last_name:
            current_user.last_name = last_name
        if display_preference in ("username", "real_name"):
            current_user.display_preference = display_preference
        if avatar_url:
            current_user.avatar_url = avatar_url

        if first_name and last_name:
            current_user.has_completed_profile = True

        for league in ALL_LEAGUES:
            team_id = request.form.get(f"{league.lower()}_team_id")
            if team_id:
                _upsert_fav(current_user.id, league, int(team_id))

        # Password change
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        confirm_pw = request.form.get("confirm_password", "")
        # Which devices stay signed in after a password change. Chosen in the
        # confirmation sheet on the settings page; only honored when the
        # password actually changes.
        session_scope = request.form.get("session_scope", "")
        password_changed = False
        if current_pw or new_pw:
            if not current_user.check_password(current_pw):
                flash("Current password is incorrect.", "error")
            elif len(new_pw) < 6:
                flash("New password must be at least 6 characters.", "error")
            elif new_pw != confirm_pw:
                flash("New passwords do not match.", "error")
            else:
                current_user.set_password(new_pw)
                password_changed = True

        # Rotating the session token invalidates every other device's cookie.
        if password_changed and session_scope in ("this_device", "sign_out_all"):
            current_user.session_token = secrets.token_hex(16)

        db.session.commit()

        if password_changed and session_scope == "sign_out_all":
            logout_user()
            flash("Password updated. Signed out of all devices — please log in again.", "success")
            return redirect(url_for("auth.login"))

        if password_changed and session_scope == "this_device":
            # Re-issue this device's cookie with the new token so only it survives.
            login_user(current_user, remember=True)
            flash("Password updated. Other devices have been signed out.", "success")
            return redirect(url_for("dashboard.settings"))

        flash("Password updated." if password_changed else "Account updated.", "success")
        return redirect(url_for("dashboard.settings"))

    return render_template(
        "settings.html",
        teams_by_league=teams_by_league,
        league_labels=LEAGUE_LABELS,
        all_leagues=ALL_LEAGUES,
        fav_teams=fav_teams,
    )


@dashboard_bp.route("/settings/delete-account", methods=["POST"])
@login_required
def delete_account():
    password = request.form.get("confirm_password", "")
    if not current_user.check_password(password):
        flash("Incorrect password. Account not deleted.", "error")
        return redirect(url_for("dashboard.settings"))

    user    = current_user._get_current_object()
    user_id = user.id

    # Log out first so Flask-Login releases the session reference
    logout_user()

    # Full cascade — same helper used by admin delete
    # (handles owned groups, friends, messages, receipts, notifications, etc.)
    from app.routes.admin import _cascade_delete_user
    _cascade_delete_user(user_id)

    # Delete the user record itself
    user_obj = db.session.get(User, user_id)
    if user_obj:
        db.session.delete(user_obj)
    db.session.commit()

    flash("Your account has been permanently deleted.", "info")
    return redirect(url_for("auth.index"))


@dashboard_bp.route("/notifications")
@login_required
def notifications():
    from app.models import Notification, FriendRequest
    all_notifs = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(100)
        .all()
    )
    # "Messages" = every informational notification EXCEPT group invites (own tab)
    # and friend_request (shown as an actionable row below). This catch-all means
    # new notification types (e.g. friend_accepted) can never be silently dropped.
    invites  = [n for n in all_notifs if n.type == "group_invite"]
    messages = [n for n in all_notifs if n.type not in ("group_invite", "friend_request")]

    pending_fr = (
        FriendRequest.query
        .filter_by(to_user_id=current_user.id, status="pending")
        .order_by(FriendRequest.created_at.desc())
        .all()
    )

    # Mark all notifications as read on page load
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return render_template("dashboard/notifications.html",
                           messages=messages, invites=invites, pending_fr=pending_fr)


@dashboard_bp.route("/notifications/mark-read", methods=["POST"])
@login_required
def notifications_mark_read():
    from app.models import Notification
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return redirect(url_for("dashboard.notifications"))


@dashboard_bp.route("/threads")
@login_required
def threads_list():
    """All active threads across every group the current user belongs to."""
    from sqlalchemy.orm import joinedload
    from datetime import date, timedelta

    memberships = (
        GroupMember.query
        .options(joinedload(GroupMember.group))
        .filter_by(user_id=current_user.id)
        .all()
    )
    group_ids = [m.group_id for m in memberships]

    from app.services.activity import unread_map, message_counts, latest_messages

    threads = []
    msg_counts = {}
    last_msgs = {}
    unread_counts = {}
    categories = {}
    cat_counts = {"active": 0, "archived": 0, "deleted": 0}

    if group_ids:
        from app.models import GroupTrigger, GameEvent
        from app.services import thread_state
        threads = (
            GameThread.query
            .options(
                joinedload(GameThread.target_user),
                joinedload(GameThread.target_team),
                joinedload(GameThread.group),
                # Incident type shown per row — avoid 3 lazy loads per thread
                joinedload(GameThread.group_trigger)
                .joinedload(GroupTrigger.game_event)
                .joinedload(GameEvent.incident_report),
            )
            .filter(
                GameThread.group_id.in_(group_ids),
                GameThread.status == "active",
            )
            .order_by(GameThread.updated_at.desc())
            .all()
        )
        if threads:
            thread_ids = [t.id for t in threads]
            msg_counts = message_counts(thread_ids)
            last_msgs = latest_messages(thread_ids)
            unread_counts = unread_map(current_user.id, thread_ids)

            # Per-user archive / local-delete categorization
            states = thread_state.states_for(current_user.id, thread_ids)
            last_msg_at = {
                t.id: (last_msgs[t.id].created_at if last_msgs.get(t.id) else t.created_at)
                for t in threads
            }
            categories = thread_state.categorize(states, thread_ids, last_msg_at)
            # Purged threads (deleted > 30d, no new activity) show nowhere
            threads = [t for t in threads if categories.get(t.id) != "purged"]
            for t in threads:
                cat_counts[categories.get(t.id, "active")] = \
                    cat_counts.get(categories.get(t.id, "active"), 0) + 1

    fav_team_ids = {uft.team_id for uft in current_user.favorite_teams.all()}

    today     = date.today()
    yesterday = today - timedelta(days=1)

    return render_template(
        "dashboard/threads.html",
        threads=threads,
        msg_counts=msg_counts,
        last_msgs=last_msgs,
        unread_counts=unread_counts,
        fav_team_ids=fav_team_ids,
        memberships=memberships,
        categories=categories,
        cat_counts=cat_counts,
        today=today,
        yesterday=yesterday,
    )


@dashboard_bp.route("/more")
@login_required
def more():
    """More hub — settings, support, legal, admin, logout."""
    from app.models import IncidentReport

    groups_count = GroupMember.query.filter_by(user_id=current_user.id).count()
    group_ids = [
        gid for (gid,) in db.session.query(GroupMember.group_id)
        .filter_by(user_id=current_user.id).all()
    ]
    threads_count = 0
    if group_ids:
        threads_count = GameThread.query.filter(
            GameThread.group_id.in_(group_ids)
        ).count()
    active_cases = IncidentReport.query.filter_by(
        target_user_id=current_user.id, status="active"
    ).count()

    fav_teams = [uft.team for uft in current_user.favorite_teams.all() if uft.team]

    return render_template(
        "dashboard/more.html",
        account_stats={
            "groups": groups_count,
            "threads": threads_count,
            "active_cases": active_cases,
        },
        fav_teams=fav_teams,
    )
