"""Preserve existing whole allocations and enable explicitly reviewed payment shares."""
from alembic import op
import sqlalchemy as sa

revision = '20261024_payment_parts'
down_revision = '20261024_unique_indexes'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('allocations', sa.Column('amount_paisa', sa.BigInteger(), nullable=True))
    op.execute('UPDATE allocations SET amount_paisa = (SELECT amount_paisa FROM statement_lines WHERE statement_lines.id = allocations.statement_line_id)')
    constraints = sa.inspect(op.get_bind()).get_unique_constraints('allocations')
    convention = {'uq': 'uq_%(table_name)s_%(column_0_name)s'}
    with op.batch_alter_table('allocations', naming_convention=convention) as batch:
        for constraint in constraints:
            if constraint['column_names'] in [['match_id'], ['order_id'], ['claim_id'], ['credit_key']]:
                batch.drop_constraint(constraint['name'] or 'uq_allocations_'+constraint['column_names'][0], type_='unique')
        batch.alter_column('amount_paisa', existing_type=sa.BigInteger(), nullable=False)
        batch.create_unique_constraint('uq_allocation_match_credit', ['match_id', 'credit_key'])
        batch.create_check_constraint('ck_allocation_positive', 'amount_paisa > 0')
        batch.create_index('ix_allocations_credit_key', ['credit_key'])
    op.create_table('allocation_reviews',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('batch_id', sa.String(36), sa.ForeignKey('batches.id', ondelete='CASCADE'), nullable=False),
        sa.Column('idempotency_key', sa.String(100), nullable=False),
        sa.Column('request_digest', sa.String(64), nullable=False),
        sa.Column('response', sa.JSON(), nullable=False),
        sa.UniqueConstraint('batch_id', 'idempotency_key', name='uq_allocation_review_key'))
    op.create_index('ix_allocation_reviews_batch_id', 'allocation_reviews', ['batch_id'])


def downgrade():
    bind = op.get_bind()
    for column in ['match_id', 'order_id', 'claim_id', 'credit_key']:
        if bind.execute(sa.text(f'SELECT {column} FROM allocations GROUP BY {column} HAVING COUNT(*) > 1')).first():
            raise RuntimeError('Cannot downgrade reviewed split/shared allocations; export and explicitly release them first')
    if bind.execute(sa.text('SELECT a.id FROM allocations a JOIN statement_lines l ON a.statement_line_id=l.id WHERE a.amount_paisa != l.amount_paisa')).first():
        raise RuntimeError('Cannot downgrade partial allocations; export and explicitly release them first')
    op.drop_table('allocation_reviews')
    with op.batch_alter_table('allocations') as batch:
        batch.drop_constraint('uq_allocation_match_credit', type_='unique')
        batch.drop_constraint('ck_allocation_positive', type_='check')
        batch.drop_index('ix_allocations_credit_key')
        batch.drop_column('amount_paisa')
        for column in ['match_id', 'order_id', 'claim_id', 'credit_key']:
            batch.create_unique_constraint('uq_allocations_'+column, [column])
