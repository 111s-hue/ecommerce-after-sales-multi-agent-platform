"""enrich legacy orders for tenant-aware commerce

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_columns = {column["name"] for column in sa.inspect(bind).get_columns("orders")}

    def add_if_missing(column: sa.Column) -> None:
        if column.name not in existing_columns:
            op.add_column("orders", column)

    add_if_missing(
        sa.Column(
            "tenant_id",
            sa.String(length=36),
            nullable=False,
            server_default="tenant-community",
        )
    )
    add_if_missing(sa.Column("external_order_no", sa.String(length=64)))
    add_if_missing(sa.Column("customer_id", sa.String(length=36)))
    add_if_missing(sa.Column("currency", sa.String(length=3), nullable=False, server_default="CNY"))
    add_if_missing(sa.Column("total_amount", sa.Numeric(18, 2)))
    add_if_missing(sa.Column("paid_amount", sa.Numeric(18, 2)))
    add_if_missing(
        sa.Column("payment_status", sa.String(length=32), nullable=False, server_default="paid")
    )
    add_if_missing(sa.Column("fulfillment_status", sa.String(length=32)))
    add_if_missing(
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="community")
    )
    add_if_missing(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    # SQLite rejects non-constant defaults in ALTER TABLE. Add, backfill, then
    # tighten the constraint with Alembic's batch table rebuild.
    add_if_missing(sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE orders SET external_order_no = order_id, customer_id = user_id, "
            "total_amount = amount, paid_amount = amount, fulfillment_status = status, "
            "updated_at = created_at"
        )
    )
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("orders") as batch_op:
            batch_op.alter_column("updated_at", existing_type=sa.DateTime(), nullable=False)
    else:
        op.alter_column("orders", "updated_at", existing_type=sa.DateTime(), nullable=False)
    existing_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("orders")}
    if "ix_orders_tenant_id" not in existing_indexes:
        op.create_index("ix_orders_tenant_id", "orders", ["tenant_id"])
    if "ix_orders_external_order_no" not in existing_indexes:
        op.create_index("ix_orders_external_order_no", "orders", ["external_order_no"])
    if "ix_orders_customer_id" not in existing_indexes:
        op.create_index("ix_orders_customer_id", "orders", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_customer_id", table_name="orders")
    op.drop_index("ix_orders_external_order_no", table_name="orders")
    op.drop_index("ix_orders_tenant_id", table_name="orders")
    for column in (
        "updated_at",
        "version",
        "channel",
        "fulfillment_status",
        "payment_status",
        "paid_amount",
        "total_amount",
        "currency",
        "customer_id",
        "external_order_no",
        "tenant_id",
    ):
        op.drop_column("orders", column)
