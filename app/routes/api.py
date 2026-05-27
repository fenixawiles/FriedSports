from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app.models import db, GameThread, GameThreadMessage, MessageReaction, MessageReport, Group, GroupMember, GameEvent, GroupTrigger
from app.services.scoring import apply_reaction_points

api_bp = Blueprint("api", __name__)


@api_bp.route("/threads/<int:thread_id>/messages.json")
@login_required
def thread_messages(thread_id):
    thread = GameThread.query.get_or_404(thread_id)
    group = Group.query.get(thread.group_id)
    if not group.is_member(current_user.id) and group.privacy != "public_readonly":
        abort(403)

    after_id = request.args.get("after", 0, type=int)
    # Eager-load author + reactions to eliminate N+1
    messages = (
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
        .order_by(GameThreadMessage.created_at)
        .all()
    )

    user_is_admin = _is_admin(current_user.id, thread.group_id)
    result = []
    for m in messages:
        result.append({
            "id": m.id,
            "type": m.message_type,
            "body": m.body,
            "author": m.author.shown_name if m.author else "FriedSports",
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "reactions": m.reaction_counts(),
            "user_reactions": m.user_reaction(current_user.id),
            "can_delete": m.user_id == current_user.id or user_is_admin,
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
    if not Group.query.get(thread.group_id).is_member(current_user.id):
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
    group = Group.query.get(thread.group_id)

    can_delete = (
        msg.user_id == current_user.id or
        _is_admin(current_user.id, thread.group_id)
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
    if not Group.query.get(thread.group_id).is_member(current_user.id):
        abort(403)

    reason = request.json.get("reason") if request.is_json else request.form.get("reason")

    existing = MessageReport.query.filter_by(
        message_id=message_id,
        reporter_user_id=current_user.id,
    ).first()
    if existing:
        return jsonify({"error": "Already reported"}), 400

    report = MessageReport(
        message_id=message_id,
        reporter_user_id=current_user.id,
        reason=reason,
    )
    db.session.add(report)
    db.session.commit()
    return jsonify({"success": True})


def _is_admin(user_id, group_id):
    member = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first()
    return member and member.role in ("owner", "admin")
