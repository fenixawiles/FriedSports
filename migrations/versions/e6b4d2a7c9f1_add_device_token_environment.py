"""add APNs environment to device tokens

Revision ID: e6b4d2a7c9f1
Revises: c5d7f2a8e4b1
Create Date: 2026-07-04

Existing device tokens predate environment tracking. Default them to production
so TestFlight/App Store diagnostics continue to target the real beta lane.
"""
from alembic import op, context
import sqlalchemy as sa


revision = "e6b4d2a7c9f1"
down_revision = "c5d7f2a8e4b1"
branch_labels = None
depends_on = None


def _has_column(table, column):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in [c["name"] for c in insp.get_columns(table)]


def _has_index(table, index):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return index in [i["name"] for i in insp.get_indexes(table)]


def upgrade():
    if context.is_offline_mode():
        op.add_column(
            "device_tokens",
            sa.Column(
                "environment",
                sa.String(length=16),
                nullable=False,
                server_default="production",
            ),
        )
        op.create_index("ix_device_tokens_environment", "device_tokens", ["environment"], unique=False)
        return

    if not _has_column("device_tokens", "environment"):
        with op.batch_alter_table("device_tokens", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "environment",
                    sa.String(length=16),
                    nullable=False,
                    server_default="production",
                )
            )
    if not _has_index("device_tokens", "ix_device_tokens_environment"):
        with op.batch_alter_table("device_tokens", schema=None) as batch_op:
            batch_op.create_index("ix_device_tokens_environment", ["environment"], unique=False)


def downgrade():
    if context.is_offline_mode():
        op.drop_index("ix_device_tokens_environment", table_name="device_tokens")
        op.drop_column("device_tokens", "environment")
        return

    if _has_index("device_tokens", "ix_device_tokens_environment"):
        with op.batch_alter_table("device_tokens", schema=None) as batch_op:
            batch_op.drop_index("ix_device_tokens_environment")
    if _has_column("device_tokens", "environment"):
        with op.batch_alter_table("device_tokens", schema=None) as batch_op:
            batch_op.drop_column("environment")
