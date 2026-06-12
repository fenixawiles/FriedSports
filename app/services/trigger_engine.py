from datetime import datetime, timedelta, timezone
from app.models import (
    db, Game, GameEvent, GroupTrigger, GameThread, GameThreadMessage,
    GroupMember, UserFavoriteTeam, Group
)
from app.services.trash_templates import pick_template
from app.services.scoring import apply_trigger_shame

COOLDOWN_MINUTES = 15


def _recent_event(game_id, trigger_type, team_id):
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=COOLDOWN_MINUTES)
    return GameEvent.query.filter(
        GameEvent.game_id == game_id,
        GameEvent.trigger_type == trigger_type,
        GameEvent.target_team_id == team_id,
        GameEvent.created_at >= cutoff,
    ).order_by(GameEvent.created_at.desc()).first()


def _detect_nba_triggers(game):
    triggers = []
    home_id = game.home_team_id
    away_id = game.away_team_id
    margin = game.home_score - game.away_score

    losing_id = game.losing_team_id()
    losing_margin = abs(margin) if losing_id else 0

    if losing_id:
        if losing_margin >= 30:
            triggers.append((losing_id, "BLOWOUT_ALERT", 4, losing_margin))
        elif losing_margin >= 25:
            triggers.append((losing_id, "BLOWOUT_ALERT", 3, losing_margin))
        elif losing_margin >= 15 and game.period >= 2:
            triggers.append((losing_id, "BLOWOUT_ALERT", 2, losing_margin))

    # Choked lead — team now losing but had a big lead
    if margin < 0 and game.max_home_lead >= 15:
        triggers.append((home_id, "CHOKED_LEAD", 3, game.max_home_lead))
    if margin > 0 and game.max_away_lead >= 15:
        triggers.append((away_id, "CHOKED_LEAD", 3, game.max_away_lead))

    # Final-game checks
    if game.status == "final":
        if losing_id:
            triggers.append((losing_id, "FINAL_LOSS", 3, losing_margin))
        # Playoff collapse: led by 10+ in Q4 but lost
        if margin < 0 and game.max_home_lead >= 10 and game.period >= 4:
            triggers.append((home_id, "PLAYOFF_COLLAPSE", 4, game.max_home_lead))
        if margin > 0 and game.max_away_lead >= 10 and game.period >= 4:
            triggers.append((away_id, "PLAYOFF_COLLAPSE", 4, game.max_away_lead))

    return triggers


def _detect_nfl_triggers(game):
    triggers = []
    margin = game.home_score - game.away_score
    losing_id = game.losing_team_id()
    losing_margin = abs(margin) if losing_id else 0

    if losing_id:
        if losing_margin >= 21:
            triggers.append((losing_id, "BLOWOUT_ALERT", 3, losing_margin))
        elif losing_margin >= 14 and game.period >= 3:
            triggers.append((losing_id, "BLOWOUT_ALERT", 2, losing_margin))

    # Scoreless at halftime
    if game.period == 3 and game.home_score == 0:
        triggers.append((game.home_team_id, "SHUTOUT_RISK", 3, 0))
    if game.period == 3 and game.away_score == 0:
        triggers.append((game.away_team_id, "SHUTOUT_RISK", 3, 0))

    # Choked lead
    if margin < 0 and game.max_home_lead >= 14:
        triggers.append((game.home_team_id, "CHOKED_LEAD", 3, game.max_home_lead))
    if margin > 0 and game.max_away_lead >= 14:
        triggers.append((game.away_team_id, "CHOKED_LEAD", 3, game.max_away_lead))

    if game.status == "final":
        if losing_id:
            triggers.append((losing_id, "FINAL_LOSS", 3, losing_margin))

    return triggers


def process_game(game):
    """Detect triggers for a game and create events, group triggers, threads, and messages."""
    if game.league == "NBA":
        raw_triggers = _detect_nba_triggers(game)
    elif game.league == "NFL":
        raw_triggers = _detect_nfl_triggers(game)
    else:
        return

    for team_id, trigger_type, severity, margin in raw_triggers:
        # Cooldown check
        existing = _recent_event(game.id, trigger_type, team_id)
        if existing and existing.severity >= severity:
            continue

        team = db.session.get(__import__('app.models', fromlist=['Team']).Team, team_id)
        if not team:
            continue

        # Create GameEvent
        body = f"{trigger_type} | {team.name} | margin: {margin}"
        title = f"{team.name}: {trigger_type.replace('_', ' ').title()}"
        event = GameEvent(
            game_id=game.id,
            trigger_type=trigger_type,
            target_team_id=team_id,
            severity=severity,
            title=title,
            body=body,
        )
        db.session.add(event)
        db.session.flush()

        # Find all affected (group, user) pairs
        fan_pairs = db.session.query(
            UserFavoriteTeam.user_id,
            GroupMember.group_id
        ).join(
            GroupMember, GroupMember.user_id == UserFavoriteTeam.user_id
        ).filter(
            UserFavoriteTeam.team_id == team_id
        ).all()

        for user_id, group_id in fan_pairs:
            # No-duplicate check
            existing_trigger = GroupTrigger.query.filter_by(
                game_event_id=event.id,
                group_id=group_id,
                target_user_id=user_id,
            ).first()
            if existing_trigger:
                continue

            group_trigger = GroupTrigger(
                game_event_id=event.id,
                group_id=group_id,
                target_user_id=user_id,
            )
            db.session.add(group_trigger)
            db.session.flush()

            # Get user and team names for template
            from app.models import User
            user = db.session.get(User, user_id)
            if not user:
                continue

            template_msg = pick_template(
                trigger_type,
                user=user.display_name,
                team=team.name,
                margin=margin,
                lead=margin,
            )

            thread_title = f"{user.display_name}'s {team.name}: {trigger_type.replace('_', ' ').title()}"
            thread = GameThread(
                group_trigger_id=group_trigger.id,
                group_id=group_id,
                target_user_id=user_id,
                target_team_id=team_id,
                title=thread_title,
                status="active",
            )
            db.session.add(thread)
            db.session.flush()

            sys_msg = GameThreadMessage(
                thread_id=thread.id,
                user_id=None,
                message_type="system",
                body=template_msg,
            )
            db.session.add(sys_msg)

            from app.services.activity import record_event
            record_event(group_id, None, "thread_started", thread.id)

            # Award shame to the target user in this group
            apply_trigger_shame(group_id, user_id, trigger_type, margin)

    db.session.commit()
    print(f"[TriggerEngine] Processed {game.league} game {game.external_game_id}")
