import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import (db, Group, GroupMember, GameThread, GameThreadMessage, Receipt,
                        IncidentReport, GameEvent, GroupTrigger, MessageReaction, MessageReport,
                        User, Notification)

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

    # Batch message counts — one query instead of one per thread card
    thread_ids = [t.id for t in threads]
    msg_counts = {}
    if thread_ids:
        rows = (
            db.session.query(
                GameThreadMessage.thread_id,
                func.count(GameThreadMessage.id),
            )
            .filter(
                GameThreadMessage.thread_id.in_(thread_ids),
                GameThreadMessage.is_deleted == False,
            )
            .group_by(GameThreadMessage.thread_id)
            .all()
        )
        msg_counts = {tid: cnt for tid, cnt in rows}

    receipts = Receipt.query.filter_by(group_id=group_id).order_by(
        Receipt.created_at.desc()
    ).limit(5).all()

    return render_template(
        "groups/show.html",
        group=group,
        member=member,
        threads=threads,
        msg_counts=msg_counts,
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

    from sqlalchemy.orm import joinedload as _jl
    all_members = (
        GroupMember.query
        .options(_jl(GroupMember.user))
        .filter_by(group_id=group_id)
        .all()
    )
    members_with_users = [
        {"member": m, "user": m.user}
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

    # Batch-load all favorite teams for target members — one IN query vs N queries
    target_user_ids = [m.user_id for m in all_members if m.user_id != current_user.id]
    user_fav_teams = {}
    if target_user_ids:
        favs = UserFavoriteTeam.query.filter(
            UserFavoriteTeam.user_id.in_(target_user_ids)
        ).all()
        for uft in favs:
            user_fav_teams.setdefault(str(uft.user_id), []).append(uft.team_id)

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


@groups_bp.route("/<int:group_id>/invite-email", methods=["POST"])
@login_required
def invite_email(group_id):
    group = Group.query.get_or_404(group_id)
    member = group.get_member(current_user.id)
    if not member:
        abort(403)
    to_email = request.form.get("invite_email", "").strip().lower()
    if not to_email or "@" not in to_email:
        flash("Enter a valid email address.", "error")
        return redirect(url_for("groups.show", group_id=group_id))
    # request.host_url always ends with '/', so no rstrip/slash-join needed
    invite_url = f"{request.host_url}groups/join/{group.invite_code}"
    try:
        from app.services.email_service import send_invite_email
        send_invite_email(to_email, current_user, group, invite_url)
        flash(f"Invite sent to {to_email}.", "success")
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Invite email failed: {e}")
        flash("Couldn't send the invite right now. Copy the link instead.", "error")

    # If the invitee already has an account, create an in-app notification as a fallback
    existing_user = User.query.filter_by(email=to_email).first()
    if existing_user and existing_user.id != current_user.id:
        notif = Notification(
            user_id=existing_user.id,
            type="group_invite",
            message=f"{current_user.shown_name} invited you to join {group.name}",
            link_url=f"/groups/join/{group.invite_code}",
        )
        db.session.add(notif)
        db.session.commit()

    return redirect(url_for("groups.show", group_id=group_id))


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


# ── Group & thread deletion helpers ──────────────────────────────────────────

def _cascade_delete_group(group_id):
    """Delete a group and all its associated data in safe dependency order."""
    # Messages in threads in this group
    thread_ids = [t.id for t in GameThread.query.filter_by(group_id=group_id).all()]
    if thread_ids:
        MessageReaction.query.filter(
            MessageReaction.message_id.in_(
                db.session.query(GameThreadMessage.id)
                .filter(GameThreadMessage.thread_id.in_(thread_ids))
            )
        ).delete(synchronize_session=False)
        MessageReport.query.filter(
            MessageReport.message_id.in_(
                db.session.query(GameThreadMessage.id)
                .filter(GameThreadMessage.thread_id.in_(thread_ids))
            )
        ).delete(synchronize_session=False)
        GameThreadMessage.query.filter(
            GameThreadMessage.thread_id.in_(thread_ids)
        ).delete(synchronize_session=False)
        Receipt.query.filter(Receipt.thread_id.in_(thread_ids)).delete(synchronize_session=False)
    # Soft-delete threads
    GameThread.query.filter_by(group_id=group_id).update({"status": "deleted"})
    # Group triggers and incident reports — load once, not twice.
    all_triggers = GroupTrigger.query.filter_by(group_id=group_id).all()
    trigger_ids  = [t.id for t in all_triggers]
    if trigger_ids:
        event_ids = [gt.game_event_id for gt in all_triggers]
        GroupTrigger.query.filter_by(group_id=group_id).delete()
        if event_ids:
            IncidentReport.query.filter(
                IncidentReport.id.in_(
                    db.session.query(GameEvent.incident_report_id)
                    .filter(GameEvent.id.in_(event_ids))
                    .filter(GameEvent.incident_report_id.isnot(None))
                )
            ).delete(synchronize_session=False)
            GameEvent.query.filter(GameEvent.id.in_(event_ids)).delete(synchronize_session=False)
    GroupMember.query.filter_by(group_id=group_id).delete()
    Receipt.query.filter_by(group_id=group_id).delete()
    group = db.session.get(Group, group_id)
    if group:
        db.session.delete(group)
    db.session.flush()


@groups_bp.route("/<int:group_id>/delete", methods=["POST"])
@login_required
def delete_group(group_id):
    group = Group.query.get_or_404(group_id)
    member = group.get_member(current_user.id)
    if not member or member.role != "owner":
        abort(403)
    group_name = group.name
    _cascade_delete_group(group_id)
    db.session.commit()
    flash(f'"{group_name}" has been permanently deleted.', "info")
    return redirect(url_for("dashboard.dashboard"))


@groups_bp.route("/threads/<int:thread_id>/delete", methods=["POST"])
@login_required
def delete_thread(thread_id):
    thread = GameThread.query.get_or_404(thread_id)
    group_id = thread.group_id
    member = Group.query.get_or_404(group_id).get_member(current_user.id)

    # Permission: group owner/admin OR the reporter of this thread
    is_admin = member and member.role in ("owner", "admin")
    is_reporter = False
    if thread.group_trigger and thread.group_trigger.game_event and \
            thread.group_trigger.game_event.incident_report:
        is_reporter = (thread.group_trigger.game_event.incident_report.reporter_user_id
                       == current_user.id)
    if not is_admin and not is_reporter:
        abort(403)

    thread.status = "deleted"
    db.session.commit()
    flash("Thread deleted.", "info")
    return redirect(url_for("groups.show", group_id=group_id))


@groups_bp.route("/<int:group_id>/threads/delete-batch", methods=["POST"])
@login_required
def delete_threads_batch(group_id):
    group = Group.query.get_or_404(group_id)
    member = group.get_member(current_user.id)
    if not member or member.role not in ("owner", "admin"):
        abort(403)
    thread_ids = request.form.getlist("thread_ids", type=int)
    if thread_ids:
        GameThread.query.filter(
            GameThread.id.in_(thread_ids),
            GameThread.group_id == group_id,
        ).update({"status": "deleted"}, synchronize_session=False)
        db.session.commit()
        flash(f"{len(thread_ids)} thread(s) deleted.", "info")
    return redirect(url_for("groups.show", group_id=group_id))
