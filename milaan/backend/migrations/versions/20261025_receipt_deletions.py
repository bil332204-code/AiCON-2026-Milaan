"""Durable receipt deletion retries; no changes to existing receipt references."""
from alembic import op
import sqlalchemy as sa
revision = '20261025_receipt_deletions'
down_revision = '20261025_verified_email'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('receipt_deletions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('object_key', sa.String(100), nullable=False),
        sa.Column('storage_identity', sa.String(64), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('storage_identity', 'object_key', name='uq_receipt_deletion_object'))
    op.create_index('ix_receipt_deletions_next_attempt_at', 'receipt_deletions', ['next_attempt_at'])


def downgrade():
    if op.get_bind().execute(sa.text('SELECT id FROM receipt_deletions LIMIT 1')).first():
        raise RuntimeError('Drain receipt deletions before downgrade; pending privacy erasures must not be lost')
    op.drop_table('receipt_deletions')
