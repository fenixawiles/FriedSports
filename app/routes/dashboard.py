from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, Team, UserFavoriteTeam, GroupMember, GameThread

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
    """Return {league: [team, ...]} for all leagues."""
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
    memberships = GroupMember.query.filter_by(user_id=current_user.id).all()
    group_ids = [m.group_id for m in memberships]

    active_threads = []
    if group_ids:
        active_threads = GameThread.query.filter(
            GameThread.group_id.in_(group_ids),
            GameThread.status == "active",
        ).order_by(GameThread.created_at.desc()).limit(10).all()

    # Build fav teams dict across all leagues
    fav_teams = {uft.league: uft.team for uft in current_user.favorite_teams.all()}

    # User's scores across all groups
    total_shame = sum(m.shame_score or 0 for m in memberships)
    total_bragging = sum(m.bragging_rights_score or 0 for m in memberships)
    total_trash = sum(m.trash_talk_score or 0 for m in memberships)

    from app.models import Group
    groups = [
        {"group": Group.query.get(m.group_id), "member": m}
        for m in memberships
    ]

    return render_template(
        "dashboard.html",
        groups=groups,
        active_threads=active_threads,
        fav_teams=fav_teams,
        # Legacy compat — keep these for templates that reference them
        fav_nba=fav_teams.get("NBA"),
        fav_nfl=fav_teams.get("NFL"),
        total_shame=total_shame,
        total_bragging=total_bragging,
        total_trash=total_trash,
    )


@dashboard_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    teams_by_league = _get_teams_by_league()
    fav_teams = {uft.league: uft.team for uft in current_user.favorite_teams.all()}

    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        avatar_url = request.form.get("avatar_url", "").strip()

        if display_name:
            current_user.display_name = display_name
        if avatar_url:
            current_user.avatar_url = avatar_url

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
        flash("Settings updated.", "success")
        return redirect(url_for("dashboard.settings"))

    return render_template(
        "settings.html",
        teams_by_league=teams_by_league,
        league_labels=LEAGUE_LABELS,
        all_leagues=ALL_LEAGUES,
        fav_teams=fav_teams,
    )
