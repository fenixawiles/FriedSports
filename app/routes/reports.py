from flask import Blueprint, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.models import db, IncidentReport, GroupMember, GameEvent, GameThreadMessage

reports_bp = Blueprint("reports", __name__)


def _get_report_and_thread(report_id):
    """Return (report, thread) or abort 404."""
    report = IncidentReport.query.get_or_404(report_id)
    # GameEvent → IncidentReport is defined on GameEvent; query via GameEvent
    event = GameEvent.query.filter_by(incident_report_id=report_id).first()
    if not event:
        abort(404)
    trigger = event.group_triggers.first()
    if not trigger:
        abort(404)
    thread = trigger.threads.first()
    if not thread:
        abort(404)
    return report, thread


def _require_admin(report):
    member = GroupMember.query.filter_by(
        group_id=report.group_id, user_id=current_user.id
    ).first()
    if not member or member.role not in ("owner", "admin"):
        abort(403)
    return member


@reports_bp.route("/<int:report_id>/confirm", methods=["POST"])
@login_required
def confirm(report_id):
    report, thread = _get_report_and_thread(report_id)
    _require_admin(report)
    if report.status not in ("active",):
        flash("Report cannot be confirmed in its current state.", "error")
        return redirect(url_for("threads.show", thread_id=thread.id))
    report.status = "confirmed"
    db.session.commit()
    flash("Report confirmed.", "success")
    return redirect(url_for("threads.show", thread_id=thread.id))


@reports_bp.route("/<int:report_id>/dismiss", methods=["POST"])
@login_required
def dismiss(report_id):
    from app.services.scoring import apply_dismiss_penalty
    report, thread = _get_report_and_thread(report_id)
    _require_admin(report)
    if report.status == "dismissed":
        flash("Already dismissed.", "info")
        return redirect(url_for("threads.show", thread_id=thread.id))
    report.status = "dismissed"
    apply_dismiss_penalty(report.group_id, report.reporter_user_id)
    db.session.commit()
    flash("Report dismissed. Reporter penalized.", "info")
    return redirect(url_for("threads.show", thread_id=thread.id))


@reports_bp.route("/<int:report_id>/redeem", methods=["POST"])
@login_required
def redeem(report_id):
    from app.services.scoring import apply_redemption_win
    from app.services.trash_templates import pick_template

    report, thread = _get_report_and_thread(report_id)

    member = GroupMember.query.filter_by(
        group_id=report.group_id, user_id=current_user.id
    ).first()
    is_target = current_user.id == report.target_user_id
    is_admin = member and member.role in ("owner", "admin")

    if not is_target and not is_admin:
        abort(403)

    if report.status == "redeemed":
        flash("Already redeemed.", "info")
        return redirect(url_for("threads.show", thread_id=thread.id))

    report.status = "redeemed"

    redemption_body = pick_template(
        "REDEMPTION_WIN",
        user=report.target_user.display_name,
        team=report.target_team.name,
        context="",
    )
    msg = GameThreadMessage(
        thread_id=thread.id,
        user_id=None,
        message_type="system",
        body=redemption_body,
    )
    db.session.add(msg)

    apply_redemption_win(thread)
    db.session.commit()
    flash("Redemption logged. The attackers have been notified.", "success")
    return redirect(url_for("threads.show", thread_id=thread.id))
