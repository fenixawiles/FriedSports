from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user, logout_user
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
    memberships = (
        GroupMember.query
        .options(joinedload(GroupMember.group))
        .filter_by(user_id=current_user.id)
        .all()
    )
    group_ids = [m.group_id for m in memberships]

    active_threads = []
    msg_counts = {}
    if group_ids:
        active_threads = (
            GameThread.query
            .filter(
                GameThread.group_id.in_(group_ids),
                GameThread.status == "active",
            )
            .order_by(GameThread.created_at.desc())
            .limit(10)
            .all()
        )
        # Batch message counts — single query instead of N+1
        if active_threads:
            thread_ids = [t.id for t in active_threads]
            counts = (
                db.session.query(
                    GameThreadMessage.thread_id,
                    func.count(GameThreadMessage.id).label("cnt"),
                )
                .filter(
                    GameThreadMessage.thread_id.in_(thread_ids),
                    GameThreadMessage.is_deleted == False,
                )
                .group_by(GameThreadMessage.thread_id)
                .all()
            )
            msg_counts = {tid: cnt for tid, cnt in counts}

    fav_teams = {uft.league: uft.team for uft in current_user.favorite_teams.all()}

    groups = [{"group": m.group, "member": m} for m in memberships]

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
        if current_pw or new_pw:
            if not current_user.check_password(current_pw):
                flash("Current password is incorrect.", "error")
            elif len(new_pw) < 6:
                flash("New password must be at least 6 characters.", "error")
            elif new_pw != confirm_pw:
                flash("New passwords do not match.", "error")
            else:
                current_user.set_password(new_pw)
                flash("Password updated.", "success")

        db.session.commit()
        flash("Account updated.", "success")
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
    messages = [n for n in all_notifs if n.type in ("thread_started", "message_received")]
    invites  = [n for n in all_notifs if n.type == "group_invite"]

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
