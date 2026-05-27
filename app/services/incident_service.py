from app.models import db, GameEvent, GroupTrigger, GameThread, GameThreadMessage
from app.services.trash_templates import pick_template
from app.services.scoring import apply_incident_shame, apply_reporter_points

INCIDENT_TYPE_LABELS = {
    "BLOWOUT_ALERT": "Blowout Alert",
    "CHOKED_LEAD": "Choked Lead",
    "FRAUD_WATCH": "Fraud Watch",
    "FINAL_LOSS": "Final Loss",
    "PLAYOFF_COLLAPSE": "Playoff Collapse",
    "UPSET_ALERT": "Upset Alert",
    "DISASTER_QUARTER": "Disaster Quarter",
    "SHUTOUT_RISK": "Shutout Risk",
    "RIVAL_LOSS": "Rival Loss",
    "PREMATURE_SLANDER": "Premature Slander",
    "REDEMPTION_WIN": "Redemption Win",
}


def _make_thread_title(report):
    label = INCIDENT_TYPE_LABELS.get(
        report.incident_type,
        report.incident_type.replace("_", " ").title()
    )
    return f"Incident Report: {report.target_user.display_name} and the {report.target_team.name} — {label}"


def create_incident_thread(report):
    """
    Given a saved IncidentReport (already flushed/committed to DB),
    create: GameEvent → GroupTrigger → GameThread → system message → scoring.
    Returns the created GameThread.
    Does NOT call db.session.commit() — caller is responsible.
    """
    template_body = pick_template(
        report.incident_type,
        user=report.target_user.display_name,
        team=report.target_team.name,
        severity=report.severity,
        context=report.reported_score_text or "",
    )

    event = GameEvent(
        game_id=None,
        incident_report_id=report.id,
        trigger_type=report.incident_type,
        target_team_id=report.target_team_id,
        severity=report.severity,
        title=f"{INCIDENT_TYPE_LABELS.get(report.incident_type, report.incident_type)} — {report.target_team.abbreviation}",
        body=template_body,
    )
    db.session.add(event)
    db.session.flush()

    trigger = GroupTrigger(
        game_event_id=event.id,
        group_id=report.group_id,
        target_user_id=report.target_user_id,
    )
    db.session.add(trigger)
    db.session.flush()

    thread = GameThread(
        group_trigger_id=trigger.id,
        group_id=report.group_id,
        target_user_id=report.target_user_id,
        target_team_id=report.target_team_id,
        title=_make_thread_title(report),
        status="active",
    )
    db.session.add(thread)
    db.session.flush()

    msg = GameThreadMessage(
        thread_id=thread.id,
        user_id=None,
        message_type="system",
        body=template_body,
    )
    db.session.add(msg)

    apply_incident_shame(report.group_id, report.target_user_id, report.severity)
    apply_reporter_points(
        report.group_id,
        report.reporter_user_id,
        report.target_user_id,
        report.target_team_id,
    )

    # Send push notification to the target user (iOS app)
    try:
        from app.services.push_service import send_push
        send_push(
            user_id=report.target_user_id,
            title="🚨 Incident Report Filed",
            body=f"{report.reporter.shown_name} filed a report against your {report.target_team.name}.",
            data={"thread_id": thread.id, "group_id": report.group_id},
        )
    except Exception:
        pass  # Never let push failures block thread creation

    return thread
