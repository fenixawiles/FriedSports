"""add thread_user_states (per-user archive + local delete)

Revision ID: d7e9b2c1a4f8
Revises: c4f8a1b2d3e4
Create Date: 2026-06-17

Per-user thread view state: archive + local delete with a `cleared_at`
watermark (messages at/before it are hidden from that user only). Nothing is
deleted from the shared message store.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d7e9b2c1a4f8"
down_revision = "c4f8a1b2d3e4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "thread_user_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["thread_id"], ["game_threads.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "thread_id", name="uq_thread_user_state"),
    )
    op.create_index("ix_thread_user_states_user_id", "thread_user_states", ["user_id"])
    op.create_index("ix_thread_user_states_thread_id", "thread_user_states", ["thread_id"])


def downgrade():
    op.drop_index("ix_thread_user_states_thread_id", table_name="thread_user_states")
    op.drop_index("ix_thread_user_states_user_id", table_name="thread_user_states")
    op.drop_table("thread_user_states")
