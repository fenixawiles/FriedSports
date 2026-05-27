"""
Derived Metrics Engine

Computes DerivedGameMetrics from TeamGameStats for LabGames.
All functions are idempotent — safe to re-run on existing data.
"""

from datetime import datetime, timezone
from app.models import db
from app.analytics.models import LabGame, TeamGameStats, DerivedGameMetrics


def compute_derived_for_game(game_id: int) -> list:
    """
    Given a LabGame with two TeamGameStats rows, compute DerivedGameMetrics
    for both teams. Returns list of DerivedGameMetrics (unsaved — caller commits).

    Raises ValueError if TeamGameStats are incomplete.
    """
    game = db.session.get(LabGame, game_id)
    if not game:
        raise ValueError(f"LabGame {game_id} not found")

    stats = game.team_stats.all()
    if len(stats) != 2:
        raise ValueError(
            f"LabGame {game_id} needs exactly 2 TeamGameStats rows, found {len(stats)}"
        )

    # Index stats by team_id for easy lookup
    by_team = {s.team_id: s for s in stats}
    team_ids = list(by_team.keys())
    results = []

    for tid in team_ids:
        opp_id = [x for x in team_ids if x != tid][0]
        t = by_team[tid]
        o = by_team[opp_id]

        win = t.points > o.points
        point_margin = t.points - o.points

        trb_diff = (t.total_rebounds or 0) - (o.total_rebounds or 0)
        orb_diff = (t.off_rebounds or 0) - (o.off_rebounds or 0)
        drb_diff = (t.def_rebounds or 0) - (o.def_rebounds or 0)

        fg_pct_diff = (t.fg_pct or 0.0) - (o.fg_pct or 0.0)
        three_pct_diff = (t.three_pct or 0.0) - (o.three_pct or 0.0)
        ft_pct_diff = (t.ft_pct or 0.0) - (o.ft_pct or 0.0)

        turnover_diff = (t.turnovers or 0) - (o.turnovers or 0)
        fta_diff = (t.fta or 0) - (o.fta or 0)

        # Possession proxy: FGA + 0.44*FTA + TOV
        t_poss = (t.fga or 0) + 0.44 * (t.fta or 0) + (t.turnovers or 0)
        o_poss = (o.fga or 0) + 0.44 * (o.fta or 0) + (o.turnovers or 0)
        possession_proxy_diff = round(t_poss - o_poss, 3)

        # Upsert — find existing row or create new
        existing = DerivedGameMetrics.query.filter_by(
            game_id=game_id, team_id=tid
        ).first()

        if existing:
            row = existing
        else:
            row = DerivedGameMetrics(game_id=game_id, team_id=tid)
            db.session.add(row)

        row.win = win
        row.point_margin = point_margin
        row.trb_diff = trb_diff
        row.orb_diff = orb_diff
        row.drb_diff = drb_diff
        row.fg_pct_diff = round(fg_pct_diff, 4)
        row.three_pct_diff = round(three_pct_diff, 4)
        row.ft_pct_diff = round(ft_pct_diff, 4)
        row.turnover_diff = turnover_diff
        row.fta_diff = fta_diff
        row.possession_proxy_diff = possession_proxy_diff
        row.computed_at = datetime.now(timezone.utc)

        results.append(row)

    return results


def compute_all_missing(league_id: int = None, season_id: int = None) -> int:
    """
    Batch compute derived metrics for all LabGames that have complete
    TeamGameStats but no DerivedGameMetrics rows.

    Returns count of games processed.
    """
    query = LabGame.query.filter_by(status="final")
    if league_id:
        query = query.filter_by(league_id=league_id)
    if season_id:
        query = query.filter_by(season_id=season_id)

    games = query.all()
    processed = 0

    for game in games:
        if not game.has_full_stats():
            continue
        if game.has_derived_metrics():
            continue
        try:
            compute_derived_for_game(game.id)
            db.session.commit()
            processed += 1
        except ValueError:
            db.session.rollback()

    return processed
