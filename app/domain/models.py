from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class OrderStatus(StrEnum):
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CLOSED = "closed"


class AfterSaleStatus(StrEnum):
    CREATED = "created"
    REJECTED = "rejected"
    COMPLETED = "completed"


class Order(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: str
    user_id: str
    product_name: str
    amount: float = Field(ge=0)
    status: OrderStatus
    created_at: datetime
    delivered_at: datetime | None = None


class Logistics(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: str
    carrier: str
    tracking_no: str
    status: str
    latest_event: str
    updated_at: datetime


class RefundEligibility(BaseModel):
    eligible: bool
    reason: str
    refundable_amount: float = Field(ge=0)
    policy_reference: str


class AfterSaleTicket(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticket_id: str
    order_id: str
    user_id: str
    reason: str
    refundable_amount: float
    status: AfterSaleStatus
    idempotency_key: str
    reviewer: str
    created_at: datetime


class AuditLog(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    thread_id: str
    user_id: str
    action: str
    resource: str
    outcome: str
    detail: str = ""
    created_at: datetime


class PolicyEvidence(BaseModel):
    source: str
    section: str
    content: str
    score: float


class TraceEvent(BaseModel):
    node: str
    message: str
    at: datetime = Field(default_factory=datetime.now)


class Conversation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    thread_id: str
    user_id: str
    title: str
    status: str
    intent: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    thread_id: str
    role: str
    content: str
    metadata_json: str = "{}"
    created_at: datetime


class ApprovalTask(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    thread_id: str
    user_id: str
    order_id: str
    action: str
    amount: float
    status: str
    reviewer: str | None = None
    reason: str = ""
    payload_json: str
    created_at: datetime
    decided_at: datetime | None = None


class KnowledgeDocument(BaseModel):
    name: str
    size: int
    updated_at: datetime
    storage: str
