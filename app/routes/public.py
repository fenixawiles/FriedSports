from flask import Blueprint, render_template, abort
from app.models import Receipt, GameThreadMessage

public_bp = Blueprint("public", __name__)


@public_bp.route("/receipts/<slug>")
def receipt(slug):
    r = Receipt.query.filter_by(public_slug=slug).first_or_404()

    # Find the worst system message from the thread
    worst_msg = GameThreadMessage.query.filter_by(
        thread_id=r.thread_id,
        message_type="system",
        is_deleted=False,
    ).order_by(GameThreadMessage.created_at.desc()).first()

    return render_template("public/receipt.html", receipt=r, worst_msg=worst_msg)
