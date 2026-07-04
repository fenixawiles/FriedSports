"""add users.avatar_data — stored profile photo (real upload, not URL entry)

Revision ID: c5d7f2a8e4b1
Revises: a8c2e5f1d9b3
Create Date: 2026-07-04

TEXT column holding the resized JPEG as a data URL (~30-50KB after client-side
crop). Served via /api/users/<id>/avatar so list payloads stay small.
Idempotent: guarded by a column-existence check.
"""
from alembic import op
import sqlalchemy as sa


revision = "c5d7f2a8e4b1"
down_revision = "a8c2e5f1d9b3"
branch_labels = None
depends_on = None


def _has_column(table, column):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in [c["name"] for c in insp.get_columns(table)]


def upgrade():
    if not _has_column("users", "avatar_data"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(sa.Column("avatar_data", sa.Text(), nullable=True))


def downgrade():
    if _has_column("users", "avatar_data"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("avatar_data")
