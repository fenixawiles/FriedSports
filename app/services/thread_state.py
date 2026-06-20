"""Per-user thread view state: archive, local delete (history clear), restore.

Delete is local — it never removes anything from the shared message store. A
`cleared_at` watermark hides messages at/before it from that user only. A deleted
thread that receives a new message after cleared_at resurfaces as a fresh thread.
Deleted threads auto-purge from the Recently Deleted bin after PURGE_DAYS (the
clear stays; they just stop showing).
"""
from datetime import datetime, timezone, timedelta

from app.models import db, ThreadUserState

PURGE_DAYS = 30


def _aware(dt):
    """Treat naive timestamps (some drivers) as UTC for safe comparison."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def states_for(user_id, thread_ids):
    """{thread_id: ThreadUserState} for the given threads, one query."""
    if not thread_ids:
        return {}
    rows = (
        ThreadUserState.query
        .filter(
            ThreadUserState.user_id == user_id,
            ThreadUserState.thread_id.in_(thread_ids),
        )
        .all()
    )
    return {r.thread_id: r for r in rows}


def _get_or_create(user_id, thread_id):
    st = ThreadUserState.query.filter_by(user_id=user_id, thread_id=thread_id).first()
    if not st:
        st = ThreadUserState(user_id=user_id, thread_id=thread_id)
        db.session.add(st)
    return st


def delete_thread(user_id, thread_id):
    now = datetime.now(timezone.utc)
    st = _get_or_create(user_id, thread_id)
    st.deleted = True
    st.deleted_at = now
    st.cleared_at = now
    st.archived = False
    db.session.commit()


def archive_thread(user_id, thread_id):
    st = _get_or_create(user_id, thread_id)
    st.archived = True
    st.deleted = False
    st.deleted_at = None
    db.session.commit()


def unarchive_thread(user_id, thread_id):
    st = _get_or_create(user_id, thread_id)
    st.archived = False
    db.session.commit()


def restore_thread(user_id, thread_id):
    """Recover from Recently Deleted — full history comes back."""
    st = _get_or_create(user_id, thread_id)
    st.deleted = False
    st.deleted_at = None
    st.cleared_at = None
    st.archived = False
    db.session.commit()


def cleared_at_for(user_id, thread_id):
    st = ThreadUserState.query.filter_by(user_id=user_id, thread_id=thread_id).first()
    return st.cleared_at if st else None


def categorize(states, thread_ids, last_msg_at):
    """thread_id -> 'active' | 'archived' | 'deleted' | 'purged'.

    states:      {thread_id: ThreadUserState}
    last_msg_at: {thread_id: datetime} last visible message time (or None)
    'purged' threads should NOT be shown anywhere.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=PURGE_DAYS)
    out = {}
    for tid in thread_ids:
        st = states.get(tid)
        if st is None or (not st.archived and not st.deleted):
            out[tid] = "active"
            continue
        if st.archived:
            out[tid] = "archived"
            continue
        # deleted: resurrected if a new message arrived after the clear
        lm = _aware(last_msg_at.get(tid))
        cl = _aware(st.cleared_at)
        if lm and cl and lm > cl:
            out[tid] = "active"
        elif _aware(st.deleted_at) and _aware(st.deleted_at) > cutoff:
            out[tid] = "deleted"
        else:
            out[tid] = "purged"
    return out
