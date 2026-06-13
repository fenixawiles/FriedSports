import re
from flask import Blueprint, render_template
from app.models import Receipt, GameThreadMessage

public_bp = Blueprint("public", __name__)


def _anonymize(text, names):
    """Replace any of the given personal names in `text` with a generic token,
    so the public receipt never names an individual."""
    if not text:
        return text
    for n in names:
        if n:
            text = re.sub(re.escape(n), "this fan", text, flags=re.IGNORECASE)
    return text


@public_bp.route("/receipts/<slug>")
def receipt(slug):
    r = Receipt.query.filter_by(public_slug=slug).first_or_404()

    # Find the worst system message from the thread
    worst_msg = GameThreadMessage.query.filter_by(
        thread_id=r.thread_id,
        message_type="system",
        is_deleted=False,
    ).order_by(GameThreadMessage.created_at.desc()).first()

    # Public receipts are anonymized — scrub any personal names that may be
    # embedded in the stored title/summary or the system-generated line.
    names = []
    if r.target_user:
        names += [r.target_user.display_name, r.target_user.first_name, r.target_user.last_name]
    if r.top_hater:
        names += [r.top_hater.display_name, r.top_hater.first_name, r.top_hater.last_name]

    worst_body = _anonymize(worst_msg.body, names) if worst_msg else None
    disp_title = _anonymize(r.title, names)
    disp_summary = _anonymize(r.summary, names)

    return render_template(
        "public/receipt.html",
        receipt=r,
        worst_body=worst_body,
        disp_title=disp_title,
        disp_summary=disp_summary,
    )
