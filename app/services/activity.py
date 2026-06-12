"""Social-state helpers: unread counts, latest-message previews, votes,
hot scores, and activity events. All batch functions are single-query —
never call the per-thread model helpers in a loop."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from app.models import (
    db, GameThread, GameThreadMessage, ThreadRead, ThreadVote, ActivityEvent,
    now_utc,
)


def unread_map(user_id, thread_ids):
    """{thread_id: unread_count} for the given threads, one query.
    A thread the user never opened counts every message as unread."""
    if not thread_ids:
        return {}
    rows = (
        db.session.query(
            GameThreadMessage.thread_id,
            func.count(GameThreadMessage.id),
        )
        .outerjoin(
            ThreadRead,
            (ThreadRead.thread_id == GameThreadMessage.thread_id)
            & (ThreadRead.user_id == user_id),
        )
        .filter(
            GameThreadMessage.thread_id.in_(thread_ids),
            GameThreadMessage.is_deleted == False,  # noqa: E712
            (ThreadRead.id == None)  # noqa: E711
            | (GameThreadMessage.created_at > ThreadRead.last_read_at),
        )
        .group_by(GameThreadMessage.thread_id)
        .all()
    )
    return {tid: cnt for tid, cnt in rows}


def message_counts(thread_ids):
    """{thread_id: visible_message_count}, one query."""
    if not thread_ids:
        return {}
    rows = (
        db.session.query(
            GameThreadMessage.thread_id,
            func.count(GameThreadMessage.id),
        )
        .filter(
            GameThreadMessage.thread_id.in_(thread_ids),
            GameThreadMessage.is_deleted == False,  # noqa: E712
        )
        .group_by(GameThreadMessage.thread_id)
        .all()
    )
    return {tid: cnt for tid, cnt in rows}


def latest_messages(thread_ids):
    """{thread_id: last GameThreadMessage} with authors eager-loaded."""
    if not thread_ids:
        return {}
    from sqlalchemy.orm import joinedload
    last_id_subq = (
        db.session.query(
            GameThreadMessage.thread_id,
            func.max(GameThreadMessage.id).label("max_id"),
        )
        .filter(
            GameThreadMessage.thread_id.in_(thread_ids),
            GameThreadMessage.is_deleted == False,  # noqa: E712
        )
        .group_by(GameThreadMessage.thread_id)
        .subquery()
    )
    rows = (
        GameThreadMessage.query
        .join(last_id_subq, GameThreadMessage.id == last_id_subq.c.max_id)
        .options(joinedload(GameThreadMessage.author))
        .all()
    )
    return {m.thread_id: m for m in rows}


def vote_count_map(thread_ids):
    """{thread_id: {'confirm': n, 'dismiss': n, 'redeem': n}}, one query."""
    if not thread_ids:
        return {}
    rows = (
        db.session.query(
            ThreadVote.thread_id, ThreadVote.vote_type, func.count(ThreadVote.id)
        )
        .filter(ThreadVote.thread_id.in_(thread_ids))
        .group_by(ThreadVote.thread_id, ThreadVote.vote_type)
        .all()
    )
    out = {}
    for tid, vtype, cnt in rows:
        out.setdefault(tid, {"confirm": 0, "dismiss": 0, "redeem": 0})[vtype] = cnt
    return out


def mark_thread_read(user_id, thread_id):
    """Upsert the read watermark to now. Caller commits."""
    read = ThreadRead.query.filter_by(user_id=user_id, thread_id=thread_id).first()
    if read:
        read.last_read_at = now_utc()
    else:
        db.session.add(ThreadRead(user_id=user_id, thread_id=thread_id,
                                  last_read_at=now_utc()))


def compute_hot_score(thread):
    """Simple recency-weighted activity score. Stored on the thread row so
    list pages can sort without recomputing."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent = (
        thread.messages
        .filter(
            GameThreadMessage.is_deleted == False,  # noqa: E712
            GameThreadMessage.created_at > cutoff,
        )
        .count()
    )
    total = thread.reply_count()
    votes = sum(thread.vote_counts().values())
    return total + (recent * 3) + (votes * 2)


def refresh_hot_score(thread):
    """Recompute and store hot_score. Caller commits."""
    thread.hot_score = compute_hot_score(thread)


def record_event(group_id, actor_id, event_type, entity_id=None):
    """Append to the group activity feed. Caller commits; never raises."""
    try:
        db.session.add(ActivityEvent(
            group_id=group_id, actor_id=actor_id,
            event_type=event_type, entity_id=entity_id,
        ))
    except Exception:
        pass
