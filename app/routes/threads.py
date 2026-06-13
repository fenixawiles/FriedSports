from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
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
    hidden_ids = current_user.hidden_user_ids()
    msg_query = (
        GameThreadMessage.query
        .filter_by(thread_id=thread_id, is_deleted=False)
        .options(
            joinedload(GameThreadMessage.author),
            joinedload(GameThreadMessage.reactions),
        )
    )
    # Hide messages from blocked users (either direction).
    if hidden_ids:
        msg_query = msg_query.filter(
            GameThreadMessage.user_id.notin_(hidden_ids)
        )
    messages = msg_query.order_by(GameThreadMessage.created_at).all()

    last_id = messages[-1].id if messages else 0

    member = GroupMember.query.filter_by(
        group_id=thread.group_id, user_id=current_user.id
    ).first()

    # Opening the thread clears its unread state
    if member:
        from app.services.activity import mark_thread_read
        mark_thread_read(current_user.id, thread_id)
        db.session.commit()

    vote_counts = thread.vote_counts()
    user_vote = thread.user_vote(current_user.id)

    # Participants for the desktop context panel — unique visible authors
    participants = []
    seen = set()
    for m in messages:
        if m.author and m.author.id not in seen:
            seen.add(m.author.id)
            participants.append(m.author)

    member_count = group.members.count()

    return render_template(
        "threads/show.html",
        thread=thread,
        group=group,
        messages=messages,
        last_id=last_id,
        member=member,
        vote_counts=vote_counts,
        user_vote=user_vote,
        participants=participants,
        member_count=member_count,
    )


@threads_bp.route("/<int:thread_id>/messages", methods=["POST"])
@login_required
def post_message(thread_id):
    _fetch = request.headers.get("X-Fetch") == "1"

    thread = GameThread.query.get_or_404(thread_id)
    group = Group.query.get(thread.group_id)
    if not group.is_member(current_user.id):
        if _fetch: return jsonify({"error": "forbidden"}), 403
        abort(403)
    if thread.status != "active":
        if _fetch: return jsonify({"error": "closed"}), 400
        flash("This thread is closed.", "error")
        return redirect(url_for("threads.show", thread_id=thread_id))

    body = request.form.get("body", "").strip()
    if not body:
        if _fetch: return jsonify({"error": "empty"}), 400
        flash("Message cannot be empty.", "error")
        return redirect(url_for("threads.show", thread_id=thread_id))
    if len(body) > 1000:
        if _fetch: return jsonify({"error": "too_long"}), 400
        flash("Message too long (max 1000 chars).", "error")
        return redirect(url_for("threads.show", thread_id=thread_id))

    from app.services.moderation import screen_text
    ok, reason = screen_text(body)
    if not ok:
        if _fetch: return jsonify({"error": "blocked", "message": reason}), 422
        flash(reason, "error")
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

    from app.services.activity import refresh_hot_score, record_event, mark_thread_read
    from app.models import now_utc
    thread.updated_at = now_utc()
    refresh_hot_score(thread)
    record_event(thread.group_id, current_user.id, "reply", thread_id)
    mark_thread_read(current_user.id, thread_id)
    db.session.commit()

    # Notify the thread's target user when someone else posts in their thread
    if thread.target_user_id and thread.target_user_id != current_user.id:
        try:
            from app.models import Notification
            title_preview = thread.title[:60] + ("…" if len(thread.title) > 60 else "")
            notif = Notification(
                user_id=thread.target_user_id,
                type="message_received",
                message=f"{current_user.shown_name} posted in \"{title_preview}\"",
                link_url=f"/threads/{thread_id}",
            )
            db.session.add(notif)
            db.session.commit()
        except Exception:
            pass  # never let notification failure block the message post

    if _fetch:
        return jsonify({
            "success": True,
            "id": msg.id,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        })
    return redirect(url_for("threads.show", thread_id=thread_id))
