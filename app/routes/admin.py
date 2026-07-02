"""
Admin blueprint — Sports Analytics Lab + privileged management.

All routes require User.role == "admin" via @admin_required.
URL prefix: /admin
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from app.utils import admin_required
from app.models import (db, Team, User, UserFavoriteTeam, GroupMember, AdminAuditLog,
                        SupportTicket, Group, IncidentReport, GameEvent, GroupTrigger,
                        GameThread, GameThreadMessage, MessageReaction, MessageReport,
                        Receipt, DeviceToken, LoginToken, Notification, FriendRequest)
from app.analytics.models import (
    LabLeague, LabSeason, LabGame, LabPlayer,
    TeamGameStats, PlayerGameStats, DerivedGameMetrics, MetricDefinition,
)
from app.analytics.metric_engine import compute_derived_for_game

admin_bp = Blueprint("admin", __name__)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    game_count = LabGame.query.count()
    # Count games with derived metrics
    derived_count = (
        db.session.query(LabGame.id)
        .join(DerivedGameMetrics, DerivedGameMetrics.game_id == LabGame.id)
        .distinct()
        .count()
    )
    recent_games = (
        LabGame.query
        .order_by(LabGame.created_at.desc())
        .limit(8)
        .all()
    )
    leagues = LabLeague.query.order_by(LabLeague.abbreviation).all()
    player_count = LabPlayer.query.count()

    return render_template(
        "admin/dashboard.html",
        game_count=game_count,
        derived_count=derived_count,
        player_count=player_count,
        recent_games=recent_games,
        leagues=leagues,
    )


# ── Games ─────────────────────────────────────────────────────────────────────

@admin_bp.route("/games")
@login_required
@admin_required
def games_list():
    league_id = request.args.get("league_id", type=int)
    season_id = request.args.get("season_id", type=int)
    page = request.args.get("page", 1, type=int)

    query = LabGame.query.order_by(LabGame.date.desc())
    if league_id:
        query = query.filter_by(league_id=league_id)
    if season_id:
        query = query.filter_by(season_id=season_id)

    games = query.paginate(page=page, per_page=25, error_out=False)
    leagues = LabLeague.query.order_by(LabLeague.abbreviation).all()
    seasons = LabSeason.query.order_by(LabSeason.year.desc()).all()

    return render_template(
        "admin/games/list.html",
        games=games,
        leagues=leagues,
        seasons=seasons,
        selected_league=league_id,
        selected_season=season_id,
    )


@admin_bp.route("/games/new", methods=["GET", "POST"])
@login_required
@admin_required
def games_new():
    leagues = LabLeague.query.order_by(LabLeague.abbreviation).all()
    seasons = LabSeason.query.order_by(LabSeason.year.desc()).all()

    if request.method == "POST":
        try:
            game = _create_game_from_form(request.form)
            db.session.add(game)
            db.session.flush()

            home_stats = _build_team_stats(request.form, game.id, game.home_team_id,
                                           game.away_team_id, is_home=True)
            away_stats = _build_team_stats(request.form, game.id, game.away_team_id,
                                           game.home_team_id, is_home=False)
            db.session.add(home_stats)
            db.session.add(away_stats)
            db.session.commit()
            flash(f"Game added (id={game.id}).", "success")
            return redirect(url_for("admin.games_detail", game_id=game.id))
        except Exception as e:
            db.session.rollback()
            flash(f"Error saving game: {e}", "error")

    # Build team lists per league for JS filtering
    all_teams = Team.query.order_by(Team.city).all()
    teams_by_league = {}
    for t in all_teams:
        teams_by_league.setdefault(t.league, []).append({"id": t.id, "name": f"{t.city} {t.name}", "abbr": t.abbreviation})

    return render_template(
        "admin/games/form.html",
        leagues=leagues,
        seasons=seasons,
        all_teams=all_teams,
        teams_by_league=teams_by_league,
        game=None,
        home_stats=None,
        away_stats=None,
    )


@admin_bp.route("/games/<int:game_id>")
@login_required
@admin_required
def games_detail(game_id):
    game = db.session.get(LabGame, game_id) or abort(404)
    stats = {s.team_id: s for s in game.team_stats.all()}
    home_stats = stats.get(game.home_team_id)
    away_stats = stats.get(game.away_team_id)
    derived = {d.team_id: d for d in game.derived_metrics.all()}

    return render_template(
        "admin/games/detail.html",
        game=game,
        home_stats=home_stats,
        away_stats=away_stats,
        derived=derived,
    )


@admin_bp.route("/games/<int:game_id>/stats", methods=["POST"])
@login_required
@admin_required
def games_update_stats(game_id):
    game = db.session.get(LabGame, game_id) or abort(404)

    # Update home stats
    home_stats = TeamGameStats.query.filter_by(game_id=game_id, team_id=game.home_team_id).first()
    if home_stats:
        _apply_stats_from_form(request.form, home_stats, prefix="home_")
    # Update away stats
    away_stats = TeamGameStats.query.filter_by(game_id=game_id, team_id=game.away_team_id).first()
    if away_stats:
        _apply_stats_from_form(request.form, away_stats, prefix="away_")

    db.session.commit()
    flash("Stats updated.", "success")
    return redirect(url_for("admin.games_detail", game_id=game_id))


@admin_bp.route("/games/<int:game_id>/derive", methods=["POST"])
@login_required
@admin_required
def games_derive(game_id):
    game = db.session.get(LabGame, game_id) or abort(404)
    try:
        compute_derived_for_game(game_id)
        db.session.commit()
        flash("Derived metrics computed.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.games_detail", game_id=game_id))


# ── Players ───────────────────────────────────────────────────────────────────

@admin_bp.route("/players")
@login_required
@admin_required
def players_list():
    team_id = request.args.get("team_id", type=int)
    query = LabPlayer.query.order_by(LabPlayer.name)
    if team_id:
        query = query.filter_by(team_id=team_id)
    players = query.all()
    teams = Team.query.order_by(Team.city).all()
    return render_template("admin/players/list.html", players=players, teams=teams, selected_team=team_id)


@admin_bp.route("/players/new", methods=["GET", "POST"])
@login_required
@admin_required
def players_new():
    teams = Team.query.order_by(Team.city).all()
    if request.method == "POST":
        team_id = request.form.get("team_id", type=int)
        name = request.form.get("name", "").strip()
        position = request.form.get("position", "").strip()
        if not team_id or not name:
            flash("Team and name are required.", "error")
        else:
            player = LabPlayer(team_id=team_id, name=name, position=position or None)
            db.session.add(player)
            db.session.commit()
            flash(f"Player {name} added.", "success")
            return redirect(url_for("admin.players_list"))
    return render_template("admin/players/form.html", teams=teams)


# ── Metrics ───────────────────────────────────────────────────────────────────

@admin_bp.route("/metrics")
@login_required
@admin_required
def metrics_list():
    metrics = MetricDefinition.query.order_by(MetricDefinition.name).all()
    return render_template("admin/metrics/list.html", metrics=metrics)


@admin_bp.route("/metrics/new", methods=["POST"])
@login_required
@admin_required
def metrics_new():
    name = request.form.get("name", "").strip()
    slug = request.form.get("slug", "").strip().lower().replace(" ", "_")
    description = request.form.get("description", "").strip()
    formula_type = request.form.get("formula_type", "python")
    parameters = request.form.get("parameters", "{}").strip()
    output_entity = request.form.get("output_entity", "game_team")

    if not name or not slug:
        flash("Name and slug are required.", "error")
        return redirect(url_for("admin.metrics_list"))

    existing = MetricDefinition.query.filter_by(slug=slug).first()
    if existing:
        flash(f"Slug '{slug}' already exists.", "error")
        return redirect(url_for("admin.metrics_list"))

    m = MetricDefinition(
        name=name, slug=slug, description=description,
        formula_type=formula_type, parameters=parameters,
        output_entity=output_entity,
    )
    db.session.add(m)
    db.session.commit()
    flash(f"Metric '{name}' created.", "success")
    return redirect(url_for("admin.metrics_list"))


# ── Seasons (quick create) ────────────────────────────────────────────────────

@admin_bp.route("/seasons/new", methods=["POST"])
@login_required
@admin_required
def seasons_new():
    league_id = request.form.get("league_id", type=int)
    year = request.form.get("year", type=int)
    season_type = request.form.get("season_type", "regular")
    next_url = request.form.get("next", url_for("admin.dashboard"))

    if not league_id or not year:
        flash("League and year required.", "error")
        return redirect(next_url)

    existing = LabSeason.query.filter_by(
        league_id=league_id, year=year, season_type=season_type
    ).first()
    if existing:
        flash("Season already exists.", "info")
        return redirect(next_url)

    s = LabSeason(league_id=league_id, year=year, season_type=season_type)
    db.session.add(s)
    db.session.commit()
    flash(f"{year} {season_type.title()} season created.", "success")
    return redirect(next_url)


# ── User Management ──────────────────────────────────────────────────────────

@admin_bp.route("/users")
@login_required
@admin_required
def users_list():
    search = request.args.get("q", "").strip()
    pending = request.args.get("pending") in ("1", "true", "yes")
    page = request.args.get("page", 1, type=int)
    query = User.query.order_by(User.created_at.desc())
    if search:
        query = query.filter(
            db.or_(
                User.display_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.uid.ilike(f"%{search}%"),
            )
        )
    if pending:
        query = query.filter_by(email_verified=False)
    users = query.paginate(page=page, per_page=50, error_out=False)
    pending_total = User.query.filter_by(email_verified=False).count()
    return render_template("admin/users/list.html", users=users, search=search,
                           pending=pending, pending_total=pending_total)


@admin_bp.route("/users/<int:user_id>")
@login_required
@admin_required
def users_detail(user_id):
    user = db.session.get(User, user_id) or abort(404)
    memberships = GroupMember.query.filter_by(user_id=user_id).all()
    from app.models import Group
    groups = [
        {"member": m, "group": Group.query.get(m.group_id)}
        for m in memberships
    ]
    fav_teams = UserFavoriteTeam.query.filter_by(user_id=user_id).all()
    return render_template(
        "admin/users/detail.html",
        user=user,
        groups=groups,
        fav_teams=fav_teams,
    )


@admin_bp.route("/users/<int:user_id>/change-email", methods=["POST"])
@login_required
@admin_required
def users_change_email(user_id):
    user = db.session.get(User, user_id) or abort(404)
    new_email = request.form.get("email", "").strip().lower()
    if not new_email:
        flash("Email cannot be empty.", "error")
    elif User.query.filter(User.email == new_email, User.id != user_id).first():
        flash("Email already in use.", "error")
    else:
        old_email = user.email
        user.email = new_email
        _audit("change_email", user, f"{old_email} → {new_email}")
        db.session.commit()
        flash(f"Email updated to {new_email}.", "success")
    return redirect(url_for("admin.users_detail", user_id=user_id))


@admin_bp.route("/users/<int:user_id>/change-password", methods=["POST"])
@login_required
@admin_required
def users_change_password(user_id):
    user = db.session.get(User, user_id) or abort(404)
    new_pw = request.form.get("password", "")
    if len(new_pw) < 6:
        flash("Password must be at least 6 characters.", "error")
    else:
        user.set_password(new_pw)
        _audit("change_password", user, "Admin reset password")
        db.session.commit()
        flash("Password updated.", "success")
    return redirect(url_for("admin.users_detail", user_id=user_id))


@admin_bp.route("/users/<int:user_id>/change-role", methods=["POST"])
@login_required
@admin_required
def users_change_role(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.id == _current_user_id():
        flash("You cannot change your own role.", "error")
        return redirect(url_for("admin.users_detail", user_id=user_id))
    new_role = request.form.get("role", "user")
    if new_role not in ("user", "admin"):
        flash("Invalid role.", "error")
    else:
        old_role = user.role
        user.role = new_role
        _audit("change_role", user, f"{old_role} → {new_role}")
        db.session.commit()
        flash(f"Role updated to '{new_role}'.", "success")
    return redirect(url_for("admin.users_detail", user_id=user_id))


@admin_bp.route("/users/<int:user_id>/approve", methods=["POST"])
@login_required
@admin_required
def users_approve(user_id):
    """Manually approve a pending account (email verification codes are off)."""
    user = db.session.get(User, user_id) or abort(404)
    if not user.email_verified:
        user.email_verified = True
        _audit("approve_user", user, "Manually approved (verification bypassed)")
        db.session.commit()
        flash(f"{user.display_name} approved.", "success")
    else:
        flash("That user is already approved.", "info")
    return redirect(url_for("admin.users_detail", user_id=user_id))


def _cascade_delete_group_admin(group_id):
    """Delete a group and all its data — used by user deletion and admin group cleanup."""
    from app.routes.groups import _cascade_delete_group
    _cascade_delete_group(group_id)


def _delete_threads_and_children(thread_ids):
    """Hard-delete threads and every row that references them, in FK order.
    Children of game_threads.id: messages (+ their reactions/reports), receipts,
    thread_reads, thread_votes, thread_user_states (verified via information_schema)."""
    if not thread_ids:
        return
    from app.models import ThreadRead, ThreadVote, ThreadUserState
    msg_subq = (
        db.session.query(GameThreadMessage.id)
        .filter(GameThreadMessage.thread_id.in_(thread_ids))
    )
    MessageReaction.query.filter(MessageReaction.message_id.in_(msg_subq)).delete(synchronize_session=False)
    MessageReport.query.filter(MessageReport.message_id.in_(msg_subq)).delete(synchronize_session=False)
    GameThreadMessage.query.filter(GameThreadMessage.thread_id.in_(thread_ids)).delete(synchronize_session=False)
    Receipt.query.filter(Receipt.thread_id.in_(thread_ids)).delete(synchronize_session=False)
    ThreadRead.query.filter(ThreadRead.thread_id.in_(thread_ids)).delete(synchronize_session=False)
    ThreadVote.query.filter(ThreadVote.thread_id.in_(thread_ids)).delete(synchronize_session=False)
    ThreadUserState.query.filter(ThreadUserState.thread_id.in_(thread_ids)).delete(synchronize_session=False)
    GameThread.query.filter(GameThread.id.in_(thread_ids)).delete(synchronize_session=False)


def _cascade_delete_user(user_id):
    """Delete a user and EVERY record referencing them, in FK-safe order.

    Each users.id FK is ON DELETE NO ACTION, so every child reference must be
    deleted (or nulled where the column is nullable) before the user row can be
    removed — otherwise the final delete raises an IntegrityError and the account
    silently survives. The full set of referencing tables was verified against
    information_schema; if you add a new table with a users.id FK, add it here.
    """
    from app.models import (BlockedUser, ThreadRead, ThreadVote,
                            ThreadUserState, ActivityEvent)

    # Groups owned by the user — full group cascade (their threads + members).
    for g in Group.query.filter_by(owner_id=user_id).all():
        from app.routes.groups import _cascade_delete_group
        _cascade_delete_group(g.id)

    # Incident/direct threads involving this user must be removed with their
    # children. Group chats they created can survive with created_by nulled.
    target_thread_ids = [
        t.id for t in GameThread.query.filter_by(target_user_id=user_id).all()
    ]
    direct_created_thread_ids = [
        t.id for t in GameThread.query.filter_by(
            thread_type="direct_chat",
            created_by_user_id=user_id,
        ).all()
    ]
    target_thread_ids = list(set(target_thread_ids + direct_created_thread_ids))
    _delete_threads_and_children(target_thread_ids)
    GameThread.query.filter_by(created_by_user_id=user_id).update(
        {"created_by_user_id": None}, synchronize_session=False
    )

    # Reactions/reports by this user; anonymise the user's own messages so the
    # rest of each surviving thread's history stays intact.
    MessageReaction.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    MessageReport.query.filter_by(reporter_user_id=user_id).delete(synchronize_session=False)
    MessageReport.query.filter_by(reviewed_by_id=user_id).update(
        {"reviewed_by_id": None}, synchronize_session=False
    )
    GameThreadMessage.query.filter_by(user_id=user_id).update(
        {"user_id": None, "is_deleted": True}, synchronize_session=False
    )

    # Group memberships (owned groups already deleted above).
    GroupMember.query.filter_by(user_id=user_id).delete(synchronize_session=False)

    # Incident reports (reporter or target) + their events/triggers.
    ir_ids = [r.id for r in IncidentReport.query.filter(
        db.or_(
            IncidentReport.reporter_user_id == user_id,
            IncidentReport.target_user_id == user_id,
        )
    ).all()]
    if ir_ids:
        ge_ids = [e.id for e in GameEvent.query.filter(
            GameEvent.incident_report_id.in_(ir_ids)
        ).all()]
        if ge_ids:
            GroupTrigger.query.filter(GroupTrigger.game_event_id.in_(ge_ids)).delete(
                synchronize_session=False
            )
            GameEvent.query.filter(GameEvent.id.in_(ge_ids)).delete(synchronize_session=False)
        IncidentReport.query.filter(IncidentReport.id.in_(ir_ids)).delete(
            synchronize_session=False
        )

    # Group triggers that target this user directly (separate FK from the event
    # path handled above).
    GroupTrigger.query.filter_by(target_user_id=user_id).delete(synchronize_session=False)

    # Receipts referencing this user.
    Receipt.query.filter(
        db.or_(Receipt.target_user_id == user_id, Receipt.top_hater_user_id == user_id)
    ).delete(synchronize_session=False)

    # Audit log — preserve history, drop the FK reference.
    AdminAuditLog.query.filter_by(target_user_id=user_id).update(
        {"target_user_id": None}, synchronize_session=False
    )
    AdminAuditLog.query.filter_by(admin_id=user_id).update(
        {"admin_id": None}, synchronize_session=False
    )

    # Blocks, thread-scoped state, and activity authored by the user.
    BlockedUser.query.filter(
        db.or_(BlockedUser.blocker_id == user_id, BlockedUser.blocked_id == user_id)
    ).delete(synchronize_session=False)
    ThreadRead.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    ThreadVote.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    ThreadUserState.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    ActivityEvent.query.filter_by(actor_id=user_id).update(
        {"actor_id": None}, synchronize_session=False
    )

    # Tokens, devices, tickets, favourites, notifications, friend requests.
    LoginToken.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    DeviceToken.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    SupportTicket.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    UserFavoriteTeam.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    Notification.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    FriendRequest.query.filter(
        db.or_(
            FriendRequest.from_user_id == user_id,
            FriendRequest.to_user_id   == user_id,
        )
    ).delete(synchronize_session=False)
    db.session.flush()


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def users_delete(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.id == _current_user_id():
        flash("You cannot delete your own account from here.", "error")
        return redirect(url_for("admin.users_detail", user_id=user_id))
    display_name = user.display_name
    email = user.email
    _audit("delete_user", user, f"Deleted account: {email}")
    db.session.flush()  # persist audit log before cascade
    _cascade_delete_user(user_id)
    user_obj = db.session.get(User, user_id)
    if user_obj:
        db.session.delete(user_obj)
    db.session.commit()
    flash(f"User '{display_name}' deleted.", "success")
    return redirect(url_for("admin.users_list"))


@admin_bp.route("/users/<int:user_id>/send-email", methods=["POST"])
@login_required
@admin_required
def users_send_email(user_id):
    user = db.session.get(User, user_id) or abort(404)
    subject = request.form.get("subject", "").strip()
    body = request.form.get("body", "").strip()
    if not subject or not body:
        flash("Subject and body are required.", "error")
        return redirect(url_for("admin.users_detail", user_id=user_id))
    from app.services.email_service import _send, _wrap
    ok = _send(user.email, subject, _wrap(f"<p>{body}</p>"), body)
    if ok:
        flash(f"Email sent to {user.email}.", "success")
    else:
        flash("Email failed — check RESEND_API_KEY in Railway.", "warning")
    return redirect(url_for("admin.users_detail", user_id=user_id))


@admin_bp.route("/users/invite", methods=["POST"])
@login_required
@admin_required
def users_invite():
    email = request.form.get("email", "").strip().lower()
    if not email:
        flash("Email is required.", "error")
        return redirect(url_for("admin.users_list"))
    if User.query.filter_by(email=email).first():
        flash("A user with that email already exists.", "info")
        return redirect(url_for("admin.users_list"))
    from app.services.email_service import _send, _wrap
    invite_url = url_for("auth.signup", _external=True)
    text = f"You've been invited to FriedSports. Sign up here: {invite_url}"
    html = _wrap(f"<p>You've been invited to FriedSports.</p>"
                 f'<a href="{invite_url}" class="btn">Sign Up →</a>')
    ok = _send(email, "You're invited to FriedSports", html, text)
    if ok:
        flash(f"Invite sent to {email}.", "success")
    else:
        flash(f"Email failed — share this link manually: {invite_url}", "info")
    return redirect(url_for("admin.users_list"))


# ── Admin Tools dashboard (separate from Lab) ─────────────────────────────────

@admin_bp.route("/tools")
@login_required
@admin_required
def tools_dashboard():
    user_count = User.query.count()
    open_tickets = SupportTicket.query.filter(
        SupportTicket.status.in_(["received", "in_progress"])
    ).count()
    recent_logs = (
        AdminAuditLog.query
        .order_by(AdminAuditLog.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template(
        "admin/tools_overview.html",
        user_count=user_count,
        open_tickets=open_tickets,
        recent_logs=recent_logs,
    )


# ── Admin email action routes ─────────────────────────────────────────────────

@admin_bp.route("/users/<int:user_id>/send-password-reset", methods=["POST"])
@login_required
@admin_required
def send_password_reset(user_id):
    import secrets as _sec
    from datetime import timedelta
    user = db.session.get(User, user_id) or abort(404)
    tok = LoginToken(
        user_id=user.id,
        token=_sec.token_urlsafe(32),
        purpose="password_reset",
        expires_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ) + timedelta(hours=1),
    )
    db.session.add(tok)
    db.session.commit()
    reset_url = url_for("auth.reset_password", token=tok.token, _external=True)
    from app.services.email_service import send_admin_password_reset
    send_admin_password_reset(user, reset_url)
    _audit("send_password_reset", user, "Admin sent password reset email")
    db.session.commit()
    flash(f"Password reset email sent to {user.email}.", "success")
    return redirect(url_for("admin.users_detail", user_id=user_id))


@admin_bp.route("/users/<int:user_id>/send-username-change", methods=["POST"])
@login_required
@admin_required
def send_username_change(user_id):
    import secrets as _sec
    from datetime import timedelta
    user = db.session.get(User, user_id) or abort(404)
    tok = LoginToken(
        user_id=user.id,
        token=_sec.token_urlsafe(32),
        purpose="magic_link",
        next_url="/dashboard/settings",
        expires_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ) + timedelta(hours=24),
    )
    db.session.add(tok)
    db.session.commit()
    settings_url = url_for("auth.magic_link", token=tok.token, _external=True)
    from app.services.email_service import send_username_change_prompt
    send_username_change_prompt(user, settings_url)
    _audit("send_username_change", user, "Admin sent username change prompt")
    db.session.commit()
    flash(f"Username change email sent to {user.email}.", "success")
    return redirect(url_for("admin.users_detail", user_id=user_id))


@admin_bp.route("/users/<int:user_id>/send-email-change", methods=["POST"])
@login_required
@admin_required
def send_email_change(user_id):
    import secrets as _sec
    from datetime import timedelta
    user = db.session.get(User, user_id) or abort(404)
    tok = LoginToken(
        user_id=user.id,
        token=_sec.token_urlsafe(32),
        purpose="magic_link",
        next_url="/dashboard/settings",
        expires_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ) + timedelta(hours=24),
    )
    db.session.add(tok)
    db.session.commit()
    settings_url = url_for("auth.magic_link", token=tok.token, _external=True)
    from app.services.email_service import send_email_change_prompt
    send_email_change_prompt(user, settings_url)
    _audit("send_email_change", user, "Admin sent email change prompt")
    db.session.commit()
    flash(f"Email change prompt sent to {user.email}.", "success")
    return redirect(url_for("admin.users_detail", user_id=user_id))


@admin_bp.route("/audit-log")
@login_required
@admin_required
def audit_log():
    page = request.args.get("page", 1, type=int)
    logs = (
        AdminAuditLog.query
        .order_by(AdminAuditLog.created_at.desc())
        .paginate(page=page, per_page=50, error_out=False)
    )
    return render_template("admin/audit_log.html", logs=logs)


def _current_user_id():
    return current_user.id


def _audit(action, target_user=None, details=None):
    """Write an admin audit log entry."""
    log = AdminAuditLog(
        admin_id=current_user.id,
        target_user_id=target_user.id if target_user else None,
        action=action,
        details=details,
        ip_address=request.remote_addr,
    )
    db.session.add(log)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create_game_from_form(form) -> LabGame:
    from datetime import date as _date
    date_str = form.get("date", "")
    game_date = _date.fromisoformat(date_str) if date_str else _date.today()

    return LabGame(
        league_id=int(form["league_id"]),
        season_id=form.get("season_id", type=int) or None,
        date=game_date,
        home_team_id=int(form["home_team_id"]),
        away_team_id=int(form["away_team_id"]),
        home_score=int(form.get("home_score", 0) or 0),
        away_score=int(form.get("away_score", 0) or 0),
        status=form.get("status", "final"),
        attendance=form.get("attendance", type=int) or None,
        venue=form.get("venue", "").strip() or None,
        notes=form.get("notes", "").strip() or None,
    )


def _build_team_stats(form, game_id: int, team_id: int, opponent_id: int, is_home: bool) -> TeamGameStats:
    prefix = "home_" if is_home else "away_"
    s = TeamGameStats(
        game_id=game_id,
        team_id=team_id,
        opponent_id=opponent_id,
        is_home=is_home,
    )
    _apply_stats_from_form(form, s, prefix=prefix)
    return s


def _apply_stats_from_form(form, stats: TeamGameStats, prefix: str = ""):
    def fi(key, default=0):
        return int(form.get(f"{prefix}{key}") or default)

    def ff(key, default=0.0):
        return float(form.get(f"{prefix}{key}") or default)

    stats.points = fi("points")
    stats.fgm = fi("fgm")
    stats.fga = fi("fga")
    stats.three_pm = fi("three_pm")
    stats.three_pa = fi("three_pa")
    stats.ftm = fi("ftm")
    stats.fta = fi("fta")
    stats.off_rebounds = fi("off_rebounds")
    stats.def_rebounds = fi("def_rebounds")
    stats.assists = fi("assists")
    stats.steals = fi("steals")
    stats.blocks = fi("blocks")
    stats.turnovers = fi("turnovers")
    stats.fouls = fi("fouls")
    stats.compute_percentages()


# ── Broadcast email ───────────────────────────────────────────────────────────

@admin_bp.route("/broadcast", methods=["GET", "POST"])
@login_required
@admin_required
def broadcast():
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        body_html = request.form.get("body_html", "").strip()
        target = request.form.get("target", "all")
        target_email = request.form.get("target_email", "").strip().lower()

        if not subject or not body_html:
            flash("Subject and body are required.", "error")
            return render_template("admin/broadcast.html")

        from app.services.email_service import send_broadcast, _send

        if target == "single":
            if not target_email:
                flash("Enter a target email address.", "error")
                return render_template("admin/broadcast.html")
            from app.services.email_service import _wrap
            ok = _send(target_email, subject, _wrap(body_html))
            if ok:
                flash(f"Email sent to {target_email}.", "success")
            else:
                flash("Send failed — check RESEND_API_KEY.", "error")
        else:
            users = User.query.filter(User.email.isnot(None)).all()
            sent, failed = send_broadcast(users, subject, body_html)
            flash(f"Sent to {sent} users. {failed} failed.", "success" if failed == 0 else "warning")

        return redirect(url_for("admin.broadcast"))

    return render_template("admin/broadcast.html")


# ── Support ticket management ─────────────────────────────────────────────────

@admin_bp.route("/support")
@login_required
@admin_required
def support_list():
    status_filter = request.args.get("status", "all")
    q = SupportTicket.query.order_by(SupportTicket.created_at.desc())
    if status_filter != "all":
        q = q.filter_by(status=status_filter)
    tickets = q.all()
    counts = {
        "all":         SupportTicket.query.count(),
        "received":    SupportTicket.query.filter_by(status="received").count(),
        "in_progress": SupportTicket.query.filter_by(status="in_progress").count(),
        "resolved":    SupportTicket.query.filter_by(status="resolved").count(),
    }
    return render_template(
        "admin/support/list.html",
        tickets=tickets,
        status_filter=status_filter,
        counts=counts,
    )


@admin_bp.route("/support/<uid>", methods=["GET", "POST"])
@login_required
@admin_required
def support_detail(uid):
    import threading
    ticket = SupportTicket.query.filter_by(uid=uid).first_or_404()

    if request.method == "POST":
        if ticket.is_resolved:
            flash("This ticket is already resolved.", "info")
            return redirect(url_for("admin.support_detail", uid=uid))

        new_status = request.form.get("status", "").strip()
        admin_note = request.form.get("admin_note", "").strip() or None

        valid_next = ticket.NEXT_STATUSES.get(ticket.status, [])
        if new_status not in valid_next:
            flash("Invalid status transition.", "error")
            return redirect(url_for("admin.support_detail", uid=uid))

        old_status = ticket.status
        ticket.status = new_status
        ticket.admin_note = admin_note
        if new_status == "resolved":
            from datetime import datetime, timezone
            ticket.resolved_at = datetime.now(timezone.utc)
            # Never leave a resolved ticket without a response the user can see.
            if not ticket.admin_note:
                ticket.admin_note = (
                    "This ticket has been marked resolved. If your issue isn't fully "
                    "sorted, just open a new ticket and we'll take another look."
                )

        # In-app notification so the user knows their ticket moved.
        from app.models import Notification
        db.session.add(Notification(
            user_id=ticket.user_id,
            type="ticket_update",
            message=f"Your support ticket {ticket.uid} is now "
                    f"{SupportTicket.STATUS_LABELS.get(new_status, new_status)}.",
            link_url=f"/support/{ticket.uid}",
        ))

        log = AdminAuditLog(
            admin_id=current_user.id,
            target_user_id=ticket.user_id,
            action="ticket_status_update",
            details=f"{ticket.uid}: {old_status} → {new_status}",
            ip_address=request.remote_addr,
        )
        db.session.add(log)
        db.session.commit()

        _app = current_app._get_current_object()
        _tid = ticket.id

        def _notify(app, ticket_id):
            with app.app_context():
                try:
                    t = db.session.get(SupportTicket, ticket_id)
                    if t:
                        from app.services.email_service import send_ticket_status_update
                        send_ticket_status_update(t)
                        db.session.commit()
                except Exception as e:
                    app.logger.error(f"Ticket status email error: {e}")

        threading.Thread(target=_notify, args=(_app, _tid), daemon=True).start()

        flash(f"Ticket {uid} updated to {ticket.status_label}.", "success")
        return redirect(url_for("admin.support_detail", uid=uid))

    return render_template("admin/support/detail.html", ticket=ticket)


# ── Content moderation queue (UGC reports) ────────────────────────────────────

@admin_bp.route("/reports")
@login_required
@admin_required
def reports_list():
    """Queue of user-submitted content reports. Open reports first so they can
    be actioned within the 24h window Apple's UGC guideline expects."""
    from sqlalchemy.orm import joinedload
    status_filter = request.args.get("status", "open")
    q = (
        MessageReport.query
        .options(
            joinedload(MessageReport.reporter),
            joinedload(MessageReport.reviewed_by),
        )
        .order_by(MessageReport.created_at.desc())
    )
    if status_filter != "all":
        q = q.filter(MessageReport.status == status_filter)
    reports = q.all()

    # Hydrate each report with its message + thread + author (one pass).
    rows = []
    for r in reports:
        msg = db.session.get(GameThreadMessage, r.message_id)
        thread = db.session.get(GameThread, msg.thread_id) if msg else None
        author = db.session.get(User, msg.user_id) if (msg and msg.user_id) else None
        rows.append({"report": r, "message": msg, "thread": thread, "author": author})

    counts = {
        "open":      MessageReport.query.filter_by(status="open").count(),
        "resolved":  MessageReport.query.filter_by(status="resolved").count(),
        "dismissed": MessageReport.query.filter_by(status="dismissed").count(),
        "all":       MessageReport.query.count(),
    }
    return render_template(
        "admin/reports/list.html",
        rows=rows,
        status_filter=status_filter,
        counts=counts,
    )


@admin_bp.route("/reports/<int:report_id>/action", methods=["POST"])
@login_required
@admin_required
def report_action(report_id):
    """Action a content report: delete the offending message, or dismiss the
    report. Both close the report and write an audit-log entry."""
    from datetime import datetime, timezone
    report = MessageReport.query.get_or_404(report_id)
    action = request.form.get("action", "")
    msg = db.session.get(GameThreadMessage, report.message_id)

    if action == "delete_message":
        if msg and not msg.is_deleted:
            msg.is_deleted = True
        report.status = "resolved"
        report.resolution = "message_deleted"
        # Resolve any sibling reports on the same message.
        if msg:
            MessageReport.query.filter(
                MessageReport.message_id == msg.id,
                MessageReport.status == "open",
                MessageReport.id != report.id,
            ).update(
                {"status": "resolved", "resolution": "message_deleted",
                 "reviewed_by_id": current_user.id, "reviewed_at": datetime.now(timezone.utc)},
                synchronize_session=False,
            )
        detail = f"Deleted message #{report.message_id} (report #{report.id})"
        flash("Message removed and report resolved.", "success")
    elif action == "dismiss":
        report.status = "dismissed"
        report.resolution = "no_action"
        detail = f"Dismissed report #{report.id} (message #{report.message_id})"
        flash("Report dismissed.", "info")
    else:
        flash("Unknown action.", "error")
        return redirect(url_for("admin.reports_list"))

    report.reviewed_by_id = current_user.id
    report.reviewed_at = datetime.now(timezone.utc)

    db.session.add(AdminAuditLog(
        admin_id=current_user.id,
        target_user_id=(msg.user_id if msg else None),
        action="content_moderation",
        details=detail,
        ip_address=request.remote_addr,
    ))
    db.session.commit()
    return redirect(url_for("admin.reports_list", status=request.args.get("status", "open")))
