"""Preserve legacy marketplace uniqueness using the model's unique indexes."""
from alembic import op
revision = '20261024_unique_indexes'
down_revision = '20261010_marketplace'
branch_labels = None
depends_on = None
TABLES = [('products', 'sku', 'uq_products_sku'), ('marketplace_orders', 'order_number', 'uq_marketplace_orders_number')]

def upgrade():
    for table, column, constraint in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(constraint, type_='unique')
            batch.drop_index(f'ix_{table}_{column}')
            batch.create_index(f'ix_{table}_{column}', [column], unique=True)

def downgrade():
    for table, column, constraint in reversed(TABLES):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f'ix_{table}_{column}')
            batch.create_unique_constraint(constraint, [column])
            batch.create_index(f'ix_{table}_{column}', [column], unique=False)
