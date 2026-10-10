"""Add pending signup challenges; preserve all existing users and records."""
from alembic import op
import sqlalchemy as sa
revision = "20261010_email"
down_revision = "69e0023d423a"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("pending_signups",
        sa.Column("email", sa.String(254), primary_key=True),
        sa.Column("challenge_id", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("code_hash", sa.String(256), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(), nullable=False),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("send_count", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False))

def downgrade():
    op.drop_table("pending_signups")
