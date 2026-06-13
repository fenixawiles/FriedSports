"""Content moderation helpers.

Two responsibilities:
  1. `screen_text()` — a lightweight server-side filter that rejects content
     Apple's guidelines treat as never-acceptable (slurs / hate speech /
     explicit threats of real-world harm). This is deliberately narrow: the
     app's whole point is trash talk, so we do NOT filter profanity or
     insults — only categorically prohibited content. Everything else is
     handled reactively via user reports + the admin moderation queue.
  2. `record_report()` — create a MessageReport, guarding against duplicates.

The blocklist is intentionally small and high-precision. It is a backstop,
not the primary safety mechanism (report + block + admin review are).
"""
import re

# High-precision list of categorically prohibited slurs. Deliberately limited
# to UNAMBIGUOUS terms whose folded form does not collide with ordinary words —
# critical for a sports app (e.g. "chink in the armor", "spicy", "tycoon",
# "Nigeria" must NOT trip the filter). Context-dependent slurs are handled
# reactively via user reports + the admin moderation queue, not auto-blocked.
# (Matched against the leetspeak-folded, separator-stripped form; see _normalize.)
_PROHIBITED = {
    "nigger", "faggot", "kike", "wetback", "tranny",
    # explicit real-world-harm threats are handled by _THREAT_PATTERNS below
}

# Explicit threat of real-world harm — phrasing-based, not single words.
_THREAT_PATTERNS = [
    re.compile(r"\bi('?m| am| will| wanna| want to| gonna)?\s*(go(ing)?\s+to\s+)?kill\s+(you|u|him|her|them)\b", re.I),
    re.compile(r"\b(i'?ll|i will|gonna)\s+(find|hunt)\s+(you|u)\b.*\b(kill|hurt|beat)\b", re.I),
    re.compile(r"\bi\s+know\s+where\s+you\s+live\b", re.I),
]

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})


def _normalize(text):
    """Lowercase, fold common leetspeak, strip repeated chars/separators so
    'n i g g e r' and 'n1gg3r' both collapse to the canonical form."""
    t = text.lower().translate(_LEET)
    # remove non-alphanumerics so spaced/punctuated evasions collapse
    return re.sub(r"[^a-z0-9]", "", t)


def screen_text(text):
    """Return (ok, reason).

    ok=True  → content is allowed.
    ok=False → reason is a short user-facing message explaining the block.

    Only categorically prohibited content (hate slurs, explicit threats) is
    rejected. Ordinary trash talk, profanity and insults pass through.
    """
    if not text:
        return True, None

    # 1. Explicit threats of harm (phrase-based, on the raw text)
    for pat in _THREAT_PATTERNS:
        if pat.search(text):
            return False, ("This looks like a threat of real-world harm. "
                           "That's not allowed on FriedSports.")

    # 2. Hate slurs (normalized, boundary-aware via collapsed form)
    folded = _normalize(text)
    for term in _PROHIBITED:
        if term in folded:
            return False, ("That message contains a slur we don't allow. "
                           "Keep it to the sports takes.")

    return True, None


def record_report(message_id, reporter_user_id, category=None, reason=None):
    """Create a MessageReport, returning (report, created).

    created=False if this reporter already has an open report on the message
    (prevents duplicate spam). Caller commits.
    """
    from app.models import db, MessageReport

    existing = MessageReport.query.filter_by(
        message_id=message_id,
        reporter_user_id=reporter_user_id,
    ).first()
    if existing:
        return existing, False

    report = MessageReport(
        message_id=message_id,
        reporter_user_id=reporter_user_id,
        category=category,
        reason=reason,
    )
    db.session.add(report)
    return report, True
