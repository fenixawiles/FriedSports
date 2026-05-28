from datetime import datetime, timedelta, timezone
from app.models import db, GroupMember, GameThreadMessage

SHAME_POINTS = {
    "BLOWOUT_ALERT": lambda margin: 20 if margin >= 35 else (10 if margin >= 25 else 5),
    "CHOKED_LEAD": lambda margin: 15,
    "PLAYOFF_COLLAPSE": lambda margin: 30,
    "RIVAL_WINNING": lambda margin: 10,
    "RIVAL_LOSS": lambda margin: 10,
    "ELIMINATION_RISK": lambda margin: 10,
    "SHUTOUT_RISK": lambda margin: 10,
    "DISASTER_QUARTER": lambda margin: 5,
    "FRAUD_WATCH": lambda margin: 5,
    "UPSET_ALERT": lambda margin: 10,
    "FINAL_LOSS": lambda margin: 15 if margin >= 17 else 5,
    "PREMATURE_SLANDER": lambda margin: 0,
}

SEVERITY_SHAME = {1: 2, 2: 5, 3: 10, 4: 15, 5: 25}


def apply_trigger_shame(group_id, user_id, trigger_type, margin=0):
    member = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first()
    if not member:
        return 0
    fn = SHAME_POINTS.get(trigger_type, lambda m: 5)
    delta = fn(margin)
    member.shame_score = (member.shame_score or 0) + delta
    db.session.commit()
    return delta


def apply_incident_shame(group_id, target_user_id, severity):
    """Apply shame to incident target based on severity (1–5)."""
    pts = SEVERITY_SHAME.get(severity, 5)
    member = GroupMember.query.filter_by(group_id=group_id, user_id=target_user_id).first()
    if member:
        member.shame_score = (member.shame_score or 0) + pts


def apply_reporter_points(group_id, reporter_user_id, target_user_id, target_team_id):
    """
    +5 for filing a report.
    +5 bonus if first report in this group for same target/team in the last 24 hours.
    """
    from app.models import IncidentReport
    member = GroupMember.query.filter_by(group_id=group_id, user_id=reporter_user_id).first()
    if not member:
        return
    member.reporter_score = (member.reporter_score or 0) + 5

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    prior = IncidentReport.query.filter(
        IncidentReport.group_id == group_id,
        IncidentReport.target_user_id == target_user_id,
        IncidentReport.target_team_id == target_team_id,
        IncidentReport.created_at >= cutoff,
        IncidentReport.reporter_user_id != reporter_user_id,
    ).first()
    if not prior:
        member.reporter_score += 5  # first-report bonus


def apply_dismiss_penalty(group_id, reporter_user_id):
    """−5 reporter_score when a report is dismissed."""
    member = GroupMember.query.filter_by(group_id=group_id, user_id=reporter_user_id).first()
    if member:
        member.reporter_score = max(0, (member.reporter_score or 0) - 5)


def apply_thread_points(thread, new_message):
    """Award scoring points when a message is posted to a thread.
    Does NOT commit — caller is responsible for committing."""
    if new_message.message_type != "user" or not new_message.user_id:
        return

    sender_id = new_message.user_id
    target_user_id = thread.target_user_id
    group_id = thread.group_id

    sender_member = GroupMember.query.filter_by(group_id=group_id, user_id=sender_id).first()
    target_member = GroupMember.query.filter_by(group_id=group_id, user_id=target_user_id).first()

    if not sender_member:
        return

    prior_user_messages = GameThreadMessage.query.filter(
        GameThreadMessage.thread_id == thread.id,
        GameThreadMessage.message_type == "user",
        GameThreadMessage.id != new_message.id
    ).count()

    if prior_user_messages == 0 and sender_id != target_user_id:
        sender_member.trash_talk_score = (sender_member.trash_talk_score or 0) + 5
    elif sender_id != target_user_id and not thread.target_has_replied():
        sender_member.trash_talk_score = (sender_member.trash_talk_score or 0) + 3

    if sender_id == target_user_id and target_member:
        target_member.defense_score = (target_member.defense_score or 0) + 5


def apply_reaction_points(message, reactor_user_id):
    """Award +1 trash_talk to message author when reacted to.
    Does NOT commit — caller is responsible for committing."""
    if not message.user_id or message.user_id == reactor_user_id:
        return
    thread = message.thread
    member = GroupMember.query.filter_by(
        group_id=thread.group_id, user_id=message.user_id
    ).first()
    if member:
        member.trash_talk_score = (member.trash_talk_score or 0) + 1


def apply_redemption_win(thread):
    """Target's team came back — flip the script on scoring."""
    group_id = thread.group_id
    target_user_id = thread.target_user_id

    target_member = GroupMember.query.filter_by(
        group_id=group_id, user_id=target_user_id
    ).first()
    if target_member:
        target_member.bragging_rights_score = (target_member.bragging_rights_score or 0) + 25

    attacker_ids = db.session.query(GameThreadMessage.user_id).filter(
        GameThreadMessage.thread_id == thread.id,
        GameThreadMessage.message_type == "user",
        GameThreadMessage.user_id != target_user_id
    ).distinct().all()

    for (uid,) in attacker_ids:
        member = GroupMember.query.filter_by(group_id=group_id, user_id=uid).first()
        if member:
            member.shame_score = (member.shame_score or 0) + 10

    db.session.commit()


def compute_leaderboards(group_id):
    from sqlalchemy.orm import joinedload
    # Single query — joins users instead of N individual lookups
    members = (
        GroupMember.query
        .options(joinedload(GroupMember.user))
        .filter_by(group_id=group_id)
        .all()
    )
    if not members:
        return {}

    enriched = []
    for m in members:
        enriched.append({
            "member": m,
            "user": m.user,
            "shame": m.shame_score or 0,
            "trash_talk": m.trash_talk_score or 0,
            "bragging": m.bragging_rights_score or 0,
            "defense": m.defense_score or 0,
            "reporter": m.reporter_score or 0,
        })

    return {
        "biggest_loser": sorted(enriched, key=lambda x: x["shame"], reverse=True)[:3],
        "best_hater": sorted(enriched, key=lambda x: x["trash_talk"], reverse=True)[:3],
        "top_informant": sorted(enriched, key=lambda x: x["reporter"], reverse=True)[:3],
        "most_delusional": sorted(
            enriched, key=lambda x: x["shame"] + x["defense"], reverse=True
        )[:3],
        "bragging_champ": sorted(enriched, key=lambda x: x["bragging"], reverse=True)[:3],
    }
