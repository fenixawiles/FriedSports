"""app review schema sync

Revision ID: 6b4f31d2a9c0
Revises: f3a1c9d2b5e7
Create Date: 2026-06-20 18:00:00.000000

Additive schema sync for columns/tables that existed in models before their
matching migration was added. The checks keep this migration safe for databases
that were partially repaired manually while still making fresh installs match
the app metadata.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6b4f31d2a9c0"
down_revision = "f3a1c9d2b5e7"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name):
    return _inspector().has_table(table_name)


def _has_column(table_name, column_name):
    if not _has_table(table_name):
        return False
    return column_name in {col["name"] for col in _inspector().get_columns(table_name)}


def _column_nullable(table_name, column_name):
    if not _has_table(table_name):
        return None
    for col in _inspector().get_columns(table_name):
        if col["name"] == column_name:
            return col["nullable"]
    return None


def upgrade():
    if _has_table("users") and not _has_column("users", "role"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "role",
                    sa.String(length=16),
                    nullable=False,
                    server_default="user",
                )
            )

    if _has_table("group_members") and not _has_column("group_members", "reporter_score"):
        with op.batch_alter_table("group_members", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("reporter_score", sa.Integer(), nullable=True, server_default="0")
            )

    if not _has_table("incident_reports"):
        op.create_table(
            "incident_reports",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("reporter_user_id", sa.Integer(), nullable=False),
            sa.Column("group_id", sa.Integer(), nullable=False),
            sa.Column("target_user_id", sa.Integer(), nullable=False),
            sa.Column("target_team_id", sa.Integer(), nullable=False),
            sa.Column("league", sa.String(length=8), nullable=False),
            sa.Column("incident_type", sa.String(length=32), nullable=False),
            sa.Column("severity", sa.Integer(), nullable=False),
            sa.Column("reported_score_text", sa.String(length=120), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
            sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["target_team_id"], ["teams.id"]),
            sa.ForeignKeyConstraint(["target_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("incident_reports", schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f("ix_incident_reports_reporter_user_id"),
                ["reporter_user_id"],
                unique=False,
            )

    if _has_column("game_events", "game_id") and _column_nullable("game_events", "game_id") is False:
        with op.batch_alter_table("game_events", schema=None) as batch_op:
            batch_op.alter_column(
                "game_id",
                existing_type=sa.Integer(),
                nullable=True,
            )

    if _has_table("game_events") and not _has_column("game_events", "incident_report_id"):
        with op.batch_alter_table("game_events", schema=None) as batch_op:
            batch_op.add_column(sa.Column("incident_report_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_game_events_incident_report_id_incident_reports",
                "incident_reports",
                ["incident_report_id"],
                ["id"],
            )

    if not _has_table("lab_leagues"):
        op.create_table(
            "lab_leagues",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("abbreviation", sa.String(length=8), nullable=False),
            sa.Column("sport_type", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("abbreviation"),
        )

    if not _has_table("lab_seasons"):
        op.create_table(
            "lab_seasons",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("league_id", sa.Integer(), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("season_type", sa.String(length=16), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["league_id"], ["lab_leagues.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("league_id", "year", "season_type", name="uq_league_season"),
        )

    if not _has_table("lab_players"):
        op.create_table(
            "lab_players",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("position", sa.String(length=32), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table("lab_games"):
        op.create_table(
            "lab_games",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("league_id", sa.Integer(), nullable=False),
            sa.Column("season_id", sa.Integer(), nullable=True),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("home_team_id", sa.Integer(), nullable=False),
            sa.Column("away_team_id", sa.Integer(), nullable=False),
            sa.Column("home_score", sa.Integer(), nullable=False),
            sa.Column("away_score", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("attendance", sa.Integer(), nullable=True),
            sa.Column("venue", sa.String(length=128), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["away_team_id"], ["teams.id"]),
            sa.ForeignKeyConstraint(["home_team_id"], ["teams.id"]),
            sa.ForeignKeyConstraint(["league_id"], ["lab_leagues.id"]),
            sa.ForeignKeyConstraint(["season_id"], ["lab_seasons.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table("lab_team_game_stats"):
        op.create_table(
            "lab_team_game_stats",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("game_id", sa.Integer(), nullable=False),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("opponent_id", sa.Integer(), nullable=False),
            sa.Column("is_home", sa.Boolean(), nullable=False),
            sa.Column("points", sa.Integer(), nullable=False),
            sa.Column("fgm", sa.Integer(), nullable=True),
            sa.Column("fga", sa.Integer(), nullable=True),
            sa.Column("fg_pct", sa.Float(), nullable=True),
            sa.Column("three_pm", sa.Integer(), nullable=True),
            sa.Column("three_pa", sa.Integer(), nullable=True),
            sa.Column("three_pct", sa.Float(), nullable=True),
            sa.Column("ftm", sa.Integer(), nullable=True),
            sa.Column("fta", sa.Integer(), nullable=True),
            sa.Column("ft_pct", sa.Float(), nullable=True),
            sa.Column("off_rebounds", sa.Integer(), nullable=True),
            sa.Column("def_rebounds", sa.Integer(), nullable=True),
            sa.Column("total_rebounds", sa.Integer(), nullable=True),
            sa.Column("assists", sa.Integer(), nullable=True),
            sa.Column("steals", sa.Integer(), nullable=True),
            sa.Column("blocks", sa.Integer(), nullable=True),
            sa.Column("turnovers", sa.Integer(), nullable=True),
            sa.Column("fouls", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["game_id"], ["lab_games.id"]),
            sa.ForeignKeyConstraint(["opponent_id"], ["teams.id"]),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("game_id", "team_id", name="uq_game_team_stats"),
        )

    if not _has_table("lab_player_game_stats"):
        op.create_table(
            "lab_player_game_stats",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("game_id", sa.Integer(), nullable=False),
            sa.Column("player_id", sa.Integer(), nullable=False),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("minutes", sa.Integer(), nullable=True),
            sa.Column("points", sa.Integer(), nullable=True),
            sa.Column("rebounds", sa.Integer(), nullable=True),
            sa.Column("assists", sa.Integer(), nullable=True),
            sa.Column("steals", sa.Integer(), nullable=True),
            sa.Column("blocks", sa.Integer(), nullable=True),
            sa.Column("turnovers", sa.Integer(), nullable=True),
            sa.Column("fgm", sa.Integer(), nullable=True),
            sa.Column("fga", sa.Integer(), nullable=True),
            sa.Column("fg_pct", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["game_id"], ["lab_games.id"]),
            sa.ForeignKeyConstraint(["player_id"], ["lab_players.id"]),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table("lab_derived_metrics"):
        op.create_table(
            "lab_derived_metrics",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("game_id", sa.Integer(), nullable=False),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("win", sa.Boolean(), nullable=True),
            sa.Column("point_margin", sa.Integer(), nullable=True),
            sa.Column("trb_diff", sa.Integer(), nullable=True),
            sa.Column("orb_diff", sa.Integer(), nullable=True),
            sa.Column("drb_diff", sa.Integer(), nullable=True),
            sa.Column("fg_pct_diff", sa.Float(), nullable=True),
            sa.Column("three_pct_diff", sa.Float(), nullable=True),
            sa.Column("ft_pct_diff", sa.Float(), nullable=True),
            sa.Column("turnover_diff", sa.Integer(), nullable=True),
            sa.Column("fta_diff", sa.Integer(), nullable=True),
            sa.Column("possession_proxy_diff", sa.Float(), nullable=True),
            sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["game_id"], ["lab_games.id"]),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("game_id", "team_id", name="uq_derived_game_team"),
        )

    if not _has_table("lab_metric_definitions"):
        op.create_table(
            "lab_metric_definitions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("slug", sa.String(length=64), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("formula_type", sa.String(length=16), nullable=False),
            sa.Column("parameters", sa.Text(), nullable=True),
            sa.Column("output_entity", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug"),
        )


def downgrade():
    for table_name in (
        "lab_metric_definitions",
        "lab_derived_metrics",
        "lab_player_game_stats",
        "lab_team_game_stats",
        "lab_games",
        "lab_players",
        "lab_seasons",
        "lab_leagues",
    ):
        if _has_table(table_name):
            op.drop_table(table_name)

    if _has_table("game_events") and _has_column("game_events", "incident_report_id"):
        with op.batch_alter_table("game_events", schema=None) as batch_op:
            batch_op.drop_constraint(
                "fk_game_events_incident_report_id_incident_reports",
                type_="foreignkey",
            )
            batch_op.drop_column("incident_report_id")

    if _has_table("incident_reports"):
        with op.batch_alter_table("incident_reports", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_incident_reports_reporter_user_id"))
        op.drop_table("incident_reports")

    if _has_table("group_members") and _has_column("group_members", "reporter_score"):
        with op.batch_alter_table("group_members", schema=None) as batch_op:
            batch_op.drop_column("reporter_score")

    if _has_table("users") and _has_column("users", "role"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("role")
