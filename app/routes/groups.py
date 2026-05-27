import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.models import db, Group, GroupMember, GameThread, Receipt
from app.services.scoring import compute_leaderboards

groups_bp = Blueprint("groups", __name__)

INCIDENT_TYPES = [
    ("BLOWOUT_ALERT", "Getting Blown Out"),
    ("CHOKED_LEAD", "Choked a Lead"),
    ("FRAUD_WATCH", "Fraud Watch"),
    ("UPSET_ALERT", "Upset Loss"),
    ("DISASTER_QUARTER", "Disaster Quarter"),
    ("PLAYOFF_COLLAPSE", "Playoff Collapse"),
    ("SHUTOUT_RISK", "Shutout Risk"),
    ("FINAL_LOSS", "Final Loss"),
    ("RIVAL_LOSS", "Rival Loss"),
    ("PREMATURE_SLANDER", "Premature Slander"),
]

SEVERITIES = [
    (1, "Mild concern"),
    (2, "Noticeable fraud"),
    (3, "Active collapse"),
    (4, "Public embarrassment"),
    (5, "Generational slander"),
]


def _require_member(group, user_id):
    member = group.get_member(user_id)
    if not member:
        if group.privacy != "public_readonly":
            abort(403)
    return member


@groups_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        league_scope = request.form.get("league_scope", "MULTI")
        privacy = request.form.get("privacy", "private")

        if not name:
            flash("Group name is required.", "error")
            return render_template("groups/new.html")
        if len(name) > 100:
            flash("Group name must be under 100 characters.", "error")
            return render_template("groups/new.html")

        group = Group(
            name=name,
            owner_id=current_user.id,
            league_scope=league_scope,
            privacy=privacy,
            invite_code=secrets.token_urlsafe(6),
        )
        db.session.add(group)
        db.session.flush()

        member = GroupMember(
            group_id=group.id,
            user_id=current_user.id,
            role="owner",
        )
        db.session.add(member)
        db.session.commit()
        flash(f'"{name}" created! Share your invite code: {group.invite_code}', "success")
        return redirect(url_for("groups.show", group_id=group.id))

    return render_template("groups/new.html")


@groups_bp.route("/<int:group_id>")
@login_required
def show(group_id):
    group = Group.query.get_or_404(group_id)
    member = _require_member(group, current_user.id)

    threads = GameThread.query.filter_by(
        group_id=group_id, status="active"
    ).order_by(GameThread.created_at.desc()).all()

    all_members = GroupMember.query.filter_by(group_id=group_id).all()
    from app.models import User
    members_with_users = [
        {"member": m, "user": User.query.get(m.user_id)}
        for m in all_members
    ]

    leaderboards = compute_leaderboards(group_id)

    receipts = Receipt.query.filter_by(group_id=group_id).order_by(
        Receipt.created_at.desc()
    ).limit(5).all()

    return render_template(
        "groups/show.html",
        group=group,
        member=member,
        threads=threads,
        members_with_users=members_with_users,
        leaderboards=leaderboards,
        receipts=receipts,
    )


@groups_bp.route("/<int:group_id>/report", methods=["GET", "POST"])
@login_required
def report_incident(group_id):
    from app.models import User, Team, IncidentReport, UserFavoriteTeam
    from app.services.incident_service import create_incident_thread

    group = Group.query.get_or_404(group_id)
    member = group.get_member(current_user.id)
    if not member:
        abort(403)

    all_members = GroupMember.query.filter_by(group_id=group_id).all()
    members_with_users = [
        {"member": m, "user": User.query.get(m.user_id)}
        for m in all_members
        if m.user_id != current_user.id
    ]

    if group.league_scope == "MULTI":
        all_teams = Team.query.order_by(Team.league, Team.city, Team.name).all()
    else:
        all_teams = Team.query.filter_by(league=group.league_scope).order_by(Team.city, Team.name).all()

    # Organize teams by league for optgroup dropdowns
    teams_by_league = {}
    for t in all_teams:
        teams_by_league.setdefault(t.league, []).append(t)

    # Build a flat id→{primary,secondary,abbr} map for JS color preview
    team_colors = {
        t.id: {
            "primary": t.primary_color,
            "secondary": t.secondary_color,
            "abbr": t.abbreviation,
            "name": t.name,
            "city": t.city,
        }
        for t in all_teams
    }

    # Build userId → [teamId, ...] map for JS team suggestions
    user_fav_teams = {}
    for item in members_with_users:
        favs = UserFavoriteTeam.query.filter_by(user_id=item["user"].id).all()
        user_fav_teams[str(item["user"].id)] = [uft.team_id for uft in favs]

    if request.method == "POST":
        target_user_id = request.form.get("target_user_id", type=int)
        target_team_id = request.form.get("target_team_id", type=int)
        incident_type = request.form.get("incident_type", "").strip()
        severity = request.form.get("severity", type=int, default=3)
        reported_score_text = request.form.get("reported_score_text", "").strip() or None
        description = request.form.get("description", "").strip() or None

        errors = []
        if not target_user_id:
            errors.append("Select a target.")
        if not target_team_id:
            errors.append("Select a team.")
        if not incident_type:
            errors.append("Select what happened.")
        if not severity or severity not in range(1, 6):
            errors.append("Select a severity level.")
        if target_user_id and target_user_id == current_user.id:
            errors.append("You cannot report yourself.")

        target_user = User.query.get(target_user_id) if target_user_id else None
        target_team = Team.query.get(target_team_id) if target_team_id else None

        if target_user_id and not target_user:
            errors.append("Invalid target user.")
        if target_team_id and not target_team:
            errors.append("Invalid team.")
        if target_user and not group.is_member(target_user_id):
            errors.append("Target must be a group member.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "groups/report.html",
                group=group, member=member,
                members_with_users=members_with_users,
                teams_by_league=teams_by_league,
                team_colors=team_colors,
                user_fav_teams=user_fav_teams,
                incident_types=INCIDENT_TYPES,
                severities=SEVERITIES,
            )

        report = IncidentReport(
            reporter_user_id=current_user.id,
            group_id=group_id,
            target_user_id=target_user_id,
            target_team_id=target_team_id,
            league=target_team.league,
            incident_type=incident_type,
            severity=severity,
            reported_score_text=reported_score_text,
            description=description,
            status="active",
        )
        db.session.add(report)
        db.session.flush()

        thread = create_incident_thread(report)
        db.session.commit()

        flash("Thread started.", "success")
        return redirect(url_for("threads.show", thread_id=thread.id))

    return render_template(
        "groups/report.html",
        group=group, member=member,
        members_with_users=members_with_users,
        teams_by_league=teams_by_league,
        team_colors=team_colors,
        user_fav_teams=user_fav_teams,
        incident_types=INCIDENT_TYPES,
        severities=SEVERITIES,
    )


@groups_bp.route("/join", methods=["GET", "POST"])
@login_required
def join_prompt():
    if request.method == "POST":
        code = request.form.get("invite_code", "").strip()
        if not code:
            flash("Enter an invite code.", "error")
            return render_template("groups/join_prompt.html")
        return redirect(url_for("groups.join", invite_code=code))
    return render_template("groups/join_prompt.html")


@groups_bp.route("/join/<invite_code>", methods=["GET", "POST"])
def join(invite_code):
    from flask_login import current_user
    group = Group.query.filter_by(invite_code=invite_code).first_or_404()

    # POST — actually join (must be authenticated)
    if request.method == "POST":
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=url_for("groups.join", invite_code=invite_code)))
        if group.is_member(current_user.id):
            flash("You're already in this group.", "info")
            return redirect(url_for("groups.show", group_id=group.id))
        member = GroupMember(
            group_id=group.id,
            user_id=current_user.id,
            role="member",
        )
        db.session.add(member)
        db.session.commit()
        flash(f'Joined "{group.name}"!', "success")
        return redirect(url_for("groups.show", group_id=group.id))

    # GET — public landing page, works for logged-in and logged-out users
    if current_user.is_authenticated and group.is_member(current_user.id):
        flash("You're already in this group.", "info")
        return redirect(url_for("groups.show", group_id=group.id))

    member_count = group.members.count()
    return render_template("groups/join.html", group=group, member_count=member_count)


@groups_bp.route("/<int:group_id>/regenerate-invite", methods=["POST"])
@login_required
def regenerate_invite(group_id):
    group = Group.query.get_or_404(group_id)
    member = group.get_member(current_user.id)
    if not member or member.role not in ("owner", "admin"):
        abort(403)
    group.invite_code = secrets.token_urlsafe(8)
    db.session.commit()
    flash("Invite link regenerated. The old link no longer works.", "success")
    return redirect(url_for("groups.show", group_id=group.id))


@groups_bp.route("/<int:group_id>/mute", methods=["POST"])
@login_required
def mute(group_id):
    group = Group.query.get_or_404(group_id)
    member = group.get_member(current_user.id)
    if not member:
        abort(403)
    member.mute_notifications = not member.mute_notifications
    db.session.commit()
    state = "muted" if member.mute_notifications else "unmuted"
    flash(f'Notifications {state} for "{group.name}".', "info")
    return redirect(url_for("groups.show", group_id=group_id))


@groups_bp.route("/<int:group_id>/leave", methods=["POST"])
@login_required
def leave(group_id):
    group = Group.query.get_or_404(group_id)
    member = group.get_member(current_user.id)
    if not member:
        abort(403)
    if member.role == "owner":
        flash("You must transfer ownership before leaving.", "error")
        return redirect(url_for("groups.show", group_id=group_id))
    db.session.delete(member)
    db.session.commit()
    flash(f'You left "{group.name}".', "info")
    return redirect(url_for("dashboard.dashboard"))


@groups_bp.route("/<int:group_id>/remove/<int:user_id>", methods=["POST"])
@login_required
def remove_member(group_id, user_id):
    group = Group.query.get_or_404(group_id)
    requester = group.get_member(current_user.id)
    if not requester or requester.role not in ("owner", "admin"):
        abort(403)
    if user_id == current_user.id:
        flash("You cannot remove yourself this way.", "error")
        return redirect(url_for("groups.show", group_id=group_id))
    target = group.get_member(user_id)
    if not target:
        flash("User not in group.", "error")
        return redirect(url_for("groups.show", group_id=group_id))
    if target.role == "owner":
        flash("Cannot remove the owner.", "error")
        return redirect(url_for("groups.show", group_id=group_id))
    db.session.delete(target)
    db.session.commit()
    flash("Member removed.", "info")
    return redirect(url_for("groups.show", group_id=group_id))


@groups_bp.route("/<int:group_id>/transfer-owner/<int:user_id>", methods=["POST"])
@login_required
def transfer_owner(group_id, user_id):
    group = Group.query.get_or_404(group_id)
    requester = group.get_member(current_user.id)
    if not requester or requester.role != "owner":
        abort(403)
    if user_id == current_user.id:
        flash("You're already the owner.", "error")
        return redirect(url_for("groups.show", group_id=group_id))
    new_owner = group.get_member(user_id)
    if not new_owner:
        abort(404)
    requester.role = "member"
    new_owner.role = "owner"
    group.owner_id = user_id
    db.session.commit()
    flash("Ownership transferred.", "success")
    return redirect(url_for("groups.show", group_id=group_id))
