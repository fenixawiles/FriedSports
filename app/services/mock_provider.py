from app.models import db, Game
from app.services.sports_provider import SportsDataProvider
from datetime import datetime, timezone


class MockSportsProvider(SportsDataProvider):
    def get_live_games(self, league):
        return Game.query.filter_by(league=league, status="live").all()

    def get_game_details(self, external_game_id):
        return Game.query.filter_by(external_game_id=external_game_id).first()

    def simulate_tick(self, game):
        """Advance a mock game one step and update lead tracking."""
        if game.status == "final":
            return

        # Advance the game state based on scenario
        scenario = game.external_game_id

        if scenario == "mock-lakers-spurs":
            # Lakers crushing Spurs — escalate in Q3 → Q4 → final
            if game.period == 3 and game.home_score < 125:
                game.home_score += 8
                game.away_score += 2
                game.clock = "5:00"
            elif game.period == 3:
                game.period = 4
                game.clock = "12:00"
            elif game.period == 4 and game.home_score < 140:
                game.home_score += 6
                game.away_score += 3
                game.clock = "3:00"
            else:
                game.status = "final"
                game.clock = "Final"

        elif scenario == "mock-eagles-cowboys":
            # Eagles blew up Cowboys who had a lead — Q3 chaos
            if game.period == 3 and game.away_score < 35:
                game.away_score += 7
                game.home_score += 0
                game.clock = "4:00"
            elif game.period == 3:
                game.period = 4
                game.clock = "15:00"
            elif game.period == 4 and game.away_score < 42:
                game.away_score += 7
                game.home_score += 3
                game.clock = "2:00"
            else:
                game.status = "final"
                game.clock = "Final"

        elif scenario == "mock-celtics-nets":
            # Celtics blowout already final
            game.status = "final"
            game.clock = "Final"

        elif scenario == "mock-nuggets-lakers":
            # Lakers had big lead, Nuggets mounting comeback
            if game.period == 4 and game.away_score < 105:
                game.away_score += 6
                game.home_score += 2
                game.clock = "4:00"
            elif game.period == 4:
                game.status = "final"
                game.clock = "Final"
            else:
                game.period = 4
                game.clock = "12:00"

        # Update max leads
        current_home_lead = game.home_score - game.away_score
        current_away_lead = game.away_score - game.home_score

        if current_home_lead > game.max_home_lead:
            game.max_home_lead = current_home_lead
        if current_away_lead > game.max_away_lead:
            game.max_away_lead = current_away_lead

        game.last_checked_at = datetime.now(timezone.utc)
        db.session.commit()
