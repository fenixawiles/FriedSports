"""add plain chat thread support

Revision ID: b6e4f9a2c8d1
Revises: 6b4f31d2a9c0
Create Date: 2026-06-21

Plain group/direct chats reuse game_threads, but they are not incident/report
threads. Existing rows backfill as thread_type='incident'.
"""
from alembic import op
import sqlalchemy as sa


revision = "b6e4f9a2c8d1"
down_revision = "6b4f31d2a9c0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("game_threads", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "thread_type",
                sa.String(length=24),
                nullable=False,
                server_default="incident",
            )
        )
        batch_op.add_column(sa.Column("created_by_user_id", sa.Integer(), nullable=True))
        batch_op.alter_column("group_trigger_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("group_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("target_user_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("target_team_id", existing_type=sa.Integer(), nullable=True)
        batch_op.create_foreign_key(
            "fk_game_threads_created_by_user_id_users",
            "users",
            ["created_by_user_id"],
            ["id"],
        )
        batch_op.create_index("ix_game_threads_thread_type", ["thread_type"])
        batch_op.create_index("ix_game_threads_created_by_user_id", ["created_by_user_id"])


def downgrade():
    with op.batch_alter_table("game_threads", schema=None) as batch_op:
        batch_op.drop_index("ix_game_threads_created_by_user_id")
        batch_op.drop_index("ix_game_threads_thread_type")
        batch_op.drop_constraint("fk_game_threads_created_by_user_id_users", type_="foreignkey")
        batch_op.alter_column("target_team_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("target_user_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("group_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("group_trigger_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("created_by_user_id")
        batch_op.drop_column("thread_type")
