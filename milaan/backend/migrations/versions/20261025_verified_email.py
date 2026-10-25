"""Keep legacy email verification unknown until the existing owner proves it."""
from alembic import op
import sqlalchemy as sa
revision = '20261025_verified_email'
down_revision = '20261025_browser_auth'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(), nullable=True))
    with op.batch_alter_table('pending_signups') as batch:
        batch.add_column(sa.Column('user_id', sa.String(36), nullable=True))
        batch.create_foreign_key('fk_pending_signup_user', 'users', ['user_id'], ['id'], ondelete='CASCADE')


def downgrade():
    # Do not convert authenticated verification challenges to guest signup challenges.
    op.execute('DELETE FROM pending_signups WHERE user_id IS NOT NULL')
    with op.batch_alter_table('pending_signups') as batch:
        batch.drop_constraint('fk_pending_signup_user', type_='foreignkey')
        batch.drop_column('user_id')
    with op.batch_alter_table('users') as batch:
        batch.drop_column('email_verified_at')
