from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import and_, insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.infrastructure.enterprise_models import (
    after_sale_cases,
    after_sale_status_history,
    approval_records,
    compensation_records,
    exchange_orders,
    idempotency_records,
    notifications,
    outbox_events,
    refund_attempts,
    refund_events,
    refunds,
    repair_orders,
    reshipment_orders,
    return_inspections,
    return_shipments,
    returns,
)
from app.infrastructure.repository import OrderRow

CASE_TYPES = {
    "refund_only",
    "return_refund",
    "exchange",
    "reshipment",
    "repair",
    "compensation",
    "appeal",
}

TERMINAL_STATUSES = {"completed", "rejected", "cancelled"}

CASE_TRANSITIONS = {
    "submitted": {"under_review", "pending_approval", "cancelled"},
    "under_review": {"pending_approval", "approved", "rejected", "cancelled"},
    "pending_approval": {"approved", "rejected", "cancelled"},
    "approved": {"awaiting_customer_return", "processing", "cancelled"},
    "awaiting_customer_return": {"awaiting_receipt", "cancelled"},
    "awaiting_receipt": {"processing", "rejected"},
    "processing": {"completed", "rejected"},
}


class AfterSalesError(Exception):
    pass


class NotFoundError(AfterSalesError):
    pass


class ConflictError(AfterSalesError):
    pass


class ValidationError(AfterSalesError):
    pass


@dataclass(frozen=True)
class RefundGatewayResult:
    successful: bool
    provider_refund_no: str | None
    raw_response: dict[str, Any]
    error_code: str | None = None
    error_message: str | None = None


class RefundGateway(Protocol):
    name: str

    def refund(
        self, *, refund_no: str, amount: Decimal, currency: str, request_id: str
    ) -> RefundGatewayResult: ...


class SandboxRefundGateway:
    """Deterministic local gateway; replace through the RefundGateway port in production."""

    name = "sandbox"

    def refund(
        self, *, refund_no: str, amount: Decimal, currency: str, request_id: str
    ) -> RefundGatewayResult:
        return RefundGatewayResult(
            successful=True,
            provider_refund_no=f"SBX-{refund_no}",
            raw_response={
                "request_id": request_id,
                "refund_no": refund_no,
                "amount": str(amount),
                "currency": currency,
                "status": "succeeded",
            },
        )


def _now() -> datetime:
    return datetime.now()


def _public_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _business_no(prefix: str) -> str:
    return f"{prefix}{_now():%Y%m%d%H%M%S}{uuid4().hex[:6].upper()}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _json_hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _serialize(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    result: dict[str, Any] = {}
    for key, value in row._mapping.items():
        if isinstance(value, Decimal):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


class AfterSalesService:
    def __init__(self, engine: Engine, refund_gateway: RefundGateway | None = None):
        self.engine = engine
        self.refund_gateway = refund_gateway or SandboxRefundGateway()

    def create_case(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        actor_role: str,
        order_id: str,
        customer_id: str,
        case_type: str,
        reason_code: str | None,
        reason: str,
        requested_amount: Decimal | None,
        priority: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if case_type not in CASE_TYPES:
            raise ValidationError("不支持的售后类型")
        request_body = {
            "order_id": order_id,
            "customer_id": customer_id,
            "case_type": case_type,
            "reason_code": reason_code,
            "reason": reason,
            "requested_amount": str(requested_amount) if requested_amount is not None else None,
            "priority": priority,
        }
        request_hash = _json_hash(request_body)
        now = _now()
        with Session(self.engine) as session, session.begin():
            previous = session.execute(
                select(idempotency_records).where(
                    idempotency_records.c.tenant_id == tenant_id,
                    idempotency_records.c.scope == "after_sale.create",
                    idempotency_records.c.idempotency_key == idempotency_key,
                )
            ).first()
            if previous:
                if previous.request_hash != request_hash:
                    raise ConflictError("相同幂等键对应了不同请求")
                return json.loads(previous.response_json)

            order = session.scalar(select(OrderRow).where(OrderRow.order_id == order_id))
            if order is None:
                raise NotFoundError("订单不存在")
            if actor_role == "customer" and order.user_id != actor_id:
                raise NotFoundError("订单不存在，或当前账号无权访问")
            if customer_id != order.user_id:
                raise ValidationError("售后申请人与订单所属用户不一致")
            if requested_amount is not None:
                if requested_amount <= 0:
                    raise ValidationError("申请金额必须大于 0")
                if requested_amount > Decimal(str(order.amount)):
                    raise ValidationError("申请金额不能超过订单实付金额")
            if case_type in {"refund_only", "return_refund", "compensation"} and (
                requested_amount is None
            ):
                raise ValidationError("该售后类型必须填写申请金额")

            case_id = _public_id("case")
            values = {
                "case_id": case_id,
                "tenant_id": tenant_id,
                "case_no": _business_no("AS"),
                "order_id": order_id,
                "customer_id": customer_id,
                "case_type": case_type,
                "source": "portal",
                "reason_code": reason_code,
                "reason": reason,
                "requested_amount": requested_amount,
                "approved_amount": None,
                "currency": "CNY",
                "status": "submitted",
                "priority": priority,
                "assignee_id": None,
                "sla_due_at": now + timedelta(hours=24 if priority == "urgent" else 72),
                "closed_at": None,
                "version": 1,
                "created_at": now,
                "updated_at": now,
            }
            session.execute(insert(after_sale_cases).values(**values))
            self._record_status(
                session,
                tenant_id=tenant_id,
                case_id=case_id,
                from_status=None,
                to_status="submitted",
                actor_id=actor_id,
                reason="创建售后申请",
            )
            self._emit_case_event(session, values, "after_sale.case.created")
            response = self._get_case(session, tenant_id, case_id)
            session.execute(
                insert(idempotency_records).values(
                    record_id=_public_id("idem"),
                    tenant_id=tenant_id,
                    scope="after_sale.create",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    status="completed",
                    response_code=201,
                    response_json=_json(response),
                    expires_at=now + timedelta(days=1),
                    created_at=now,
                    updated_at=now,
                )
            )
            return response

    def list_cases(
        self,
        *,
        tenant_id: str,
        customer_id: str | None,
        status: str | None,
        case_type: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        filters = [after_sale_cases.c.tenant_id == tenant_id]
        if customer_id:
            filters.append(after_sale_cases.c.customer_id == customer_id)
        if status:
            filters.append(after_sale_cases.c.status == status)
        if case_type:
            filters.append(after_sale_cases.c.case_type == case_type)
        with Session(self.engine) as session:
            rows = session.execute(
                select(after_sale_cases)
                .where(and_(*filters))
                .order_by(after_sale_cases.c.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
            return {"items": [_serialize(row) for row in rows], "limit": limit, "offset": offset}

    def get_case(
        self, *, tenant_id: str, case_id: str, customer_id: str | None = None
    ) -> dict[str, Any]:
        with Session(self.engine) as session:
            result = self._get_case(session, tenant_id, case_id)
            if customer_id and result["customer_id"] != customer_id:
                raise NotFoundError("售后单不存在")
            return result

    def review_case(
        self,
        *,
        tenant_id: str,
        case_id: str,
        actor_id: str,
        approved: bool,
        approved_amount: Decimal | None,
        reason: str,
    ) -> dict[str, Any]:
        with Session(self.engine) as session, session.begin():
            case = self._case_row(session, tenant_id, case_id)
            if case.status not in {"submitted", "under_review", "pending_approval"}:
                raise ConflictError("当前状态不能审批")
            if case.status == "submitted":
                self._set_case_status(
                    session,
                    case,
                    "under_review",
                    actor_id=actor_id,
                    reason="审批人开始审核",
                )
                case = self._case_row(session, tenant_id, case_id)
            amount = approved_amount if approved_amount is not None else case.requested_amount
            if approved and amount is not None and amount > case.requested_amount:
                raise ValidationError("批准金额不能超过申请金额")
            target_status = "approved" if approved else "rejected"
            session.execute(
                insert(approval_records).values(
                    record_id=_public_id("approval"),
                    tenant_id=tenant_id,
                    task_thread_id=case_id,
                    step_no=1,
                    action="approve" if approved else "reject",
                    actor_id=actor_id,
                    reason=reason,
                    snapshot_json=_json(_serialize(case)),
                    created_at=_now(),
                )
            )
            self._set_case_status(
                session,
                case,
                target_status,
                actor_id=actor_id,
                reason=reason or ("审批通过" if approved else "审批拒绝"),
                extra_values={"approved_amount": amount},
            )
            if approved:
                self._materialize_fulfillment(session, case, amount)
            return self._get_case(session, tenant_id, case_id)

    def ship_return(
        self,
        *,
        tenant_id: str,
        case_id: str,
        actor_id: str,
        customer_id: str | None,
        carrier: str,
        tracking_no: str,
    ) -> dict[str, Any]:
        now = _now()
        with Session(self.engine) as session, session.begin():
            case = self._case_row(session, tenant_id, case_id)
            if customer_id and case.customer_id != customer_id:
                raise NotFoundError("售后单不存在")
            return_row = session.execute(
                select(returns).where(
                    returns.c.tenant_id == tenant_id, returns.c.case_id == case_id
                )
            ).first()
            if not return_row or return_row.status != "awaiting_shipment":
                raise ConflictError("当前售后单不接受退货物流")
            session.execute(
                insert(return_shipments).values(
                    return_shipment_id=_public_id("rship"),
                    tenant_id=tenant_id,
                    return_id=return_row.return_id,
                    carrier=carrier,
                    tracking_no=tracking_no,
                    status="in_transit",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.execute(
                update(returns)
                .where(returns.c.return_id == return_row.return_id)
                .values(status="in_transit", shipped_at=now, updated_at=now)
            )
            self._set_case_status(
                session,
                case,
                "awaiting_receipt",
                actor_id=actor_id,
                reason=f"客户已寄回：{carrier} {tracking_no}",
            )
            return self._get_case(session, tenant_id, case_id)

    def inspect_return(
        self,
        *,
        tenant_id: str,
        case_id: str,
        actor_id: str,
        accepted: bool,
        notes: str,
        deduction_amount: Decimal | None,
    ) -> dict[str, Any]:
        now = _now()
        with Session(self.engine) as session, session.begin():
            case = self._case_row(session, tenant_id, case_id)
            return_row = session.execute(
                select(returns).where(
                    returns.c.tenant_id == tenant_id, returns.c.case_id == case_id
                )
            ).first()
            if not return_row or return_row.status not in {"in_transit", "received"}:
                raise ConflictError("退货尚未进入可验收状态")
            session.execute(
                insert(return_inspections).values(
                    inspection_id=_public_id("inspect"),
                    tenant_id=tenant_id,
                    return_id=return_row.return_id,
                    inspector_id=actor_id,
                    result="accepted" if accepted else "rejected",
                    deduction_amount=deduction_amount,
                    notes=notes,
                    evidence_json="[]",
                    inspected_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.execute(
                update(returns)
                .where(returns.c.return_id == return_row.return_id)
                .values(
                    status="accepted" if accepted else "rejected", received_at=now, updated_at=now
                )
            )
            target = "processing" if accepted else "rejected"
            self._set_case_status(
                session,
                case,
                target,
                actor_id=actor_id,
                reason=notes or ("退货验收通过" if accepted else "退货验收拒绝"),
            )
            if accepted and case.case_type == "return_refund":
                amount = Decimal(case.approved_amount or case.requested_amount or 0)
                if deduction_amount:
                    amount -= deduction_amount
                if amount <= 0:
                    raise ValidationError("扣减后退款金额必须大于 0")
                self._create_refund(session, case, amount)
            elif accepted and case.case_type == "exchange":
                session.execute(
                    update(exchange_orders)
                    .where(exchange_orders.c.case_id == case_id)
                    .values(status="ready_to_ship", updated_at=now)
                )
            elif accepted and case.case_type == "repair":
                session.execute(
                    update(repair_orders)
                    .where(repair_orders.c.case_id == case_id)
                    .values(status="repairing", updated_at=now)
                )
            return self._get_case(session, tenant_id, case_id)

    def execute_refund(
        self,
        *,
        tenant_id: str,
        case_id: str,
        refund_id: str,
        actor_id: str,
    ) -> dict[str, Any]:
        now = _now()
        with Session(self.engine) as session, session.begin():
            case = self._case_row(session, tenant_id, case_id)
            refund = session.execute(
                select(refunds).where(
                    refunds.c.tenant_id == tenant_id,
                    refunds.c.case_id == case_id,
                    refunds.c.refund_id == refund_id,
                )
            ).first()
            if not refund:
                raise NotFoundError("退款单不存在")
            if refund.status == "succeeded":
                return self._get_case(session, tenant_id, case_id)
            if refund.status not in {"pending", "failed"}:
                raise ConflictError("当前退款状态不可执行")
            attempt_count = session.scalar(
                select(refund_attempts.c.attempt_no)
                .where(refund_attempts.c.refund_id == refund_id)
                .order_by(refund_attempts.c.attempt_no.desc())
                .limit(1)
            )
            attempt_no = (attempt_count or 0) + 1
            request_id = _public_id("refund-request")
            result = self.refund_gateway.refund(
                refund_no=refund.refund_no,
                amount=Decimal(refund.amount),
                currency=refund.currency,
                request_id=request_id,
            )
            target = "succeeded" if result.successful else "failed"
            session.execute(
                insert(refund_attempts).values(
                    attempt_id=_public_id("attempt"),
                    tenant_id=tenant_id,
                    refund_id=refund_id,
                    attempt_no=attempt_no,
                    request_id=request_id,
                    status=target,
                    request_json=_json({"amount": str(refund.amount), "currency": refund.currency}),
                    response_json=_json(result.raw_response),
                    error_code=result.error_code,
                    error_message=result.error_message,
                    started_at=now,
                    finished_at=_now(),
                )
            )
            session.execute(
                update(refunds)
                .where(refunds.c.refund_id == refund_id)
                .values(
                    status=target,
                    provider_refund_no=result.provider_refund_no,
                    failure_code=result.error_code,
                    failure_message=result.error_message,
                    processed_at=_now(),
                    updated_at=_now(),
                    version=refund.version + 1,
                )
            )
            session.execute(
                insert(refund_events).values(
                    event_id=_public_id("refund-event"),
                    tenant_id=tenant_id,
                    refund_id=refund_id,
                    event_type="refund.succeeded" if result.successful else "refund.failed",
                    from_status=refund.status,
                    to_status=target,
                    actor_type="user",
                    actor_id=actor_id,
                    payload_json=_json(result.raw_response),
                    created_at=_now(),
                )
            )
            if result.successful:
                self._set_case_status(
                    session,
                    case,
                    "completed",
                    actor_id=actor_id,
                    reason="退款网关处理成功",
                )
            return self._get_case(session, tenant_id, case_id)

    def complete_fulfillment(
        self, *, tenant_id: str, case_id: str, actor_id: str, notes: str
    ) -> dict[str, Any]:
        with Session(self.engine) as session, session.begin():
            case = self._case_row(session, tenant_id, case_id)
            if case.status not in {"approved", "processing"}:
                raise ConflictError("当前售后单不能完成履约")
            table = {
                "exchange": exchange_orders,
                "reshipment": reshipment_orders,
                "repair": repair_orders,
            }.get(case.case_type)
            if table is not None:
                session.execute(
                    update(table)
                    .where(table.c.case_id == case_id)
                    .values(status="completed", completed_at=_now(), updated_at=_now())
                )
            if case.case_type == "compensation":
                session.execute(
                    update(compensation_records)
                    .where(compensation_records.c.case_id == case_id)
                    .values(status="completed", updated_at=_now())
                )
            self._set_case_status(
                session,
                case,
                "completed",
                actor_id=actor_id,
                reason=notes or "售后履约完成",
            )
            return self._get_case(session, tenant_id, case_id)

    def _materialize_fulfillment(self, session: Session, case: Any, amount: Decimal | None) -> None:
        now = _now()
        if case.case_type == "refund_only":
            self._create_refund(session, case, Decimal(amount or 0))
            self._set_case_status(
                session,
                self._case_row(session, case.tenant_id, case.case_id),
                "processing",
                actor_id="system",
                reason="退款单已创建，等待支付网关处理",
            )
            return
        if case.case_type in {"return_refund", "exchange", "repair"}:
            session.execute(
                insert(returns).values(
                    return_id=_public_id("return"),
                    tenant_id=case.tenant_id,
                    case_id=case.case_id,
                    return_no=_business_no("RT"),
                    status="awaiting_shipment",
                    return_address_json=_json({"warehouse": "default"}),
                    shipped_at=None,
                    received_at=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            if case.case_type == "exchange":
                self._create_fulfillment_row(session, exchange_orders, "exchange_id", case)
            elif case.case_type == "repair":
                self._create_fulfillment_row(session, repair_orders, "repair_id", case)
            self._set_case_status(
                session,
                self._case_row(session, case.tenant_id, case.case_id),
                "awaiting_customer_return",
                actor_id="system",
                reason="等待客户寄回商品",
            )
            return
        if case.case_type == "reshipment":
            self._create_fulfillment_row(session, reshipment_orders, "reshipment_id", case)
        elif case.case_type == "compensation":
            session.execute(
                insert(compensation_records).values(
                    compensation_id=_public_id("compensation"),
                    tenant_id=case.tenant_id,
                    case_id=case.case_id,
                    compensation_type="cash",
                    amount=amount,
                    currency=case.currency,
                    status="approved",
                    external_reference=None,
                    created_at=now,
                    updated_at=now,
                )
            )
        self._set_case_status(
            session,
            self._case_row(session, case.tenant_id, case.case_id),
            "processing",
            actor_id="system",
            reason="开始售后履约",
        )

    @staticmethod
    def _create_fulfillment_row(session: Session, table: Any, id_column: str, case: Any) -> None:
        now = _now()
        session.execute(
            insert(table).values(
                **{
                    id_column: _public_id(id_column.removesuffix("_id")),
                    "tenant_id": case.tenant_id,
                    "case_id": case.case_id,
                    "status": "pending_return"
                    if case.case_type in {"exchange", "repair"}
                    else "ready_to_ship",
                    "payload_json": "{}",
                    "completed_at": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        )

    def _create_refund(self, session: Session, case: Any, amount: Decimal) -> None:
        if amount <= 0:
            raise ValidationError("退款金额必须大于 0")
        now = _now()
        refund_id = _public_id("refund")
        session.execute(
            insert(refunds).values(
                refund_id=refund_id,
                tenant_id=case.tenant_id,
                case_id=case.case_id,
                payment_id=None,
                refund_no=_business_no("RF"),
                provider=self.refund_gateway.name,
                amount=amount,
                currency=case.currency,
                status="pending",
                idempotency_key=f"case:{case.case_id}",
                provider_refund_no=None,
                failure_code=None,
                failure_message=None,
                version=1,
                processed_at=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            insert(refund_events).values(
                event_id=_public_id("refund-event"),
                tenant_id=case.tenant_id,
                refund_id=refund_id,
                event_type="refund.created",
                from_status=None,
                to_status="pending",
                actor_type="system",
                actor_id="system",
                payload_json=_json({"case_id": case.case_id, "amount": str(amount)}),
                created_at=now,
            )
        )

    def _set_case_status(
        self,
        session: Session,
        case: Any,
        target_status: str,
        *,
        actor_id: str,
        reason: str,
        extra_values: dict[str, Any] | None = None,
    ) -> None:
        if target_status not in CASE_TRANSITIONS.get(case.status, set()):
            raise ConflictError(f"不允许从 {case.status} 变更为 {target_status}")
        now = _now()
        values = {
            "status": target_status,
            "updated_at": now,
            "version": case.version + 1,
            "closed_at": now if target_status in TERMINAL_STATUSES else None,
            **(extra_values or {}),
        }
        result = session.execute(
            update(after_sale_cases)
            .where(
                after_sale_cases.c.case_id == case.case_id,
                after_sale_cases.c.tenant_id == case.tenant_id,
                after_sale_cases.c.version == case.version,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            raise ConflictError("售后单已被其他操作更新，请刷新后重试")
        self._record_status(
            session,
            tenant_id=case.tenant_id,
            case_id=case.case_id,
            from_status=case.status,
            to_status=target_status,
            actor_id=actor_id,
            reason=reason,
        )
        payload = {**_serialize(case), **values}
        self._emit_case_event(session, payload, "after_sale.case.status_changed")

    @staticmethod
    def _record_status(
        session: Session,
        *,
        tenant_id: str,
        case_id: str,
        from_status: str | None,
        to_status: str,
        actor_id: str,
        reason: str,
    ) -> None:
        session.execute(
            insert(after_sale_status_history).values(
                history_id=_public_id("history"),
                tenant_id=tenant_id,
                case_id=case_id,
                from_status=from_status,
                to_status=to_status,
                actor_type="system" if actor_id == "system" else "user",
                actor_id=actor_id,
                reason=reason,
                payload_json="{}",
                created_at=_now(),
            )
        )

    @staticmethod
    def _emit_case_event(session: Session, case: dict[str, Any], event_type: str) -> None:
        now = _now()
        session.execute(
            insert(outbox_events).values(
                event_id=_public_id("event"),
                tenant_id=case["tenant_id"],
                aggregate_type="after_sale_case",
                aggregate_id=case["case_id"],
                event_type=event_type,
                payload_json=_json(case),
                status="pending",
                available_at=now,
                attempts=0,
                last_error=None,
                processed_at=None,
                created_at=now,
            )
        )
        session.execute(
            insert(notifications).values(
                notification_id=_public_id("notification"),
                tenant_id=case["tenant_id"],
                recipient_id=case.get("customer_id") or "operations",
                channel="in_app",
                template_code=event_type,
                subject="售后进度更新",
                payload_json=_json({"case_id": case["case_id"], "status": case.get("status")}),
                status="unread",
                read_at=None,
                created_at=now,
                updated_at=now,
            )
        )

    @staticmethod
    def _case_row(session: Session, tenant_id: str, case_id: str) -> Any:
        row = session.execute(
            select(after_sale_cases).where(
                after_sale_cases.c.tenant_id == tenant_id,
                after_sale_cases.c.case_id == case_id,
            )
        ).first()
        if not row:
            raise NotFoundError("售后单不存在")
        return row

    def _get_case(self, session: Session, tenant_id: str, case_id: str) -> dict[str, Any]:
        case = self._case_row(session, tenant_id, case_id)
        result = _serialize(case)
        related = {
            "history": after_sale_status_history,
            "refunds": refunds,
            "returns": returns,
            "exchanges": exchange_orders,
            "reshipments": reshipment_orders,
            "repairs": repair_orders,
            "compensations": compensation_records,
        }
        for key, table in related.items():
            rows = session.execute(
                select(table).where(table.c.tenant_id == tenant_id, table.c.case_id == case_id)
            ).all()
            result[key] = [_serialize(row) for row in rows]
        return result
