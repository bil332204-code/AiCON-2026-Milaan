"""Independent cookie sessions and password recovery; preserve existing account IDs."""
from alembic import op
import sqlalchemy as sa
revision = '20261025_browser_auth'
down_revision = '20261024_payment_parts'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('failed_logins', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('login_locked_until', sa.DateTime(), nullable=True))
    op.add_column('session_tokens', sa.Column('session_kind', sa.String(10), nullable=False, server_default='bearer'))
    op.create_table('password_resets',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('last_sent_at', sa.DateTime(), nullable=False),
        sa.Column('window_start', sa.DateTime(), nullable=False),
        sa.Column('send_count', sa.Integer(), nullable=False))


def downgrade():
    # Cookie credentials must never become valid bearer credentials on old code.
    op.execute("DELETE FROM session_tokens WHERE session_kind = 'cookie'")
    op.drop_table('password_resets')
    with op.batch_alter_table('session_tokens') as batch:
        batch.drop_column('session_kind')
    with op.batch_alter_table('users') as batch:
        batch.drop_column('failed_logins')
        batch.drop_column('login_locked_until')
