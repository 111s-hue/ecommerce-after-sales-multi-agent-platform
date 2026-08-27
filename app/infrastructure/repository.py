from __future__ import annotations

from datetime import datetime, timedelta
from threading import Lock
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
    desc,
    select,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.domain.models import (
    AfterSaleStatus,
    AfterSaleTicket,
    ApprovalTask,
    AuditLog,
    ChatMessage,
    Conversation,
    Logistics,
    Order,
    OrderStatus,
)
from app.infrastructure.database import Base
from app.infrastructure.enterprise_models import register_models

register_models()


class OrderRow(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    product_name: Mapped[str] = mapped_column(String(255))
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tenant_id: Mapped[str] = mapped_column(String(36), default="tenant-community", index=True)
    external_order_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="CNY")
    total_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    paid_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    payment_status: Mapped[str] = mapped_column(String(32), default="paid")
    fulfillment_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), default="community")
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class LogisticsRow(Base):
    __tablename__ = "logistics"

    order_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    carrier: Mapped[str] = mapped_column(String(64))
    tracking_no: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(32))
    latest_event: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class AfterSaleRow(Base):
    __tablename__ = "after_sale_tickets"

    ticket_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(32), index=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    reason: Mapped[str] = mapped_column(Text)
    refundable_amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    reviewer: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class AuditRow(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(64))
    resource: Mapped[str] = mapped_column(String(128))
    outcome: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ConversationRow(Base):
    __tablename__ = "conversations"

    thread_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), index=True)
    intent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class ChatMessageRow(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ApprovalTaskRow(Base):
    __tablename__ = "approval_tasks"

    thread_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    order_id: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(64))
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), index=True)
    reviewer: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


def _to_order(row: OrderRow) -> Order:
    return Order(
        order_id=row.order_id,
        user_id=row.user_id,
        product_name=row.product_name,
        amount=row.amount,
        status=OrderStatus(row.status),
        created_at=row.created_at,
        delivered_at=row.delivered_at,
    )


def _to_logistics(row: LogisticsRow) -> Logistics:
    return Logistics.model_validate(row)


def _to_ticket(row: AfterSaleRow) -> AfterSaleTicket:
    return AfterSaleTicket(
        ticket_id=row.ticket_id,
        order_id=row.order_id,
        user_id=row.user_id,
        reason=row.reason,
        refundable_amount=row.refundable_amount,
        status=AfterSaleStatus(row.status),
        idempotency_key=row.idempotency_key,
        reviewer=row.reviewer,
        created_at=row.created_at,
    )


def _to_audit(row: AuditRow) -> AuditLog:
    return AuditLog.model_validate(row)


def _to_conversation(row: ConversationRow) -> Conversation:
    return Conversation.model_validate(row)


def _to_message(row: ChatMessageRow) -> ChatMessage:
    return ChatMessage.model_validate(row)


def _to_approval(row: ApprovalTaskRow) -> ApprovalTask:
    return ApprovalTask.model_validate(row)


class SQLAlchemySupportRepository:
    def __init__(self, database_url: str):
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)

    def init_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def assert_schema_revision(self, expected_revision: str) -> None:
        try:
            with self.engine.connect() as connection:
                revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
        except Exception as exc:
            raise RuntimeError("数据库尚未迁移，请先执行 alembic upgrade head") from exc
        if revision != expected_revision:
            raise RuntimeError(
                f"数据库迁移版本为 {revision}，应用要求 {expected_revision}；"
                "请执行 alembic upgrade head"
            )

    def healthcheck(self) -> bool:
        with Session(self.engine) as session:
            session.execute(select(1))
        return True

    def seed_demo_data(self) -> None:
        now = datetime.now()
        with Session(self.engine) as session:
            if session.scalar(select(OrderRow.order_id).limit(1)):
                return
            session.add_all(
                [
                    OrderRow(
                        order_id="ORD-1001",
                        user_id="U1001",
                        product_name="智能降噪耳机",
                        amount=699.0,
                        status=OrderStatus.DELIVERED.value,
                        created_at=now - timedelta(days=10),
                        delivered_at=now - timedelta(days=3),
                        tenant_id="tenant-community",
                        external_order_no="ORD-1001",
                        customer_id="U1001",
                        currency="CNY",
                        total_amount=699.0,
                        paid_amount=699.0,
                        payment_status="paid",
                        fulfillment_status="delivered",
                        channel="community",
                        version=1,
                        updated_at=now,
                    ),
                    OrderRow(
                        order_id="ORD-1002",
                        user_id="U1001",
                        product_name="人体工学键盘",
                        amount=399.0,
                        status=OrderStatus.SHIPPED.value,
                        created_at=now - timedelta(days=2),
                        tenant_id="tenant-community",
                        external_order_no="ORD-1002",
                        customer_id="U1001",
                        currency="CNY",
                        total_amount=399.0,
                        paid_amount=399.0,
                        payment_status="paid",
                        fulfillment_status="shipped",
                        channel="community",
                        version=1,
                        updated_at=now,
                    ),
                    OrderRow(
                        order_id="ORD-2001",
                        user_id="U2001",
                        product_name="便携显示器",
                        amount=1299.0,
                        status=OrderStatus.DELIVERED.value,
                        created_at=now - timedelta(days=20),
                        delivered_at=now - timedelta(days=12),
                        tenant_id="tenant-community",
                        external_order_no="ORD-2001",
                        customer_id="U2001",
                        currency="CNY",
                        total_amount=1299.0,
                        paid_amount=1299.0,
                        payment_status="paid",
                        fulfillment_status="delivered",
                        channel="community",
                        version=1,
                        updated_at=now,
                    ),
                ]
            )
            session.add_all(
                [
                    LogisticsRow(
                        order_id="ORD-1001",
                        carrier="顺丰速运",
                        tracking_no="SF-DEMO-1001",
                        status="已签收",
                        latest_event="包裹已由本人签收",
                        updated_at=now - timedelta(days=3),
                    ),
                    LogisticsRow(
                        order_id="ORD-1002",
                        carrier="京东物流",
                        tracking_no="JD-DEMO-1002",
                        status="运输中",
                        latest_event="包裹已到达成都分拨中心",
                        updated_at=now - timedelta(hours=2),
                    ),
                    LogisticsRow(
                        order_id="ORD-2001",
                        carrier="中通快递",
                        tracking_no="ZT-DEMO-2001",
                        status="已签收",
                        latest_event="包裹已签收",
                        updated_at=now - timedelta(days=12),
                    ),
                ]
            )
            session.commit()

    def get_order(self, order_id: str, user_id: str) -> Order | None:
        with Session(self.engine) as session:
            row = session.scalar(
                select(OrderRow).where(OrderRow.order_id == order_id, OrderRow.user_id == user_id)
            )
            return _to_order(row) if row else None

    def list_orders(
        self, user_id: str | None = None, status: str | None = None, limit: int = 100
    ) -> list[Order]:
        statement = select(OrderRow)
        if user_id:
            statement = statement.where(OrderRow.user_id == user_id)
        if status:
            statement = statement.where(OrderRow.status == status)
        with Session(self.engine) as session:
            rows = session.scalars(statement.order_by(desc(OrderRow.created_at)).limit(limit)).all()
            return [_to_order(row) for row in rows]

    def get_logistics(self, order_id: str, user_id: str) -> Logistics | None:
        with Session(self.engine) as session:
            row = session.scalar(
                select(LogisticsRow)
                .join(OrderRow, LogisticsRow.order_id == OrderRow.order_id)
                .where(LogisticsRow.order_id == order_id, OrderRow.user_id == user_id)
            )
            return _to_logistics(row) if row else None

    def create_after_sale(
        self,
        *,
        order_id: str,
        user_id: str,
        reason: str,
        refundable_amount: float,
        idempotency_key: str,
        reviewer: str,
    ) -> AfterSaleTicket:
        existing = self.get_after_sale_by_key(idempotency_key)
        if existing:
            return existing
        row = AfterSaleRow(
            ticket_id=f"AS-{uuid4().hex[:12].upper()}",
            order_id=order_id,
            user_id=user_id,
            reason=reason,
            refundable_amount=refundable_amount,
            status=AfterSaleStatus.CREATED.value,
            idempotency_key=idempotency_key,
            reviewer=reviewer,
            created_at=datetime.now(),
        )
        try:
            with Session(self.engine) as session:
                session.add(row)
                session.commit()
                session.refresh(row)
                return _to_ticket(row)
        except IntegrityError:
            existing = self.get_after_sale_by_key(idempotency_key)
            if existing is None:
                raise
            return existing

    def get_after_sale_by_key(self, idempotency_key: str) -> AfterSaleTicket | None:
        with Session(self.engine) as session:
            row = session.scalar(
                select(AfterSaleRow).where(AfterSaleRow.idempotency_key == idempotency_key)
            )
            return _to_ticket(row) if row else None

    def list_after_sales(
        self, user_id: str | None = None, status: str | None = None, limit: int = 100
    ) -> list[AfterSaleTicket]:
        statement = select(AfterSaleRow)
        if user_id:
            statement = statement.where(AfterSaleRow.user_id == user_id)
        if status:
            statement = statement.where(AfterSaleRow.status == status)
        with Session(self.engine) as session:
            rows = session.scalars(
                statement.order_by(desc(AfterSaleRow.created_at)).limit(limit)
            ).all()
            return [_to_ticket(row) for row in rows]

    def add_audit(
        self,
        *,
        thread_id: str,
        user_id: str,
        action: str,
        resource: str,
        outcome: str,
        detail: str = "",
    ) -> AuditLog:
        with Session(self.engine) as session:
            row = AuditRow(
                thread_id=thread_id,
                user_id=user_id,
                action=action,
                resource=resource,
                outcome=outcome,
                detail=detail,
                created_at=datetime.now(),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_audit(row)

    def list_audits(self, limit: int = 100) -> list[AuditLog]:
        with Session(self.engine) as session:
            rows = session.scalars(select(AuditRow).order_by(desc(AuditRow.id)).limit(limit)).all()
            return [_to_audit(row) for row in rows]

    def upsert_conversation(
        self,
        *,
        thread_id: str,
        user_id: str,
        title: str,
        status: str,
        intent: str | None,
    ) -> Conversation:
        now = datetime.now()
        with Session(self.engine) as session:
            row = session.get(ConversationRow, thread_id)
            if row is None:
                row = ConversationRow(
                    thread_id=thread_id,
                    user_id=user_id,
                    title=title[:255],
                    status=status,
                    intent=intent,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.status = status
                row.intent = intent or row.intent
                row.updated_at = now
            session.commit()
            session.refresh(row)
            return _to_conversation(row)

    def add_message(
        self, *, thread_id: str, role: str, content: str, metadata_json: str = "{}"
    ) -> ChatMessage:
        with Session(self.engine) as session:
            row = ChatMessageRow(
                thread_id=thread_id,
                role=role,
                content=content,
                metadata_json=metadata_json,
                created_at=datetime.now(),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_message(row)

    def list_conversations(
        self, user_id: str | None = None, limit: int = 100
    ) -> list[Conversation]:
        statement = select(ConversationRow)
        if user_id:
            statement = statement.where(ConversationRow.user_id == user_id)
        with Session(self.engine) as session:
            rows = session.scalars(
                statement.order_by(desc(ConversationRow.updated_at)).limit(limit)
            ).all()
            return [_to_conversation(row) for row in rows]

    def list_messages(self, thread_id: str) -> list[ChatMessage]:
        with Session(self.engine) as session:
            rows = session.scalars(
                select(ChatMessageRow)
                .where(ChatMessageRow.thread_id == thread_id)
                .order_by(ChatMessageRow.id)
            ).all()
            return [_to_message(row) for row in rows]

    def upsert_approval(
        self,
        *,
        thread_id: str,
        user_id: str,
        order_id: str,
        action: str,
        amount: float,
        payload_json: str,
    ) -> ApprovalTask:
        with Session(self.engine) as session:
            row = session.get(ApprovalTaskRow, thread_id)
            if row is None:
                row = ApprovalTaskRow(
                    thread_id=thread_id,
                    user_id=user_id,
                    order_id=order_id,
                    action=action,
                    amount=amount,
                    status="pending",
                    payload_json=payload_json,
                    created_at=datetime.now(),
                )
                session.add(row)
                session.commit()
                session.refresh(row)
            return _to_approval(row)

    def decide_approval(
        self, *, thread_id: str, approved: bool, reviewer: str, reason: str
    ) -> ApprovalTask | None:
        with Session(self.engine) as session:
            row = session.get(ApprovalTaskRow, thread_id)
            if row is None:
                return None
            row.status = "approved" if approved else "rejected"
            row.reviewer = reviewer
            row.reason = reason
            row.decided_at = datetime.now()
            session.commit()
            session.refresh(row)
            return _to_approval(row)

    def list_approvals(self, status: str | None = None, limit: int = 100) -> list[ApprovalTask]:
        statement = select(ApprovalTaskRow)
        if status:
            statement = statement.where(ApprovalTaskRow.status == status)
        with Session(self.engine) as session:
            rows = session.scalars(
                statement.order_by(desc(ApprovalTaskRow.created_at)).limit(limit)
            ).all()
            return [_to_approval(row) for row in rows]


class InMemorySupportRepository:
    """Fast deterministic repository used by graph tests and examples."""

    def __init__(self):
        now = datetime.now()
        self.orders = {
            "ORD-1001": Order(
                order_id="ORD-1001",
                user_id="U1001",
                product_name="智能降噪耳机",
                amount=699,
                status=OrderStatus.DELIVERED,
                created_at=now - timedelta(days=10),
                delivered_at=now - timedelta(days=3),
            ),
            "ORD-1002": Order(
                order_id="ORD-1002",
                user_id="U1001",
                product_name="人体工学键盘",
                amount=399,
                status=OrderStatus.SHIPPED,
                created_at=now - timedelta(days=2),
            ),
            "ORD-2001": Order(
                order_id="ORD-2001",
                user_id="U2001",
                product_name="便携显示器",
                amount=1299,
                status=OrderStatus.DELIVERED,
                created_at=now - timedelta(days=20),
                delivered_at=now - timedelta(days=12),
            ),
        }
        self.logistics = {
            "ORD-1001": Logistics(
                order_id="ORD-1001",
                carrier="顺丰速运",
                tracking_no="SF-DEMO-1001",
                status="已签收",
                latest_event="包裹已由本人签收",
                updated_at=now - timedelta(days=3),
            ),
            "ORD-1002": Logistics(
                order_id="ORD-1002",
                carrier="京东物流",
                tracking_no="JD-DEMO-1002",
                status="运输中",
                latest_event="包裹已到达成都分拨中心",
                updated_at=now - timedelta(hours=2),
            ),
        }
        self.tickets: dict[str, AfterSaleTicket] = {}
        self.audits: list[AuditLog] = []
        self.conversations: dict[str, Conversation] = {}
        self.messages: list[ChatMessage] = []
        self.approvals: dict[str, ApprovalTask] = {}
        self._lock = Lock()

    def healthcheck(self) -> bool:
        return True

    def get_order(self, order_id: str, user_id: str) -> Order | None:
        order = self.orders.get(order_id)
        return order if order and order.user_id == user_id else None

    def list_orders(
        self, user_id: str | None = None, status: str | None = None, limit: int = 100
    ) -> list[Order]:
        values = [
            item
            for item in self.orders.values()
            if (not user_id or item.user_id == user_id)
            and (not status or item.status.value == status)
        ]
        return sorted(values, key=lambda item: item.created_at, reverse=True)[:limit]

    def get_logistics(self, order_id: str, user_id: str) -> Logistics | None:
        if self.get_order(order_id, user_id) is None:
            return None
        return self.logistics.get(order_id)

    def create_after_sale(
        self,
        *,
        order_id: str,
        user_id: str,
        reason: str,
        refundable_amount: float,
        idempotency_key: str,
        reviewer: str,
    ) -> AfterSaleTicket:
        with self._lock:
            if idempotency_key in self.tickets:
                return self.tickets[idempotency_key]
            ticket = AfterSaleTicket(
                ticket_id=f"AS-{uuid4().hex[:12].upper()}",
                order_id=order_id,
                user_id=user_id,
                reason=reason,
                refundable_amount=refundable_amount,
                status=AfterSaleStatus.CREATED,
                idempotency_key=idempotency_key,
                reviewer=reviewer,
                created_at=datetime.now(),
            )
            self.tickets[idempotency_key] = ticket
            return ticket

    def get_after_sale_by_key(self, idempotency_key: str) -> AfterSaleTicket | None:
        return self.tickets.get(idempotency_key)

    def list_after_sales(
        self, user_id: str | None = None, status: str | None = None, limit: int = 100
    ) -> list[AfterSaleTicket]:
        values = [
            item
            for item in self.tickets.values()
            if (not user_id or item.user_id == user_id)
            and (not status or item.status.value == status)
        ]
        return sorted(values, key=lambda item: item.created_at, reverse=True)[:limit]

    def add_audit(
        self,
        *,
        thread_id: str,
        user_id: str,
        action: str,
        resource: str,
        outcome: str,
        detail: str = "",
    ) -> AuditLog:
        audit = AuditLog(
            id=len(self.audits) + 1,
            thread_id=thread_id,
            user_id=user_id,
            action=action,
            resource=resource,
            outcome=outcome,
            detail=detail,
            created_at=datetime.now(),
        )
        self.audits.append(audit)
        return audit

    def list_audits(self, limit: int = 100) -> list[AuditLog]:
        return list(reversed(self.audits[-limit:]))

    def upsert_conversation(
        self,
        *,
        thread_id: str,
        user_id: str,
        title: str,
        status: str,
        intent: str | None,
    ) -> Conversation:
        now = datetime.now()
        existing = self.conversations.get(thread_id)
        conversation = Conversation(
            thread_id=thread_id,
            user_id=user_id,
            title=existing.title if existing else title[:255],
            status=status,
            intent=intent or (existing.intent if existing else None),
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        self.conversations[thread_id] = conversation
        return conversation

    def add_message(
        self, *, thread_id: str, role: str, content: str, metadata_json: str = "{}"
    ) -> ChatMessage:
        message = ChatMessage(
            id=len(self.messages) + 1,
            thread_id=thread_id,
            role=role,
            content=content,
            metadata_json=metadata_json,
            created_at=datetime.now(),
        )
        self.messages.append(message)
        return message

    def list_conversations(
        self, user_id: str | None = None, limit: int = 100
    ) -> list[Conversation]:
        values = [
            item for item in self.conversations.values() if not user_id or item.user_id == user_id
        ]
        return sorted(values, key=lambda item: item.updated_at, reverse=True)[:limit]

    def list_messages(self, thread_id: str) -> list[ChatMessage]:
        return [item for item in self.messages if item.thread_id == thread_id]

    def upsert_approval(
        self,
        *,
        thread_id: str,
        user_id: str,
        order_id: str,
        action: str,
        amount: float,
        payload_json: str,
    ) -> ApprovalTask:
        existing = self.approvals.get(thread_id)
        if existing:
            return existing
        task = ApprovalTask(
            thread_id=thread_id,
            user_id=user_id,
            order_id=order_id,
            action=action,
            amount=amount,
            status="pending",
            payload_json=payload_json,
            created_at=datetime.now(),
        )
        self.approvals[thread_id] = task
        return task

    def decide_approval(
        self, *, thread_id: str, approved: bool, reviewer: str, reason: str
    ) -> ApprovalTask | None:
        existing = self.approvals.get(thread_id)
        if existing is None:
            return None
        task = existing.model_copy(
            update={
                "status": "approved" if approved else "rejected",
                "reviewer": reviewer,
                "reason": reason,
                "decided_at": datetime.now(),
            }
        )
        self.approvals[thread_id] = task
        return task

    def list_approvals(self, status: str | None = None, limit: int = 100) -> list[ApprovalTask]:
        values = [item for item in self.approvals.values() if not status or item.status == status]
        return sorted(values, key=lambda item: item.created_at, reverse=True)[:limit]
