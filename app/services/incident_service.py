import threading
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
    return f"{label} — {report.target_user.display_name}'s {report.target_team.name}"


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

    # Fire push + email notifications in background — never block thread creation
    try:
        from flask import current_app

        _app = current_app._get_current_object()
        _report_id = report.id
        _thread_id = thread.id

        def _notify_background(app, report_id, thread_id):
            with app.app_context():
                try:
                    from app.models import db as _db, IncidentReport, Notification
                    r = _db.session.get(IncidentReport, report_id)
                    if not r:
                        return
                    # Push notification (iOS)
                    try:
                        from app.services.push_service import send_push
                        send_push(
                            user_id=r.target_user_id,
                            title="🚨 Thread Started",
                            body=f"{r.reporter.shown_name} started a thread on your {r.target_team.name}.",
                            data={"thread_id": thread_id, "group_id": r.group_id},
                        )
                    except Exception as e:
                        app.logger.warning(f"Push notification failed: {e}")
                    # Email notification with magic-link CTA
                    try:
                        from app.services.email_service import send_thread_notification
                        send_thread_notification(
                            target_user=r.target_user,
                            reporter=r.reporter,
                            team=r.target_team,
                            incident_type=r.incident_type,
                            group=r.group,
                            thread_id=thread_id,
                            description=r.description,
                        )
                        # Commit magic link token created inside send_thread_notification
                        _db.session.commit()
                    except Exception as e:
                        app.logger.warning(f"Thread notification email failed: {e}")
                    # In-app notification + 10-unread email trigger
                    try:
                        notif = Notification(
                            user_id=r.target_user_id,
                            type="thread_started",
                            message=f"{r.reporter.shown_name} started a thread about your {r.target_team.name}",
                            link_url=f"/threads/{thread_id}",
                        )
                        _db.session.add(notif)
                        _db.session.flush()
                        unread = Notification.query.filter_by(
                            user_id=r.target_user_id, is_read=False
                        ).count()
                        if unread == 10:
                            from app.services.email_service import send_missed_notifications_email
                            send_missed_notifications_email(r.target_user, unread)
                        _db.session.commit()
                    except Exception as e:
                        app.logger.warning(f"Notification creation failed: {e}")
                except Exception as e:
                    app.logger.warning(f"Notification background task failed: {e}")

        threading.Thread(
            target=_notify_background,
            args=(_app, _report_id, _thread_id),
            daemon=True,
        ).start()
    except Exception:
        pass  # Never let notification failures block thread creation

    return thread
