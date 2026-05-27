from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app.models import db, GameThread, GameThreadMessage, Group, GroupMember
from app.services.scoring import apply_thread_points

threads_bp = Blueprint("threads", __name__)


@threads_bp.route("/<int:thread_id>")
@login_required
def show(thread_id):
    thread = (
        GameThread.query
        .options(
            joinedload(GameThread.target_user),
            joinedload(GameThread.target_team),
        )
        .get_or_404(thread_id)
    )
    group = Group.query.get(thread.group_id)
    if not group.is_member(current_user.id) and group.privacy != "public_readonly":
        abort(403)

    # Eager-load authors and reactions in one query — eliminates N+1
    messages = (
        GameThreadMessage.query
        .filter_by(thread_id=thread_id, is_deleted=False)
        .options(
            joinedload(GameThreadMessage.author),
            joinedload(GameThreadMessage.reactions),
        )
        .order_by(GameThreadMessage.created_at)
        .all()
    )

    last_id = messages[-1].id if messages else 0

    member = GroupMember.query.filter_by(
        group_id=thread.group_id, user_id=current_user.id
    ).first()

    return render_template(
        "threads/show.html",
        thread=thread,
        group=group,
        messages=messages,
        last_id=last_id,
        member=member,
    )


@threads_bp.route("/<int:thread_id>/messages", methods=["POST"])
@login_required
def post_message(thread_id):
    thread = GameThread.query.get_or_404(thread_id)
    group = Group.query.get(thread.group_id)
    if not group.is_member(current_user.id):
        abort(403)
    if thread.status != "active":
        flash("This thread is closed.", "error")
        return redirect(url_for("threads.show", thread_id=thread_id))

    body = request.form.get("body", "").strip()
    if not body:
        flash("Message cannot be empty.", "error")
        return redirect(url_for("threads.show", thread_id=thread_id))
    if len(body) > 1000:
        flash("Message too long (max 1000 chars).", "error")
        return redirect(url_for("threads.show", thread_id=thread_id))

    msg = GameThreadMessage(
        thread_id=thread_id,
        user_id=current_user.id,
        message_type="user",
        body=body,
    )
    db.session.add(msg)
    db.session.flush()

    apply_thread_points(thread, msg)
    db.session.commit()

    return redirect(url_for("threads.show", thread_id=thread_id))
