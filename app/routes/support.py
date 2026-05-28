import threading

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user

from app.models import db, SupportTicket

support_bp = Blueprint("support", __name__)

CATEGORIES = [
    ("bug",     "Bug / Something Broken"),
    ("account", "Account Issue"),
    ("feature", "Feature Request"),
    ("billing", "Billing"),
    ("other",   "Other"),
]


@support_bp.route("/")
@login_required
def index():
    tickets = (
        SupportTicket.query
        .filter_by(user_id=current_user.id)
        .order_by(SupportTicket.created_at.desc())
        .all()
    )
    return render_template("support/index.html", tickets=tickets)


@support_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        subject     = request.form.get("subject", "").strip()
        category    = request.form.get("category", "other").strip()
        description = request.form.get("description", "").strip()

        errors = []
        if not subject:
            errors.append("Subject is required.")
        elif len(subject) > 200:
            errors.append("Subject must be under 200 characters.")
        if not description:
            errors.append("Description is required.")
        elif len(description) < 20:
            errors.append("Please describe the issue in at least 20 characters.")
        if category not in [c[0] for c in CATEGORIES]:
            category = "other"

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("support/new.html", categories=CATEGORIES)

        ticket = SupportTicket(
            user_id=current_user.id,
            subject=subject,
            category=category,
            description=description,
        )
        db.session.add(ticket)
        db.session.commit()

        # Fire emails in background — never block the redirect
        _app = current_app._get_current_object()
        _tid = ticket.id

        def _notify(app, ticket_id):
            with app.app_context():
                try:
                    t = db.session.get(SupportTicket, ticket_id)
                    if not t:
                        return
                    from app.services.email_service import (
                        send_ticket_received_user,
                        send_ticket_received_admin,
                    )
                    send_ticket_received_user(t)
                    db.session.commit()   # commit the magic link token
                    send_ticket_received_admin(t)
                    db.session.commit()
                except Exception as e:
                    app.logger.error(f"Support email error: {e}")

        threading.Thread(target=_notify, args=(_app, _tid), daemon=True).start()

        flash(f"Report submitted — reference {ticket.uid}", "success")
        return redirect(url_for("support.detail", uid=ticket.uid))

    return render_template("support/new.html", categories=CATEGORIES)


@support_bp.route("/<uid>")
@login_required
def detail(uid):
    ticket = SupportTicket.query.filter_by(uid=uid).first_or_404()
    if ticket.user_id != current_user.id:
        abort(403)
    return render_template("support/detail.html", ticket=ticket)
