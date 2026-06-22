from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app.models import db, GameThread, GameThreadMessage, MessageReaction, MessageReport, Group, GroupMember, GameEvent, GroupTrigger, DeviceToken
from app.services.scoring import apply_reaction_points

api_bp = Blueprint("api", __name__)


@api_bp.route("/threads/<int:thread_id>/messages.json")
@login_required
def thread_messages(thread_id):
    thread = GameThread.query.get_or_404(thread_id)
    if not _can_access_thread(thread):
        abort(403)

    after_id = request.args.get("after", 0, type=int)
    hidden_ids = current_user.hidden_user_ids()
    # Eager-load author + reactions to eliminate N+1
    mq = (
        GameThreadMessage.query
        .filter(
            GameThreadMessage.thread_id == thread_id,
            GameThreadMessage.id > after_id,
            GameThreadMessage.is_deleted == False,
        )
        .options(
            joinedload(GameThreadMessage.author),
            joinedload(GameThreadMessage.reactions),
        )
    )
    if hidden_ids:
        mq = mq.filter(GameThreadMessage.user_id.notin_(hidden_ids))
    # Local-delete: hide messages at/before this user's clear watermark.
    from app.services.thread_state import cleared_at_for
    cleared = cleared_at_for(current_user.id, thread_id)
    if cleared:
        mq = mq.filter(GameThreadMessage.created_at > cleared)
    messages = mq.order_by(GameThreadMessage.created_at).all()

    user_is_admin = bool(thread.group_id and _is_admin(current_user.id, thread.group_id))
    result = []
    for m in messages:
        reply = None
        if m.reply_to_id and m.reply_to and not m.reply_to.is_deleted:
            reply = {
                "author": m.reply_to.author.shown_name if m.reply_to.author else "FriedSports",
                "body": m.reply_to.body,
            }
        result.append({
            "id": m.id,
            "type": m.message_type,
            "body": m.body,
            "author": m.author.shown_name if m.author else "FriedSports",
            "author_id": m.user_id,
            "is_mine": m.user_id == current_user.id,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "reactions": m.reaction_counts(),
            "user_reactions": m.user_reaction(current_user.id),
            "can_delete": m.user_id == current_user.id or user_is_admin,
            "reply_to": reply,
        })
    return jsonify(result)


@api_bp.route("/dashboard/alerts.json")
@login_required
def dashboard_alerts():
    memberships = GroupMember.query.filter_by(user_id=current_user.id).all()
    group_ids = [m.group_id for m in memberships]

    if not group_ids:
        return jsonify({"count": 0, "threads": []})

    threads = GameThread.query.filter(
        GameThread.group_id.in_(group_ids),
        GameThread.status == "active",
        GameThread.target_user_id == current_user.id,
    ).order_by(GameThread.created_at.desc()).limit(10).all()

    result = []
    for t in threads:
        result.append({
            "id": t.id,
            "title": t.title,
            "group_id": t.group_id,
            "url": f"/threads/{t.id}",
        })

    return jsonify({"count": len(result), "threads": result})


@api_bp.route("/messages/<int:message_id>/react", methods=["POST"])
@login_required
def react(message_id):
    msg = GameThreadMessage.query.get_or_404(message_id)
    thread = GameThread.query.get(msg.thread_id)
    if not _can_access_thread(thread):
        abort(403)

    reaction_type = request.json.get("reaction_type") if request.is_json else request.form.get("reaction_type")
    valid_types = ("laugh", "cook", "fraud", "receipt")
    if reaction_type not in valid_types:
        return jsonify({"error": "Invalid reaction type"}), 400

    existing = MessageReaction.query.filter_by(
        message_id=message_id,
        user_id=current_user.id,
        reaction_type=reaction_type,
    ).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        added = False
    else:
        reaction = MessageReaction(
            message_id=message_id,
            user_id=current_user.id,
            reaction_type=reaction_type,
        )
        db.session.add(reaction)
        db.session.flush()
        apply_reaction_points(msg, current_user.id)
        db.session.commit()
        added = True

    return jsonify({"counts": msg.reaction_counts(), "added": added})


@api_bp.route("/messages/<int:message_id>/delete", methods=["POST"])
@login_required
def delete_message(message_id):
    msg = GameThreadMessage.query.get_or_404(message_id)
    thread = GameThread.query.get(msg.thread_id)

    can_delete = (
        msg.user_id == current_user.id or
        bool(thread.group_id and _is_admin(current_user.id, thread.group_id))
    )
    if not can_delete:
        abort(403)

    msg.is_deleted = True
    db.session.commit()
    return jsonify({"success": True})


@api_bp.route("/messages/<int:message_id>/report", methods=["POST"])
@login_required
def report_message(message_id):
    msg = GameThreadMessage.query.get_or_404(message_id)
    thread = GameThread.query.get(msg.thread_id)
    if not _can_access_thread(thread):
        abort(403)

    # You can't report your own message.
    if msg.user_id == current_user.id:
        return jsonify({"error": "You can't report your own message."}), 400

    data = request.get_json(silent=True) or {}
    category = (data.get("category") or request.form.get("category") or "other").strip()
    reason = (data.get("reason") if request.is_json else request.form.get("reason")) or None
    valid = set(MessageReport.CATEGORY_LABELS.keys())
    if category not in valid:
        category = "other"

    from app.services.moderation import record_report
    report, created = record_report(
        message_id=message_id,
        reporter_user_id=current_user.id,
        category=category,
        reason=reason,
    )
    if not created:
        return jsonify({"error": "You've already reported this message.",
                        "already": True}), 409
    db.session.commit()
    return jsonify({"success": True})


def _is_direct_participant(thread):
    return (
        (thread.created_by_user_id == current_user.id and thread.target_user_id)
        or (thread.target_user_id == current_user.id and thread.created_by_user_id)
    )


def _can_access_thread(thread):
    if not thread:
        return False
    if (thread.thread_type or "incident") == "direct_chat":
        if not _is_direct_participant(thread):
            return False
        other_id = (
            thread.target_user_id
            if thread.created_by_user_id == current_user.id
            else thread.created_by_user_id
        )
        return other_id not in current_user.hidden_user_ids()
    group = Group.query.get(thread.group_id) if thread.group_id else None
    return bool(group and group.is_member(current_user.id))


def _require_member(thread_id):
    """Load a thread and 403 unless the current user can access it."""
    thread = GameThread.query.get_or_404(thread_id)
    if not _can_access_thread(thread):
        abort(403)
    return thread


@api_bp.route("/threads/<int:thread_id>/archive", methods=["POST"])
@login_required
def thread_archive(thread_id):
    from app.services import thread_state
    _require_member(thread_id)
    thread_state.archive_thread(current_user.id, thread_id)
    return jsonify({"ok": True, "state": "archived"})


@api_bp.route("/threads/<int:thread_id>/unarchive", methods=["POST"])
@login_required
def thread_unarchive(thread_id):
    from app.services import thread_state
    _require_member(thread_id)
    thread_state.unarchive_thread(current_user.id, thread_id)
    return jsonify({"ok": True, "state": "active"})


@api_bp.route("/threads/<int:thread_id>/delete-local", methods=["POST"])
@login_required
def thread_delete_local(thread_id):
    """Delete the thread for THIS user only — clears their history, leaves the
    shared message store untouched. Moves to Recently Deleted."""
    from app.services import thread_state
    _require_member(thread_id)
    thread_state.delete_thread(current_user.id, thread_id)
    return jsonify({"ok": True, "state": "deleted"})


@api_bp.route("/threads/<int:thread_id>/restore", methods=["POST"])
@login_required
def thread_restore(thread_id):
    from app.services import thread_state
    _require_member(thread_id)
    thread_state.restore_thread(current_user.id, thread_id)
    return jsonify({"ok": True, "state": "active"})


@api_bp.route("/device-token", methods=["POST"])
@login_required
def register_device_token():
    """Called by the iOS app on launch to register/refresh the APNs device token."""
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    if not token:
        return jsonify({"error": "token required"}), 400

    existing = DeviceToken.query.filter_by(token=token).first()
    if existing:
        # Re-associate with current user if token moved (e.g. reinstall)
        existing.user_id = current_user.id
    else:
        db.session.add(DeviceToken(
            user_id=current_user.id,
            token=token,
            platform="ios",
        ))
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.route("/groups/<int:group_id>/members")
@login_required
def group_members(group_id):
    group = Group.query.get_or_404(group_id)
    requester = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not requester and group.privacy != "public_readonly":
        abort(403)

    all_members = (
        GroupMember.query
        .options(joinedload(GroupMember.user))
        .filter_by(group_id=group_id)
        .all()
    )

    is_owner = requester and requester.role == "owner"
    is_admin = requester and requester.role in ("owner", "admin")

    result = []
    for m in all_members:
        can_remove = (
            is_admin
            and m.role != "owner"
            and m.user_id != current_user.id
        )
        can_transfer = (
            is_owner
            and m.user_id != current_user.id
        )
        result.append({
            "user_id": m.user_id,
            "display_name": m.user.shown_name if m.user else "Unknown",
            "role": m.role,
            "can_remove": can_remove,
            "can_transfer": can_transfer,
        })

    return jsonify(result)


def _is_admin(user_id, group_id):
    if not group_id:
        return False
    member = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first()
    return member and member.role in ("owner", "admin")


@api_bp.route("/users/search")
@login_required
def search_users():
    """Live user search for friends page. Returns JSON list with friendship status."""
    from app.models import User, FriendRequest
    from sqlalchemy import or_, and_

    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])

    users = (
        User.query
        .filter(
            User.id != current_user.id,
            or_(
                User.email.ilike(f"%{q}%"),
                User.uid.ilike(f"%{q}%"),
                User.display_name.ilike(f"%{q}%"),
                User.first_name.ilike(f"%{q}%"),
                User.last_name.ilike(f"%{q}%"),
            ),
        )
        .limit(20)
        .all()
    )

    if not users:
        return jsonify([])

    user_ids = [u.id for u in users]

    # One batch query instead of 1 per user — eliminates N+1 (was up to 21 queries).
    fr_rows = FriendRequest.query.filter(
        or_(
            and_(FriendRequest.from_user_id == current_user.id,
                 FriendRequest.to_user_id.in_(user_ids)),
            and_(FriendRequest.to_user_id   == current_user.id,
                 FriendRequest.from_user_id.in_(user_ids)),
        )
    ).all()

    # Build a lookup: other_user_id → FriendRequest
    fr_map = {}
    for fr in fr_rows:
        other = fr.to_user_id if fr.from_user_id == current_user.id else fr.from_user_id
        fr_map[other] = fr

    result = []
    for user in users:
        fr = fr_map.get(user.id)
        if fr is None:
            status = "none"
        elif fr.status == "accepted":
            status = "friends"
        elif fr.status == "pending":
            status = "pending_sent" if fr.from_user_id == current_user.id else "pending_received"
        else:
            status = "none"

        result.append({
            "id":   user.id,
            "name": user.shown_name,
            "uid":  user.uid,
            "status": status,
        })

    return jsonify(result)
