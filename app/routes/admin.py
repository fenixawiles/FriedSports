"""
Admin blueprint — Sports Analytics Lab + privileged management.

All routes require User.role == "admin" via @admin_required.
URL prefix: /admin
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from app.utils import admin_required
from app.models import db, Team, User, UserFavoriteTeam, GroupMember, AdminAuditLog, SupportTicket
from app.analytics.models import (
    LabLeague, LabSeason, LabGame, LabPlayer,
    TeamGameStats, PlayerGameStats, DerivedGameMetrics, MetricDefinition,
)
from app.analytics.metric_engine import compute_derived_for_game
from app.analytics.rebound_lab import run_rebound_leverage_query

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


# ── Rebound Leverage Lab ──────────────────────────────────────────────────────

@admin_bp.route("/lab/rebound", methods=["GET", "POST"])
@login_required
@admin_required
def lab_rebound():
    leagues = LabLeague.query.order_by(LabLeague.abbreviation).all()
    seasons = LabSeason.query.order_by(LabSeason.year.desc()).all()
    results = None
    params = {}

    if request.method == "POST":
        league_id = request.form.get("league_id", type=int)
        season_id = request.form.get("season_id", type=int) or None
        threshold = request.form.get("fg_pct_threshold", 0.02, type=float)
        bin_size = request.form.get("bin_size", 5, type=int)
        playoffs_only = bool(request.form.get("playoffs_only"))

        params = {
            "league_id": league_id,
            "season_id": season_id,
            "threshold": threshold,
            "bin_size": bin_size,
            "playoffs_only": playoffs_only,
        }

        if not league_id:
            flash("Select a league.", "error")
        else:
            try:
                results = run_rebound_leverage_query(
                    league_id=league_id,
                    season_id=season_id,
                    fg_pct_parity_threshold=threshold,
                    bin_size=bin_size,
                    playoffs_only=playoffs_only,
                )
            except Exception as e:
                flash(f"Query error: {e}", "error")

    return render_template(
        "admin/lab/rebound.html",
        leagues=leagues,
        seasons=seasons,
        results=results,
        params=params,
    )


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
    page = request.args.get("page", 1, type=int)
    query = User.query.order_by(User.created_at.desc())
    if search:
        query = query.filter(
            db.or_(
                User.display_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
            )
        )
    users = query.paginate(page=page, per_page=50, error_out=False)
    return render_template("admin/users/list.html", users=users, search=search)


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


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def users_delete(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.id == _current_user_id():
        flash("You cannot delete your own account from here.", "error")
        return redirect(url_for("admin.users_detail", user_id=user_id))
    display_name = user.display_name
    _audit("delete_user", user, f"Deleted account: {user.email}")
    db.session.delete(user)
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
