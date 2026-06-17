"""add reply_to_id to game_thread_messages

Revision ID: c4f8a1b2d3e4
Revises: 9b2c4d6e8f10
Create Date: 2026-06-16

Adds an optional self-reference so a message can quote-reply another. Plain
nullable Integer (no DB-level FK constraint) so the ADD COLUMN is trivial and
safe on both SQLite (dev) and Postgres (prod). The ORM relationship in
models.py carries the foreign-key hint for joins.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c4f8a1b2d3e4"
down_revision = "9b2c4d6e8f10"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "game_thread_messages",
        sa.Column("reply_to_id", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column("game_thread_messages", "reply_to_id")
