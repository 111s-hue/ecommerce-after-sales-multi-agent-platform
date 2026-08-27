from typing import Protocol

from app.domain.models import (
    AfterSaleTicket,
    ApprovalTask,
    AuditLog,
    ChatMessage,
    Conversation,
    Logistics,
    Order,
)


class SupportRepository(Protocol):
    def healthcheck(self) -> bool: ...

    def get_order(self, order_id: str, user_id: str) -> Order | None: ...

    def list_orders(
        self, user_id: str | None = None, status: str | None = None, limit: int = 100
    ) -> list[Order]: ...

    def get_logistics(self, order_id: str, user_id: str) -> Logistics | None: ...

    def create_after_sale(
        self,
        *,
        order_id: str,
        user_id: str,
        reason: str,
        refundable_amount: float,
        idempotency_key: str,
        reviewer: str,
    ) -> AfterSaleTicket: ...

    def get_after_sale_by_key(self, idempotency_key: str) -> AfterSaleTicket | None: ...

    def list_after_sales(
        self, user_id: str | None = None, status: str | None = None, limit: int = 100
    ) -> list[AfterSaleTicket]: ...

    def add_audit(
        self,
        *,
        thread_id: str,
        user_id: str,
        action: str,
        resource: str,
        outcome: str,
        detail: str = "",
    ) -> AuditLog: ...

    def list_audits(self, limit: int = 100) -> list[AuditLog]: ...

    def upsert_conversation(
        self, *, thread_id: str, user_id: str, title: str, status: str, intent: str | None
    ) -> Conversation: ...

    def add_message(
        self, *, thread_id: str, role: str, content: str, metadata_json: str = "{}"
    ) -> ChatMessage: ...

    def list_conversations(
        self, user_id: str | None = None, limit: int = 100
    ) -> list[Conversation]: ...

    def list_messages(self, thread_id: str) -> list[ChatMessage]: ...

    def upsert_approval(
        self,
        *,
        thread_id: str,
        user_id: str,
        order_id: str,
        action: str,
        amount: float,
        payload_json: str,
    ) -> ApprovalTask: ...

    def decide_approval(
        self, *, thread_id: str, approved: bool, reviewer: str, reason: str
    ) -> ApprovalTask | None: ...

    def list_approvals(self, status: str | None = None, limit: int = 100) -> list[ApprovalTask]: ...
