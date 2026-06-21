"""add users.session_token (multi-device sign-out)

Revision ID: f3a1c9d2b5e7
Revises: d7e9b2c1a4f8
Create Date: 2026-06-20

Rotating per-account session secret. When set, every live session cookie must
carry the matching token; bumping it signs out all other devices. Nullable so
existing sessions stay valid after deploy (no forced mass logout).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f3a1c9d2b5e7"
down_revision = "d7e9b2c1a4f8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("session_token", sa.String(length=32), nullable=True))


def downgrade():
    op.drop_column("users", "session_token")
