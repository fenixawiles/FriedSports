from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from app.models import db, User, FriendRequest, Notification, BlockedUser

friends_bp = Blueprint("friends", __name__)


def _friendship_status(user_id):
    """Return the friendship status between current_user and user_id.
    Returns: 'self' | 'friends' | 'pending_sent' | 'pending_received' | 'none'
    """
    if user_id == current_user.id:
        return "self"
    fr = FriendRequest.query.filter(
        or_(
            and_(FriendRequest.from_user_id == current_user.id,
                    FriendRequest.to_user_id   == user_id),
            and_(FriendRequest.from_user_id == user_id,
                    FriendRequest.to_user_id   == current_user.id),
        )
    ).first()
    if not fr:
        return "none"
    if fr.status == "accepted":
        return "friends"
    if fr.status == "pending":
        return "pending_sent" if fr.from_user_id == current_user.id else "pending_received"
    return "none"


@friends_bp.route("/")
@login_required
def index():
    """Friends list + search."""
    q = request.args.get("q", "").strip()
    hidden_ids = current_user.hidden_user_ids()
    results = []
    if q:
        query = (
            User.query
            .filter(
                User.id != current_user.id,
                or_(
                    User.email.ilike(f"%{q}%"),
                    User.uid.ilike(f"%{q}%"),
                    User.display_name.ilike(f"%{q}%"),
                    User.first_name.ilike(f"%{q}%"),
                    User.last_name.ilike(f"%{q}%"),
                )
            )
        )
        # Blocked users (either direction) never appear in search.
        if hidden_ids:
            query = query.filter(User.id.notin_(hidden_ids))
        results = query.limit(20).all()
        results = [{"user": u, "status": _friendship_status(u.id)} for u in results]

    # Build friends list
    sent     = FriendRequest.query.filter_by(from_user_id=current_user.id, status="accepted").all()
    received = FriendRequest.query.filter_by(to_user_id=current_user.id,   status="accepted").all()
    friend_ids = [fr.to_user_id for fr in sent] + [fr.from_user_id for fr in received]
    # Defensive: never show a blocked user as a friend even if a stale row exists.
    friend_ids = [fid for fid in friend_ids if fid not in hidden_ids]
    friends = User.query.filter(User.id.in_(friend_ids)).all() if friend_ids else []

    # Incoming pending requests
    pending_requests = (
        FriendRequest.query
        .filter_by(to_user_id=current_user.id, status="pending")
        .order_by(FriendRequest.created_at.desc())
        .all()
    )

    # Shared-group counts — one query for all friends
    from app.models import GroupMember
    from sqlalchemy import func
    shared_counts = {}
    total_shared_groups = 0
    if friends:
        my_group_ids = [
            gid for (gid,) in db.session.query(GroupMember.group_id)
            .filter_by(user_id=current_user.id).all()
        ]
        if my_group_ids:
            rows = (
                db.session.query(GroupMember.user_id, func.count(GroupMember.id))
                .filter(
                    GroupMember.user_id.in_(friend_ids),
                    GroupMember.group_id.in_(my_group_ids),
                )
                .group_by(GroupMember.user_id)
                .all()
            )
            shared_counts = {uid: cnt for uid, cnt in rows}
            shared_group_rows = (
                db.session.query(func.count(func.distinct(GroupMember.group_id)))
                .filter(
                    GroupMember.user_id.in_(friend_ids),
                    GroupMember.group_id.in_(my_group_ids),
                )
                .scalar()
            )
            total_shared_groups = shared_group_rows or 0

    return render_template(
        "friends.html",
        friends=friends,
        results=results,
        q=q,
        pending_requests=pending_requests,
        shared_counts=shared_counts,
        total_shared_groups=total_shared_groups,
    )


@friends_bp.route("/request/<int:user_id>", methods=["POST"])
@login_required
def send_request(user_id):
    if user_id == current_user.id:
        flash("You can't add yourself.", "error")
        return redirect(url_for("friends.index"))

    target = User.query.get_or_404(user_id)

    # No friend requests across a block (either direction).
    if user_id in current_user.hidden_user_ids():
        if request.headers.get("X-Fetch") == "1":
            return jsonify({"ok": False, "error": "blocked"}), 403
        flash("You can't send a request to this user.", "error")
        return redirect(request.referrer or url_for("friends.index"))

    # Check if already a request/friend
    existing = FriendRequest.query.filter(
        or_(
            and_(FriendRequest.from_user_id == current_user.id,
                    FriendRequest.to_user_id   == user_id),
            and_(FriendRequest.from_user_id == user_id,
                    FriendRequest.to_user_id   == current_user.id),
        )
    ).first()

    if existing:
        if existing.status == "accepted":
            flash("You're already friends.", "info")
        elif existing.status == "pending":
            flash("Request already sent.", "info")
        else:
            # declined — allow retry
            existing.status = "pending"
            existing.from_user_id = current_user.id
            existing.to_user_id   = user_id
            db.session.commit()
            # Email the recipient (best-effort)
            try:
                from app.services.email_service import send_friend_request_email
                send_friend_request_email(current_user, target)
            except Exception:
                pass
            flash(f"Friend request sent to {target.shown_name}.", "success")
        if request.headers.get("X-Fetch") == "1":
            return jsonify({"ok": True, "status": "pending_sent"})
        return redirect(request.referrer or url_for("friends.index"))

    fr = FriendRequest(from_user_id=current_user.id, to_user_id=user_id)
    db.session.add(fr)
    db.session.flush()

    # Notify recipient
    notif = Notification(
        user_id=user_id,
        type="friend_request",
        message=f"{current_user.shown_name} sent you a friend request",
        link_url="/notifications",
    )
    db.session.add(notif)
    db.session.commit()

    # Email the recipient (best-effort — failure must not block the request)
    try:
        from app.services.email_service import send_friend_request_email
        send_friend_request_email(current_user, target)
    except Exception:
        pass

    if request.headers.get("X-Fetch") == "1":
        return jsonify({"ok": True, "status": "pending_sent"})
    flash(f"Friend request sent to {target.shown_name}.", "success")
    return redirect(request.referrer or url_for("friends.index"))


@friends_bp.route("/accept/<int:request_id>", methods=["POST"])
@login_required
def accept_request(request_id):
    fr = FriendRequest.query.get_or_404(request_id)
    if fr.to_user_id != current_user.id:
        abort(403)
    fr.status = "accepted"

    # Notify the requester
    notif = Notification(
        user_id=fr.from_user_id,
        type="friend_accepted",
        message=f"{current_user.shown_name} accepted your friend request",
        link_url="/friends",
    )
    db.session.add(notif)
    db.session.commit()

    if request.headers.get("X-Fetch") == "1":
        return jsonify({"ok": True, "name": fr.from_user.shown_name})
    flash(f"You're now friends with {fr.from_user.shown_name}.", "success")
    return redirect(request.referrer or url_for("friends.index"))


@friends_bp.route("/decline/<int:request_id>", methods=["POST"])
@login_required
def decline_request(request_id):
    fr = FriendRequest.query.get_or_404(request_id)
    if fr.to_user_id != current_user.id:
        abort(403)
    db.session.delete(fr)
    db.session.commit()
    if request.headers.get("X-Fetch") == "1":
        return jsonify({"ok": True})
    return redirect(request.referrer or url_for("dashboard.notifications"))


@friends_bp.route("/remove/<int:user_id>", methods=["POST"])
@login_required
def remove_friend(user_id):
    fr = FriendRequest.query.filter(
        or_(
            and_(FriendRequest.from_user_id == current_user.id,
                    FriendRequest.to_user_id   == user_id),
            and_(FriendRequest.from_user_id == user_id,
                    FriendRequest.to_user_id   == current_user.id),
        ),
        FriendRequest.status == "accepted",
    ).first()
    if fr:
        db.session.delete(fr)
        db.session.commit()
    flash("Friend removed.", "info")
    return redirect(request.referrer or url_for("friends.index"))


def _purge_relationship(user_a, user_b):
    """Delete any friend request / friendship rows between two users (either
    direction). Used when a block is placed."""
    FriendRequest.query.filter(
        or_(
            and_(FriendRequest.from_user_id == user_a, FriendRequest.to_user_id == user_b),
            and_(FriendRequest.from_user_id == user_b, FriendRequest.to_user_id == user_a),
        )
    ).delete(synchronize_session=False)


@friends_bp.route("/block/<int:user_id>", methods=["POST"])
@login_required
def block_user(user_id):
    """Block a user: severs any friendship, drops pending requests, and hides
    each user's content from the other (enforced via User.hidden_user_ids)."""
    if user_id == current_user.id:
        if request.headers.get("X-Fetch") == "1":
            return jsonify({"ok": False, "error": "cannot block yourself"}), 400
        flash("You can't block yourself.", "error")
        return redirect(request.referrer or url_for("friends.index"))

    target = User.query.get_or_404(user_id)

    existing = BlockedUser.query.filter_by(
        blocker_id=current_user.id, blocked_id=user_id
    ).first()
    if not existing:
        db.session.add(BlockedUser(blocker_id=current_user.id, blocked_id=user_id))
    # Severing the relationship is idempotent and safe to repeat.
    _purge_relationship(current_user.id, user_id)
    db.session.commit()

    if request.headers.get("X-Fetch") == "1":
        return jsonify({"ok": True, "blocked": True})
    flash(f"{target.shown_name} has been blocked.", "info")
    return redirect(request.referrer or url_for("friends.index"))


@friends_bp.route("/unblock/<int:user_id>", methods=["POST"])
@login_required
def unblock_user(user_id):
    BlockedUser.query.filter_by(
        blocker_id=current_user.id, blocked_id=user_id
    ).delete(synchronize_session=False)
    db.session.commit()
    if request.headers.get("X-Fetch") == "1":
        return jsonify({"ok": True, "blocked": False})
    flash("User unblocked.", "info")
    return redirect(request.referrer or url_for("friends.blocked_list"))


@friends_bp.route("/blocked")
@login_required
def blocked_list():
    """The current user's block list — reachable from Settings."""
    rows = (
        BlockedUser.query
        .filter_by(blocker_id=current_user.id)
        .order_by(BlockedUser.created_at.desc())
        .all()
    )
    blocked = [(b, User.query.get(b.blocked_id)) for b in rows]
    blocked = [(b, u) for (b, u) in blocked if u is not None]
    return render_template("friends/blocked.html", blocked=blocked)
