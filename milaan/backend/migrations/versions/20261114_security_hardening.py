"""Security hardening: long-lived credit ledger and decision log, optional TOTP,
and removal of the unused marketplace tables."""
from alembic import op
import sqlalchemy as sa

revision = '20261114_security_hardening'
down_revision = '20261025_receipt_deletions'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('credit_ledger',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('credit_key', sa.String(64), nullable=False),
        sa.Column('account_id', sa.String(100), nullable=False),
        sa.Column('credit_amount_paisa', sa.BigInteger(), nullable=False),
        sa.Column('amount_paisa', sa.BigInteger(), nullable=False),
        sa.Column('order_ref', sa.String(100), nullable=False),
        sa.Column('transaction_id', sa.String(150), nullable=False, server_default=''),
        sa.Column('batch_name', sa.String(150), nullable=False, server_default=''),
        sa.Column('used_at', sa.DateTime(), nullable=False),
        sa.Column('retain_until', sa.DateTime(), nullable=False),
        sa.CheckConstraint('amount_paisa > 0', name='ck_credit_ledger_positive'))
    op.create_index('ix_credit_ledger_owner_id', 'credit_ledger', ['owner_id'])
    op.create_index('ix_credit_ledger_credit_key', 'credit_ledger', ['credit_key'])
    op.create_index('ix_credit_ledger_retain_until', 'credit_ledger', ['retain_until'])
    op.create_table('decision_log',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('batch_name', sa.String(150), nullable=False, server_default=''),
        sa.Column('order_ref', sa.String(100), nullable=False),
        sa.Column('amount_paisa', sa.BigInteger(), nullable=False),
        sa.Column('decision', sa.String(10), nullable=False),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False, server_default=''),
        sa.Column('transaction_id', sa.String(150), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('retain_until', sa.DateTime(), nullable=False))
    op.create_index('ix_decision_log_owner_id', 'decision_log', ['owner_id'])
    op.create_index('ix_decision_log_created_at', 'decision_log', ['created_at'])
    op.create_index('ix_decision_log_retain_until', 'decision_log', ['retain_until'])
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('totp_secret', sa.String(64), nullable=True))
        batch.add_column(sa.Column('totp_enabled_at', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('totp_last_step', sa.BigInteger(), nullable=True))
    # The marketplace experiment never had endpoints; its tables only widened the schema.
    for table in ('marketplace_order_items', 'marketplace_orders', 'cart_items', 'products'):
        if sa.inspect(op.get_bind()).has_table(table):
            op.drop_table(table)


def downgrade():
    with op.batch_alter_table('users') as batch:
        batch.drop_column('totp_last_step')
        batch.drop_column('totp_enabled_at')
        batch.drop_column('totp_secret')
    op.drop_table('decision_log')
    op.drop_table('credit_ledger')
