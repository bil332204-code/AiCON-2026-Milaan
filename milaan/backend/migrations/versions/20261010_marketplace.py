"""Add products, cart_items, marketplace_orders, marketplace_order_items, and users.is_admin

Revision ID: 20261010_marketplace
Revises: 20261010_public_orders
Create Date: 2026-10-10
"""
from alembic import op
import sqlalchemy as sa

revision = "20261010_marketplace"
down_revision = "20261010_public_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add is_admin to users
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("is_admin", sa.Boolean(), server_default=sa.false(), nullable=False))

    # 2. Create products table
    op.create_table(
        "products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("sku", sa.String(100), nullable=False),
        sa.Column("category", sa.String(100), server_default="General", nullable=False),
        sa.Column("purchase_price_paisa", sa.BigInteger(), nullable=False),
        sa.Column("selling_price_paisa", sa.BigInteger(), nullable=False),
        sa.Column("stock_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("low_stock_threshold", sa.Integer(), server_default="5", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("sku", name="uq_products_sku"),
    )
    op.create_index("ix_products_sku", "products", ["sku"])
    op.create_index("ix_products_category", "products", ["category"])
    op.create_index("ix_products_is_active", "products", ["is_active"])

    # 3. Create cart_items table
    op.create_table(
        "cart_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),
    )
    op.create_index("ix_cart_items_user_id", "cart_items", ["user_id"])
    op.create_index("ix_cart_items_product_id", "cart_items", ["product_id"])

    # 4. Create marketplace_orders table
    op.create_table(
        "marketplace_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_number", sa.String(50), nullable=False),
        sa.Column("seller_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_name", sa.String(150), nullable=False),
        sa.Column("customer_email", sa.String(254), nullable=False),
        sa.Column("customer_phone", sa.String(30), nullable=True),
        sa.Column("shipping_address", sa.Text(), nullable=True),
        sa.Column("subtotal_paisa", sa.BigInteger(), nullable=False),
        sa.Column("shipping_fee_paisa", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("total_paisa", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(30), server_default="Pending", nullable=False),
        sa.Column("payment_mode", sa.String(30), server_default="test_checkout", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("order_number", name="uq_marketplace_orders_number"),
    )
    op.create_index("ix_marketplace_orders_order_number", "marketplace_orders", ["order_number"])
    op.create_index("ix_marketplace_orders_seller_id", "marketplace_orders", ["seller_id"])
    op.create_index("ix_marketplace_orders_status", "marketplace_orders", ["status"])
    op.create_index("ix_marketplace_orders_created_at", "marketplace_orders", ["created_at"])

    # 5. Create marketplace_order_items table
    op.create_table(
        "marketplace_order_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("marketplace_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("product_sku", sa.String(100), nullable=False),
        sa.Column("unit_price_paisa", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("total_price_paisa", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_marketplace_order_items_order_id", "marketplace_order_items", ["order_id"])
    op.create_index("ix_marketplace_order_items_product_id", "marketplace_order_items", ["product_id"])


def downgrade() -> None:
    op.drop_table("marketplace_order_items")
    op.drop_table("marketplace_orders")
    op.drop_table("cart_items")
    op.drop_table("products")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("is_admin")
