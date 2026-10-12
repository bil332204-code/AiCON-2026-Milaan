"""add customer_phone and placed_at to orders

Revision ID: 20261010_public_orders
Revises: 20261010_email_verification
Create Date: 2026-10-10
"""
from alembic import op
import sqlalchemy as sa

revision = "20261010_public_orders"
down_revision = "20261010_email"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("customer_phone", sa.String(30), nullable=True))
    op.add_column("orders", sa.Column("placed_at", sa.DateTime, nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "placed_at")
    op.drop_column("orders", "customer_phone")
