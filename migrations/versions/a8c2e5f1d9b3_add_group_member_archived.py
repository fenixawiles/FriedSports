"""add group_members.archived — per-user group archive (long-press action)

Revision ID: a8c2e5f1d9b3
Revises: b6e4f9a2c8d1
Create Date: 2026-07-03

Idempotent: guarded by a column-existence check so a re-run (or a deploy that
races the manual apply) is a no-op instead of an error.
"""
from alembic import op
import sqlalchemy as sa


revision = "a8c2e5f1d9b3"
down_revision = "b6e4f9a2c8d1"
branch_labels = None
depends_on = None


def _has_column(table, column):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in [c["name"] for c in insp.get_columns(table)]


def upgrade():
    if not _has_column("group_members", "archived"):
        with op.batch_alter_table("group_members", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "archived",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )


def downgrade():
    if _has_column("group_members", "archived"):
        with op.batch_alter_table("group_members", schema=None) as batch_op:
            batch_op.drop_column("archived")
