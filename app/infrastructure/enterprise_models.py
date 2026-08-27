"""Enterprise baseline relational schema.

The existing MVP tables remain readable during migration. New bounded contexts use
tenant-scoped records, UUID-like public identifiers, precise money columns and
explicit history/attempt tables. Alembic owns production schema upgrades.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base

ID = String(36)
BUSINESS_ID = String(64)
MONEY = Numeric(18, 2)


class TenantRow(Base):
    __tablename__ = "tenants"

    tenant_id: Mapped[str] = mapped_column(ID, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class UserAccountRow(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "username", name="uq_users_tenant_name"),)

    user_id: Mapped[str] = mapped_column(ID, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    username: Mapped[str] = mapped_column(String(64), index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone_masked: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class UserCredentialRow(Base):
    __tablename__ = "user_credentials"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    password_changed_at: Mapped[datetime] = mapped_column(DateTime)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)


class RoleRow(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_roles_tenant_code"),)

    role_id: Mapped[str] = mapped_column(ID, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(255), default="")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class PermissionRow(Base):
    __tablename__ = "permissions"

    permission_id: Mapped[str] = mapped_column(ID, primary_key=True)
    code: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    resource: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))


class UserRoleRow(Base):
    __tablename__ = "user_roles"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.role_id"), primary_key=True)
    granted_by: Mapped[str] = mapped_column(String(64))
    granted_at: Mapped[datetime] = mapped_column(DateTime)


class RolePermissionRow(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[str] = mapped_column(ForeignKey("roles.role_id"), primary_key=True)
    permission_id: Mapped[str] = mapped_column(
        ForeignKey("permissions.permission_id"), primary_key=True
    )


class RefreshTokenRow(Base):
    __tablename__ = "refresh_tokens"

    token_id: Mapped[str] = mapped_column(ID, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    family_id: Mapped[str] = mapped_column(ID, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    replaced_by: Mapped[str | None] = mapped_column(ID, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class LoginEventRow(Base):
    __tablename__ = "login_events"

    event_id: Mapped[str] = mapped_column(ID, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ID, index=True)
    user_id: Mapped[str | None] = mapped_column(ID, nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(32), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class OIDCConnectionRow(Base):
    __tablename__ = "oidc_connections"

    connection_id: Mapped[str] = mapped_column(ID, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    issuer: Mapped[str] = mapped_column(String(512))
    client_id: Mapped[str] = mapped_column(String(255))
    secret_reference: Mapped[str] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime)


def _id(name: str) -> Column:
    return Column(name, ID, primary_key=True)


def _tenant() -> Column:
    return Column("tenant_id", ID, ForeignKey("tenants.tenant_id"), nullable=False, index=True)


def _timestamps() -> tuple[Column, Column]:
    return (
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
    )


customers = Table(
    "customers",
    Base.metadata,
    _id("customer_id"),
    _tenant(),
    Column("external_customer_id", BUSINESS_ID),
    Column("display_name", String(128), nullable=False),
    Column("email_masked", String(255)),
    Column("phone_masked", String(32)),
    Column("status", String(32), nullable=False, default="active"),
    *_timestamps(),
    UniqueConstraint("tenant_id", "external_customer_id", name="uq_customers_external"),
)
customer_addresses = Table(
    "customer_addresses",
    Base.metadata,
    _id("address_id"),
    _tenant(),
    Column("customer_id", ID, ForeignKey("customers.customer_id"), nullable=False),
    Column("recipient_masked", String(128)),
    Column("phone_masked", String(32)),
    Column("region", String(255)),
    Column("address_ciphertext", Text),
    Column("is_default", Boolean),
    *_timestamps(),
)
products = Table(
    "products",
    Base.metadata,
    _id("product_id"),
    _tenant(),
    Column("name", String(255), nullable=False),
    Column("category", String(128)),
    Column("status", String(32), nullable=False),
    *_timestamps(),
)
product_skus = Table(
    "product_skus",
    Base.metadata,
    _id("sku_id"),
    _tenant(),
    Column("product_id", ID, ForeignKey("products.product_id"), nullable=False),
    Column("sku_code", String(128), nullable=False),
    Column("name", String(255), nullable=False),
    Column("attributes_json", Text, nullable=False, default="{}"),
    *_timestamps(),
    UniqueConstraint("tenant_id", "sku_code", name="uq_skus_code"),
)
order_items = Table(
    "order_items",
    Base.metadata,
    _id("order_item_id"),
    _tenant(),
    Column("order_id", String(32), nullable=False, index=True),
    Column("sku_id", ID),
    Column("sku_code", String(128)),
    Column("product_name", String(255), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("unit_price", MONEY, nullable=False),
    Column("paid_amount", MONEY, nullable=False),
    Column("refunded_amount", MONEY, nullable=False, default=0),
    Column("snapshot_json", Text, nullable=False, default="{}"),
    *_timestamps(),
)
order_addresses = Table(
    "order_addresses",
    Base.metadata,
    _id("order_address_id"),
    _tenant(),
    Column("order_id", String(32), nullable=False, index=True),
    Column("address_type", String(32)),
    Column("recipient_masked", String(128)),
    Column("phone_masked", String(32)),
    Column("address_ciphertext", Text),
    *_timestamps(),
)
order_status_history = Table(
    "order_status_history",
    Base.metadata,
    _id("history_id"),
    _tenant(),
    Column("order_id", String(32), nullable=False, index=True),
    Column("from_status", String(32)),
    Column("to_status", String(32), nullable=False),
    Column("actor_type", String(32), nullable=False),
    Column("actor_id", String(64)),
    Column("reason", String(500)),
    Column("created_at", DateTime, nullable=False),
)
payments = Table(
    "payments",
    Base.metadata,
    _id("payment_id"),
    _tenant(),
    Column("order_id", String(32), nullable=False, index=True),
    Column("provider", String(64), nullable=False),
    Column("merchant_trade_no", String(128), nullable=False),
    Column("provider_trade_no", String(128)),
    Column("amount", MONEY, nullable=False),
    Column("refunded_amount", MONEY, nullable=False, default=0),
    Column("currency", String(3), nullable=False),
    Column("status", String(32), nullable=False, index=True),
    Column("paid_at", DateTime),
    *_timestamps(),
    UniqueConstraint("tenant_id", "merchant_trade_no", name="uq_payments_merchant_no"),
)
payment_transactions = Table(
    "payment_transactions",
    Base.metadata,
    _id("transaction_id"),
    _tenant(),
    Column("payment_id", ID, ForeignKey("payments.payment_id"), nullable=False, index=True),
    Column("transaction_type", String(32), nullable=False),
    Column("amount", MONEY, nullable=False),
    Column("provider_request_id", String(128)),
    Column("status", String(32), nullable=False),
    Column("request_json", Text, nullable=False),
    Column("response_json", Text),
    *_timestamps(),
)
payment_callbacks = Table(
    "payment_callbacks",
    Base.metadata,
    _id("callback_id"),
    _tenant(),
    Column("provider", String(64), nullable=False),
    Column("provider_event_id", String(128), nullable=False),
    Column("event_type", String(64), nullable=False),
    Column("signature_valid", Boolean, nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("processed_at", DateTime),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("provider", "provider_event_id", name="uq_payment_callbacks_event"),
)
shipments = Table(
    "shipments",
    Base.metadata,
    _id("shipment_id"),
    _tenant(),
    Column("order_id", String(32), nullable=False, index=True),
    Column("carrier", String(64)),
    Column("tracking_no", String(128)),
    Column("status", String(32), nullable=False),
    Column("shipped_at", DateTime),
    Column("delivered_at", DateTime),
    *_timestamps(),
    UniqueConstraint("tenant_id", "carrier", "tracking_no", name="uq_shipments_tracking"),
)
shipment_items = Table(
    "shipment_items",
    Base.metadata,
    Column("shipment_id", ID, ForeignKey("shipments.shipment_id"), primary_key=True),
    Column("order_item_id", ID, ForeignKey("order_items.order_item_id"), primary_key=True),
    Column("quantity", Integer, nullable=False),
)
shipment_events = Table(
    "shipment_events",
    Base.metadata,
    _id("event_id"),
    _tenant(),
    Column("shipment_id", ID, ForeignKey("shipments.shipment_id"), nullable=False, index=True),
    Column("event_code", String(64)),
    Column("description", String(500), nullable=False),
    Column("location", String(255)),
    Column("occurred_at", DateTime, nullable=False),
    Column("raw_json", Text),
)

after_sale_cases = Table(
    "after_sale_cases",
    Base.metadata,
    _id("case_id"),
    _tenant(),
    Column("case_no", String(64), nullable=False),
    Column("order_id", String(32), nullable=False, index=True),
    Column("customer_id", ID),
    Column("case_type", String(32), nullable=False, index=True),
    Column("source", String(32), nullable=False),
    Column("reason_code", String(64)),
    Column("reason", Text, nullable=False),
    Column("requested_amount", MONEY),
    Column("approved_amount", MONEY),
    Column("currency", String(3), nullable=False, default="CNY"),
    Column("status", String(32), nullable=False, index=True),
    Column("priority", String(16), nullable=False),
    Column("assignee_id", ID),
    Column("sla_due_at", DateTime),
    Column("closed_at", DateTime),
    Column("version", Integer, nullable=False, default=1),
    *_timestamps(),
    UniqueConstraint("tenant_id", "case_no", name="uq_after_sale_case_no"),
)
after_sale_items = Table(
    "after_sale_items",
    Base.metadata,
    _id("case_item_id"),
    _tenant(),
    Column("case_id", ID, ForeignKey("after_sale_cases.case_id"), nullable=False, index=True),
    Column("order_item_id", ID, nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("requested_amount", MONEY),
    Column("approved_amount", MONEY),
    *_timestamps(),
)
after_sale_evidence = Table(
    "after_sale_evidence",
    Base.metadata,
    _id("evidence_id"),
    _tenant(),
    Column("case_id", ID, ForeignKey("after_sale_cases.case_id"), nullable=False, index=True),
    Column("evidence_type", String(32)),
    Column("object_key", String(512)),
    Column("content_type", String(128)),
    Column("sha256", String(64)),
    Column("submitted_by", ID),
    Column("created_at", DateTime, nullable=False),
)
after_sale_status_history = Table(
    "after_sale_status_history",
    Base.metadata,
    _id("history_id"),
    _tenant(),
    Column("case_id", ID, ForeignKey("after_sale_cases.case_id"), nullable=False, index=True),
    Column("from_status", String(32)),
    Column("to_status", String(32), nullable=False),
    Column("actor_type", String(32)),
    Column("actor_id", String(64)),
    Column("reason", String(500)),
    Column("payload_json", Text, nullable=False, default="{}"),
    Column("created_at", DateTime, nullable=False),
)
case_assignments = Table(
    "case_assignments",
    Base.metadata,
    _id("assignment_id"),
    _tenant(),
    Column("case_id", ID, ForeignKey("after_sale_cases.case_id"), nullable=False, index=True),
    Column("from_user_id", ID),
    Column("to_user_id", ID, nullable=False),
    Column("reason", String(500)),
    Column("assigned_at", DateTime, nullable=False),
    Column("released_at", DateTime),
)
case_comments = Table(
    "case_comments",
    Base.metadata,
    _id("comment_id"),
    _tenant(),
    Column("case_id", ID, ForeignKey("after_sale_cases.case_id"), nullable=False, index=True),
    Column("author_id", ID, nullable=False),
    Column("visibility", String(32), nullable=False),
    Column("content", Text, nullable=False),
    Column("created_at", DateTime, nullable=False),
)
approval_definitions = Table(
    "approval_definitions",
    Base.metadata,
    _id("definition_id"),
    _tenant(),
    Column("code", String(64), nullable=False),
    Column("name", String(128), nullable=False),
    Column("version", Integer, nullable=False),
    Column("steps_json", Text, nullable=False),
    Column("enabled", Boolean, nullable=False),
    *_timestamps(),
    UniqueConstraint("tenant_id", "code", "version", name="uq_approval_def_version"),
)
approval_records = Table(
    "approval_records",
    Base.metadata,
    _id("record_id"),
    _tenant(),
    Column("task_thread_id", String(64), nullable=False, index=True),
    Column("step_no", Integer, nullable=False),
    Column("action", String(32), nullable=False),
    Column("actor_id", ID, nullable=False),
    Column("reason", String(500)),
    Column("snapshot_json", Text, nullable=False),
    Column("created_at", DateTime, nullable=False),
)
returns = Table(
    "returns",
    Base.metadata,
    _id("return_id"),
    _tenant(),
    Column("case_id", ID, ForeignKey("after_sale_cases.case_id"), nullable=False, unique=True),
    Column("return_no", String(64), nullable=False),
    Column("status", String(32), nullable=False, index=True),
    Column("return_address_json", Text),
    Column("shipped_at", DateTime),
    Column("received_at", DateTime),
    *_timestamps(),
    UniqueConstraint("tenant_id", "return_no", name="uq_returns_no"),
)
return_shipments = Table(
    "return_shipments",
    Base.metadata,
    _id("return_shipment_id"),
    _tenant(),
    Column("return_id", ID, ForeignKey("returns.return_id"), nullable=False, index=True),
    Column("carrier", String(64)),
    Column("tracking_no", String(128)),
    Column("status", String(32)),
    *_timestamps(),
)
return_inspections = Table(
    "return_inspections",
    Base.metadata,
    _id("inspection_id"),
    _tenant(),
    Column("return_id", ID, ForeignKey("returns.return_id"), nullable=False, index=True),
    Column("inspector_id", ID),
    Column("result", String(32), nullable=False),
    Column("deduction_amount", MONEY),
    Column("notes", Text),
    Column("evidence_json", Text, nullable=False, default="[]"),
    Column("inspected_at", DateTime),
    *_timestamps(),
)


def _fulfillment_order(name: str, id_name: str) -> Table:
    return Table(
        name,
        Base.metadata,
        _id(id_name),
        _tenant(),
        Column("case_id", ID, ForeignKey("after_sale_cases.case_id"), nullable=False, unique=True),
        Column("status", String(32), nullable=False, index=True),
        Column("payload_json", Text, nullable=False, default="{}"),
        Column("completed_at", DateTime),
        *_timestamps(),
    )


exchange_orders = _fulfillment_order("exchange_orders", "exchange_id")
reshipment_orders = _fulfillment_order("reshipment_orders", "reshipment_id")
repair_orders = _fulfillment_order("repair_orders", "repair_id")
refunds = Table(
    "refunds",
    Base.metadata,
    _id("refund_id"),
    _tenant(),
    Column("case_id", ID, ForeignKey("after_sale_cases.case_id"), nullable=False, index=True),
    Column("payment_id", ID, ForeignKey("payments.payment_id")),
    Column("refund_no", String(64), nullable=False),
    Column("provider", String(64), nullable=False),
    Column("amount", MONEY, nullable=False),
    Column("currency", String(3), nullable=False),
    Column("status", String(32), nullable=False, index=True),
    Column("idempotency_key", String(128), nullable=False),
    Column("provider_refund_no", String(128)),
    Column("failure_code", String(64)),
    Column("failure_message", String(500)),
    Column("version", Integer, nullable=False, default=1),
    Column("processed_at", DateTime),
    *_timestamps(),
    UniqueConstraint("tenant_id", "refund_no", name="uq_refunds_no"),
    UniqueConstraint("tenant_id", "idempotency_key", name="uq_refunds_idempotency"),
)
refund_attempts = Table(
    "refund_attempts",
    Base.metadata,
    _id("attempt_id"),
    _tenant(),
    Column("refund_id", ID, ForeignKey("refunds.refund_id"), nullable=False, index=True),
    Column("attempt_no", Integer, nullable=False),
    Column("request_id", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    Column("request_json", Text, nullable=False),
    Column("response_json", Text),
    Column("error_code", String(64)),
    Column("error_message", String(500)),
    Column("started_at", DateTime, nullable=False),
    Column("finished_at", DateTime),
    UniqueConstraint("refund_id", "attempt_no", name="uq_refund_attempt_no"),
)
refund_events = Table(
    "refund_events",
    Base.metadata,
    _id("event_id"),
    _tenant(),
    Column("refund_id", ID, ForeignKey("refunds.refund_id"), nullable=False, index=True),
    Column("event_type", String(64), nullable=False),
    Column("from_status", String(32)),
    Column("to_status", String(32), nullable=False),
    Column("actor_type", String(32)),
    Column("actor_id", String(64)),
    Column("payload_json", Text, nullable=False, default="{}"),
    Column("created_at", DateTime, nullable=False),
)
refund_reconciliations = Table(
    "refund_reconciliations",
    Base.metadata,
    _id("reconciliation_id"),
    _tenant(),
    Column("refund_id", ID, ForeignKey("refunds.refund_id"), nullable=False, index=True),
    Column("provider", String(64)),
    Column("provider_amount", MONEY),
    Column("local_amount", MONEY),
    Column("result", String(32)),
    Column("difference_reason", String(500)),
    Column("reconciled_at", DateTime),
    *_timestamps(),
)
compensation_records = Table(
    "compensation_records",
    Base.metadata,
    _id("compensation_id"),
    _tenant(),
    Column("case_id", ID, ForeignKey("after_sale_cases.case_id"), nullable=False, index=True),
    Column("compensation_type", String(32)),
    Column("amount", MONEY),
    Column("currency", String(3)),
    Column("status", String(32)),
    Column("external_reference", String(128)),
    *_timestamps(),
)

message_attachments = Table(
    "message_attachments",
    Base.metadata,
    _id("attachment_id"),
    _tenant(),
    Column("message_id", Integer, nullable=False, index=True),
    Column("object_key", String(512), nullable=False),
    Column("content_type", String(128)),
    Column("size", Integer),
    Column("sha256", String(64)),
    Column("created_at", DateTime, nullable=False),
)
message_feedback = Table(
    "message_feedback",
    Base.metadata,
    _id("feedback_id"),
    _tenant(),
    Column("message_id", Integer, nullable=False, index=True),
    Column("user_id", ID),
    Column("rating", Integer),
    Column("reason", String(500)),
    Column("created_at", DateTime, nullable=False),
)
agent_runs = Table(
    "agent_runs",
    Base.metadata,
    _id("run_id"),
    _tenant(),
    Column("thread_id", String(64), nullable=False, index=True),
    Column("user_id", String(64), nullable=False),
    Column("intent", String(32)),
    Column("status", String(32), nullable=False),
    Column("model", String(128)),
    Column("prompt_version", String(64)),
    Column("input_tokens", Integer),
    Column("output_tokens", Integer),
    Column("cost_amount", Numeric(18, 6)),
    Column("error_code", String(64)),
    Column("started_at", DateTime, nullable=False),
    Column("finished_at", DateTime),
)
agent_run_steps = Table(
    "agent_run_steps",
    Base.metadata,
    _id("step_id"),
    _tenant(),
    Column("run_id", ID, ForeignKey("agent_runs.run_id"), nullable=False, index=True),
    Column("step_no", Integer, nullable=False),
    Column("node", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    Column("input_json", Text),
    Column("output_json", Text),
    Column("duration_ms", Integer),
    Column("started_at", DateTime),
    Column("finished_at", DateTime),
)
tool_calls = Table(
    "tool_calls",
    Base.metadata,
    _id("tool_call_id"),
    _tenant(),
    Column("run_id", ID, ForeignKey("agent_runs.run_id"), nullable=False, index=True),
    Column("step_id", ID),
    Column("tool_name", String(128), nullable=False),
    Column("request_json", Text, nullable=False),
    Column("response_json", Text),
    Column("status", String(32), nullable=False),
    Column("duration_ms", Integer),
    Column("idempotency_key", String(128)),
    Column("created_at", DateTime, nullable=False),
)
human_handoff_tasks = Table(
    "human_handoff_tasks",
    Base.metadata,
    _id("handoff_id"),
    _tenant(),
    Column("thread_id", String(64), nullable=False, index=True),
    Column("case_id", ID),
    Column("reason", String(500)),
    Column("status", String(32), nullable=False),
    Column("assignee_id", ID),
    Column("due_at", DateTime),
    Column("resolved_at", DateTime),
    *_timestamps(),
)

knowledge_bases = Table(
    "knowledge_bases",
    Base.metadata,
    _id("knowledge_base_id"),
    _tenant(),
    Column("name", String(128), nullable=False),
    Column("description", String(500)),
    Column("status", String(32), nullable=False),
    *_timestamps(),
)
knowledge_documents = Table(
    "knowledge_documents",
    Base.metadata,
    _id("document_id"),
    _tenant(),
    Column(
        "knowledge_base_id",
        ID,
        ForeignKey("knowledge_bases.knowledge_base_id"),
        nullable=False,
        index=True,
    ),
    Column("title", String(255), nullable=False),
    Column("slug", String(255), nullable=False),
    Column("status", String(32), nullable=False),
    Column("current_version_id", ID),
    *_timestamps(),
    UniqueConstraint("tenant_id", "knowledge_base_id", "slug", name="uq_kb_document_slug"),
)
knowledge_document_versions = Table(
    "knowledge_document_versions",
    Base.metadata,
    _id("version_id"),
    _tenant(),
    Column(
        "document_id", ID, ForeignKey("knowledge_documents.document_id"), nullable=False, index=True
    ),
    Column("version_no", Integer, nullable=False),
    Column("object_key", String(512), nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("content_type", String(128)),
    Column("size", Integer),
    Column("status", String(32), nullable=False),
    Column("created_by", ID),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("document_id", "version_no", name="uq_knowledge_doc_version"),
)
knowledge_chunks = Table(
    "knowledge_chunks",
    Base.metadata,
    _id("chunk_id"),
    _tenant(),
    Column(
        "version_id",
        ID,
        ForeignKey("knowledge_document_versions.version_id"),
        nullable=False,
        index=True,
    ),
    Column("sequence_no", Integer, nullable=False),
    Column("section", String(512)),
    Column("content", Text, nullable=False),
    Column("content_hash", String(64), nullable=False),
    Column("embedding_ref", String(255)),
    UniqueConstraint("version_id", "sequence_no", name="uq_knowledge_chunk_sequence"),
)
knowledge_review_records = Table(
    "knowledge_review_records",
    Base.metadata,
    _id("review_id"),
    _tenant(),
    Column(
        "version_id",
        ID,
        ForeignKey("knowledge_document_versions.version_id"),
        nullable=False,
        index=True,
    ),
    Column("reviewer_id", ID, nullable=False),
    Column("decision", String(32), nullable=False),
    Column("comment", String(500)),
    Column("created_at", DateTime, nullable=False),
)
knowledge_index_jobs = Table(
    "knowledge_index_jobs",
    Base.metadata,
    _id("job_id"),
    _tenant(),
    Column(
        "version_id",
        ID,
        ForeignKey("knowledge_document_versions.version_id"),
        nullable=False,
        index=True,
    ),
    Column("backend", String(64), nullable=False),
    Column("status", String(32), nullable=False, index=True),
    Column("chunk_count", Integer),
    Column("error_message", String(1000)),
    Column("started_at", DateTime),
    Column("finished_at", DateTime),
    *_timestamps(),
)
knowledge_publications = Table(
    "knowledge_publications",
    Base.metadata,
    _id("publication_id"),
    _tenant(),
    Column(
        "version_id",
        ID,
        ForeignKey("knowledge_document_versions.version_id"),
        nullable=False,
        index=True,
    ),
    Column("environment", String(32), nullable=False),
    Column("status", String(32), nullable=False),
    Column("published_by", ID),
    Column("published_at", DateTime),
    Column("retired_at", DateTime),
    *_timestamps(),
)

quality_rules = Table(
    "quality_rules",
    Base.metadata,
    _id("rule_id"),
    _tenant(),
    Column("code", String(64), nullable=False),
    Column("name", String(128), nullable=False),
    Column("rule_type", String(32), nullable=False),
    Column("definition_json", Text, nullable=False),
    Column("enabled", Boolean, nullable=False),
    *_timestamps(),
)
quality_tasks = Table(
    "quality_tasks",
    Base.metadata,
    _id("task_id"),
    _tenant(),
    Column("thread_id", String(64), nullable=False, index=True),
    Column("status", String(32), nullable=False),
    Column("assignee_id", ID),
    Column("due_at", DateTime),
    *_timestamps(),
)
quality_results = Table(
    "quality_results",
    Base.metadata,
    _id("result_id"),
    _tenant(),
    Column("task_id", ID, ForeignKey("quality_tasks.task_id"), nullable=False, index=True),
    Column("rule_id", ID, ForeignKey("quality_rules.rule_id")),
    Column("score", Numeric(8, 4)),
    Column("passed", Boolean),
    Column("findings_json", Text, nullable=False),
    Column("reviewed_by", ID),
    Column("created_at", DateTime, nullable=False),
)
evaluation_suites = Table(
    "evaluation_suites",
    Base.metadata,
    _id("suite_id"),
    _tenant(),
    Column("name", String(128), nullable=False),
    Column("version", Integer, nullable=False),
    Column("status", String(32), nullable=False),
    *_timestamps(),
)
evaluation_cases = Table(
    "evaluation_cases",
    Base.metadata,
    _id("evaluation_case_id"),
    _tenant(),
    Column("suite_id", ID, ForeignKey("evaluation_suites.suite_id"), nullable=False, index=True),
    Column("name", String(128), nullable=False),
    Column("input_json", Text, nullable=False),
    Column("expected_json", Text, nullable=False),
    Column("enabled", Boolean, nullable=False),
    *_timestamps(),
)
evaluation_runs = Table(
    "evaluation_runs",
    Base.metadata,
    _id("evaluation_run_id"),
    _tenant(),
    Column("suite_id", ID, ForeignKey("evaluation_suites.suite_id"), nullable=False, index=True),
    Column("status", String(32), nullable=False),
    Column("model", String(128)),
    Column("config_json", Text),
    Column("started_at", DateTime),
    Column("finished_at", DateTime),
    *_timestamps(),
)
evaluation_results = Table(
    "evaluation_results",
    Base.metadata,
    _id("evaluation_result_id"),
    _tenant(),
    Column(
        "run_id", ID, ForeignKey("evaluation_runs.evaluation_run_id"), nullable=False, index=True
    ),
    Column(
        "evaluation_case_id", ID, ForeignKey("evaluation_cases.evaluation_case_id"), nullable=False
    ),
    Column("passed", Boolean, nullable=False),
    Column("score", Numeric(8, 4)),
    Column("actual_json", Text),
    Column("error_message", String(1000)),
    Column("created_at", DateTime, nullable=False),
)

idempotency_records = Table(
    "idempotency_records",
    Base.metadata,
    _id("record_id"),
    _tenant(),
    Column("scope", String(64), nullable=False),
    Column("idempotency_key", String(128), nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    Column("response_code", Integer),
    Column("response_json", Text),
    Column("expires_at", DateTime),
    *_timestamps(),
    UniqueConstraint("tenant_id", "scope", "idempotency_key", name="uq_idempotency_scope_key"),
)
outbox_events = Table(
    "outbox_events",
    Base.metadata,
    _id("event_id"),
    _tenant(),
    Column("aggregate_type", String(64), nullable=False),
    Column("aggregate_id", String(64), nullable=False, index=True),
    Column("event_type", String(128), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("status", String(32), nullable=False, index=True),
    Column("available_at", DateTime, nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
    Column("last_error", String(1000)),
    Column("processed_at", DateTime),
    Column("created_at", DateTime, nullable=False),
)
inbox_events = Table(
    "inbox_events",
    Base.metadata,
    _id("inbox_id"),
    _tenant(),
    Column("source", String(64), nullable=False),
    Column("external_event_id", String(128), nullable=False),
    Column("event_type", String(128), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("status", String(32), nullable=False),
    Column("processed_at", DateTime),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("tenant_id", "source", "external_event_id", name="uq_inbox_external_event"),
)
webhook_endpoints = Table(
    "webhook_endpoints",
    Base.metadata,
    _id("endpoint_id"),
    _tenant(),
    Column("name", String(128), nullable=False),
    Column("url", String(1024), nullable=False),
    Column("secret_reference", String(255), nullable=False),
    Column("event_types_json", Text, nullable=False),
    Column("enabled", Boolean, nullable=False),
    *_timestamps(),
)
webhook_deliveries = Table(
    "webhook_deliveries",
    Base.metadata,
    _id("delivery_id"),
    _tenant(),
    Column(
        "endpoint_id", ID, ForeignKey("webhook_endpoints.endpoint_id"), nullable=False, index=True
    ),
    Column("event_id", ID, nullable=False),
    Column("status", String(32), nullable=False),
    Column("attempt_no", Integer, nullable=False),
    Column("response_status", Integer),
    Column("response_body", Text),
    Column("next_retry_at", DateTime),
    Column("created_at", DateTime, nullable=False),
)
notifications = Table(
    "notifications",
    Base.metadata,
    _id("notification_id"),
    _tenant(),
    Column("recipient_id", ID, nullable=False, index=True),
    Column("channel", String(32), nullable=False),
    Column("template_code", String(64), nullable=False),
    Column("subject", String(255)),
    Column("payload_json", Text, nullable=False),
    Column("status", String(32), nullable=False),
    Column("read_at", DateTime),
    *_timestamps(),
)
notification_deliveries = Table(
    "notification_deliveries",
    Base.metadata,
    _id("notification_delivery_id"),
    _tenant(),
    Column(
        "notification_id",
        ID,
        ForeignKey("notifications.notification_id"),
        nullable=False,
        index=True,
    ),
    Column("provider", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    Column("attempt_no", Integer, nullable=False),
    Column("provider_message_id", String(128)),
    Column("error_message", String(500)),
    Column("sent_at", DateTime),
    Column("created_at", DateTime, nullable=False),
)
system_configs = Table(
    "system_configs",
    Base.metadata,
    _id("config_id"),
    _tenant(),
    Column("config_key", String(128), nullable=False),
    Column("value_json", Text, nullable=False),
    Column("is_secret_reference", Boolean, nullable=False),
    Column("version", Integer, nullable=False),
    Column("updated_by", ID),
    *_timestamps(),
    UniqueConstraint("tenant_id", "config_key", name="uq_system_config_key"),
)
feature_flags = Table(
    "feature_flags",
    Base.metadata,
    _id("flag_id"),
    _tenant(),
    Column("flag_key", String(128), nullable=False),
    Column("enabled", Boolean, nullable=False),
    Column("rules_json", Text, nullable=False, default="{}"),
    Column("updated_by", ID),
    *_timestamps(),
    UniqueConstraint("tenant_id", "flag_key", name="uq_feature_flag_key"),
)

Index(
    "ix_refunds_tenant_status_created", refunds.c.tenant_id, refunds.c.status, refunds.c.created_at
)
Index(
    "ix_cases_tenant_status_created",
    after_sale_cases.c.tenant_id,
    after_sale_cases.c.status,
    after_sale_cases.c.created_at,
)
Index("ix_outbox_available", outbox_events.c.status, outbox_events.c.available_at)


def register_models() -> None:
    """Import hook used by repository startup and Alembic metadata loading."""
