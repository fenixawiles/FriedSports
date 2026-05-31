from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from app.models import db, User, FriendRequest, Notification

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
    results = []
    if q:
        results = (
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
            .limit(20)
            .all()
        )
        results = [{"user": u, "status": _friendship_status(u.id)} for u in results]

    # Build friends list
    sent     = FriendRequest.query.filter_by(from_user_id=current_user.id, status="accepted").all()
    received = FriendRequest.query.filter_by(to_user_id=current_user.id,   status="accepted").all()
    friend_ids = [fr.to_user_id for fr in sent] + [fr.from_user_id for fr in received]
    friends = User.query.filter(User.id.in_(friend_ids)).all() if friend_ids else []

    return render_template("friends.html", friends=friends, results=results, q=q)


@friends_bp.route("/request/<int:user_id>", methods=["POST"])
@login_required
def send_request(user_id):
    if user_id == current_user.id:
        flash("You can't add yourself.", "error")
        return redirect(url_for("friends.index"))

    target = User.query.get_or_404(user_id)

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
