"""
Sports Analytics Lab — data models.

Table names use `lab_` prefix to cleanly separate from the social domain.
Analytics games reference existing `teams` rows (teams.id) — no team duplication.
"""

import json
from datetime import datetime, timezone, date
from app.models import db


def now_utc():
    return datetime.now(timezone.utc)


# ── Leagues ─────────────────────────────────────────────────────────────────

class LabLeague(db.Model):
    __tablename__ = "lab_leagues"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)        # "National Basketball Association"
    abbreviation = db.Column(db.String(8), nullable=False, unique=True)  # "NBA"
    sport_type = db.Column(db.String(32), nullable=False)  # "basketball", "football"
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    seasons = db.relationship("LabSeason", backref="league", lazy="dynamic")
    games = db.relationship("LabGame", backref="league", lazy="dynamic")

    def __repr__(self):
        return f"<LabLeague {self.abbreviation}>"


# ── Seasons ──────────────────────────────────────────────────────────────────

class LabSeason(db.Model):
    __tablename__ = "lab_seasons"

    id = db.Column(db.Integer, primary_key=True)
    league_id = db.Column(db.Integer, db.ForeignKey("lab_leagues.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)           # 2024
    season_type = db.Column(db.String(16), nullable=False, default="regular")  # regular, playoffs, preseason
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    __table_args__ = (
        db.UniqueConstraint("league_id", "year", "season_type", name="uq_league_season"),
    )

    games = db.relationship("LabGame", backref="season", lazy="dynamic")

    def label(self):
        return f"{self.year} {self.season_type.title()}"

    def __repr__(self):
        return f"<LabSeason {self.year} {self.season_type}>"


# ── Players ───────────────────────────────────────────────────────────────────

class LabPlayer(db.Model):
    __tablename__ = "lab_players"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    position = db.Column(db.String(32))                    # PG, SG, SF, PF, C, QB, WR, etc.
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    team = db.relationship("Team")
    game_stats = db.relationship("PlayerGameStats", backref="player", lazy="dynamic")

    def __repr__(self):
        return f"<LabPlayer {self.name}>"


# ── Games ────────────────────────────────────────────────────────────────────

class LabGame(db.Model):
    __tablename__ = "lab_games"

    id = db.Column(db.Integer, primary_key=True)
    league_id = db.Column(db.Integer, db.ForeignKey("lab_leagues.id"), nullable=False)
    season_id = db.Column(db.Integer, db.ForeignKey("lab_seasons.id"), nullable=True)
    date = db.Column(db.Date, nullable=False)
    home_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    away_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    home_score = db.Column(db.Integer, nullable=False, default=0)
    away_score = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(16), nullable=False, default="final")  # final, scheduled
    attendance = db.Column(db.Integer, nullable=True)
    venue = db.Column(db.String(128), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    home_team = db.relationship("Team", foreign_keys=[home_team_id])
    away_team = db.relationship("Team", foreign_keys=[away_team_id])
    team_stats = db.relationship("TeamGameStats", backref="game", lazy="dynamic",
                                 cascade="all, delete-orphan")
    player_stats = db.relationship("PlayerGameStats", backref="game", lazy="dynamic",
                                   cascade="all, delete-orphan")
    derived_metrics = db.relationship("DerivedGameMetrics", backref="game", lazy="dynamic",
                                      cascade="all, delete-orphan")

    @property
    def winner_id(self):
        if self.home_score > self.away_score:
            return self.home_team_id
        elif self.away_score > self.home_score:
            return self.away_team_id
        return None

    @property
    def margin(self):
        return abs(self.home_score - self.away_score)

    def has_full_stats(self):
        """True if both home and away TeamGameStats rows exist."""
        return self.team_stats.count() == 2

    def has_derived_metrics(self):
        return self.derived_metrics.count() == 2

    def __repr__(self):
        return f"<LabGame {self.date} {self.away_team_id}@{self.home_team_id}>"


# ── Team Game Stats ──────────────────────────────────────────────────────────

class TeamGameStats(db.Model):
    __tablename__ = "lab_team_game_stats"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("lab_games.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    opponent_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    is_home = db.Column(db.Boolean, nullable=False, default=False)

    points = db.Column(db.Integer, nullable=False, default=0)

    fgm = db.Column(db.Integer, default=0)
    fga = db.Column(db.Integer, default=0)
    fg_pct = db.Column(db.Float, default=0.0)

    three_pm = db.Column(db.Integer, default=0)
    three_pa = db.Column(db.Integer, default=0)
    three_pct = db.Column(db.Float, default=0.0)

    ftm = db.Column(db.Integer, default=0)
    fta = db.Column(db.Integer, default=0)
    ft_pct = db.Column(db.Float, default=0.0)

    off_rebounds = db.Column(db.Integer, default=0)
    def_rebounds = db.Column(db.Integer, default=0)
    total_rebounds = db.Column(db.Integer, default=0)

    assists = db.Column(db.Integer, default=0)
    steals = db.Column(db.Integer, default=0)
    blocks = db.Column(db.Integer, default=0)
    turnovers = db.Column(db.Integer, default=0)
    fouls = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    __table_args__ = (
        db.UniqueConstraint("game_id", "team_id", name="uq_game_team_stats"),
    )

    team = db.relationship("Team", foreign_keys=[team_id])
    opponent = db.relationship("Team", foreign_keys=[opponent_id])

    def compute_percentages(self):
        """Update fg_pct, three_pct, ft_pct from makes/attempts."""
        self.fg_pct = round(self.fgm / self.fga, 4) if self.fga else 0.0
        self.three_pct = round(self.three_pm / self.three_pa, 4) if self.three_pa else 0.0
        self.ft_pct = round(self.ftm / self.fta, 4) if self.fta else 0.0
        self.total_rebounds = (self.off_rebounds or 0) + (self.def_rebounds or 0)

    def __repr__(self):
        return f"<TeamGameStats game={self.game_id} team={self.team_id}>"


# ── Player Game Stats ────────────────────────────────────────────────────────

class PlayerGameStats(db.Model):
    __tablename__ = "lab_player_game_stats"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("lab_games.id"), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey("lab_players.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)

    minutes = db.Column(db.Integer, nullable=True)
    points = db.Column(db.Integer, default=0)
    rebounds = db.Column(db.Integer, default=0)
    assists = db.Column(db.Integer, default=0)
    steals = db.Column(db.Integer, default=0)
    blocks = db.Column(db.Integer, default=0)
    turnovers = db.Column(db.Integer, default=0)
    fgm = db.Column(db.Integer, default=0)
    fga = db.Column(db.Integer, default=0)
    fg_pct = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    team = db.relationship("Team")

    def compute_fg_pct(self):
        self.fg_pct = round(self.fgm / self.fga, 4) if self.fga else 0.0

    def __repr__(self):
        return f"<PlayerGameStats game={self.game_id} player={self.player_id}>"


# ── Derived Game Metrics ─────────────────────────────────────────────────────

class DerivedGameMetrics(db.Model):
    """
    Computed from TeamGameStats. One row per (game, team).
    Values are signed from the perspective of `team_id`:
      positive = team advantage, negative = opponent advantage.
    """
    __tablename__ = "lab_derived_metrics"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("lab_games.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)

    win = db.Column(db.Boolean)
    point_margin = db.Column(db.Integer)         # team pts - opp pts (signed)

    trb_diff = db.Column(db.Integer)             # team TRB - opp TRB
    orb_diff = db.Column(db.Integer)
    drb_diff = db.Column(db.Integer)

    fg_pct_diff = db.Column(db.Float)            # team fg% - opp fg%
    three_pct_diff = db.Column(db.Float)
    ft_pct_diff = db.Column(db.Float)

    turnover_diff = db.Column(db.Integer)        # team TOV - opp TOV (negative = better)
    fta_diff = db.Column(db.Integer)             # team FTA - opp FTA

    # (FGA + 0.44*FTA + TOV) diff — proxy for possession advantage
    possession_proxy_diff = db.Column(db.Float)

    computed_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    __table_args__ = (
        db.UniqueConstraint("game_id", "team_id", name="uq_derived_game_team"),
    )

    team = db.relationship("Team")

    def __repr__(self):
        return f"<DerivedGameMetrics game={self.game_id} team={self.team_id} win={self.win}>"


# ── Metric Definitions ───────────────────────────────────────────────────────

class MetricDefinition(db.Model):
    """
    Extensible registry for custom analytics experiments.
    parameters field stores a JSON blob of config (weights, thresholds, etc.).
    """
    __tablename__ = "lab_metric_definitions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)         # "Rebound Compensation Index"
    slug = db.Column(db.String(64), unique=True, nullable=False)  # "rebound_compensation_index"
    description = db.Column(db.Text)
    formula_type = db.Column(db.String(16), nullable=False, default="python")  # python, sql, composite
    parameters = db.Column(db.Text)                          # JSON blob
    output_entity = db.Column(db.String(32), nullable=False, default="game_team")  # game_team, game_player, season_team
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    def get_parameters(self):
        """Deserialize parameters JSON."""
        if self.parameters:
            return json.loads(self.parameters)
        return {}

    def set_parameters(self, params: dict):
        self.parameters = json.dumps(params)

    def __repr__(self):
        return f"<MetricDefinition {self.slug}>"
