"""moderation + blocking + EULA: blocked_users, message_report lifecycle, agreed_to_terms_at

Revision ID: 9b2c4d6e8f10
Revises: 741e8374db51
Create Date: 2026-06-13 13:45:00.000000

Additive-only migration (App Store UGC compliance):
  - new table blocked_users
  - new nullable / server-defaulted columns on message_reports (moderation lifecycle)
  - new nullable column users.agreed_to_terms_at

No data is dropped or rewritten; safe to run against existing production rows.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9b2c4d6e8f10'
down_revision = '741e8374db51'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'blocked_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('blocker_id', sa.Integer(), nullable=False),
        sa.Column('blocked_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['blocker_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['blocked_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('blocker_id', 'blocked_id', name='uq_blocked_user'),
    )
    with op.batch_alter_table('blocked_users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_blocked_users_blocker_id'), ['blocker_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_blocked_users_blocked_id'), ['blocked_id'], unique=False)

    with op.batch_alter_table('message_reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=16),
                                      server_default='open', nullable=False))
        batch_op.add_column(sa.Column('resolution', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('reviewed_by_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key('fk_message_reports_reviewed_by',
                                    'users', ['reviewed_by_id'], ['id'])

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('agreed_to_terms_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('agreed_to_terms_at')

    with op.batch_alter_table('message_reports', schema=None) as batch_op:
        batch_op.drop_constraint('fk_message_reports_reviewed_by', type_='foreignkey')
        batch_op.drop_column('reviewed_at')
        batch_op.drop_column('reviewed_by_id')
        batch_op.drop_column('resolution')
        batch_op.drop_column('status')
        batch_op.drop_column('category')

    with op.batch_alter_table('blocked_users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_blocked_users_blocked_id'))
        batch_op.drop_index(batch_op.f('ix_blocked_users_blocker_id'))
    op.drop_table('blocked_users')
