from datetime import datetime

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.domain.models import RefundEligibility
from app.domain.repositories import SupportRepository


class OrderQuery(BaseModel):
    order_id: str = Field(pattern=r"^ORD-\d{4,}$")
    user_id: str = Field(min_length=2, max_length=32)
    thread_id: str = Field(min_length=1, max_length=64)


class RefundCheckInput(OrderQuery):
    reason: str = Field(min_length=2, max_length=500)


class CreateAfterSaleInput(RefundCheckInput):
    refundable_amount: float = Field(ge=0)
    approved: bool
    reviewer: str = Field(min_length=2, max_length=64)
    idempotency_key: str = Field(min_length=8, max_length=128)


class CommerceTools:
    def __init__(self, repository: SupportRepository):
        self.repository = repository

    def get_order(self, order_id: str, user_id: str, thread_id: str) -> dict:
        order = self.repository.get_order(order_id, user_id)
        outcome = "success" if order else "not_found_or_forbidden"
        self.repository.add_audit(
            thread_id=thread_id,
            user_id=user_id,
            action="get_order",
            resource=order_id,
            outcome=outcome,
        )
        if order is None:
            raise PermissionError("订单不存在，或当前用户无权访问该订单")
        return order.model_dump(mode="json")

    def get_logistics(self, order_id: str, user_id: str, thread_id: str) -> dict:
        logistics = self.repository.get_logistics(order_id, user_id)
        outcome = "success" if logistics else "not_found_or_forbidden"
        self.repository.add_audit(
            thread_id=thread_id,
            user_id=user_id,
            action="get_logistics",
            resource=order_id,
            outcome=outcome,
        )
        if logistics is None:
            raise PermissionError("物流不存在，或当前用户无权访问该订单")
        return logistics.model_dump(mode="json")

    def check_refund_eligibility(
        self, order_id: str, user_id: str, thread_id: str, reason: str
    ) -> dict:
        order = self.repository.get_order(order_id, user_id)
        if order is None:
            self.repository.add_audit(
                thread_id=thread_id,
                user_id=user_id,
                action="check_refund_eligibility",
                resource=order_id,
                outcome="not_found_or_forbidden",
            )
            raise PermissionError("订单不存在，或当前用户无权访问该订单")

        if order.status.value == "delivered" and order.delivered_at:
            elapsed = (datetime.now() - order.delivered_at).days
            eligible = elapsed <= 7
            explanation = (
                f"订单签收后已过 {elapsed} 天，{'符合' if eligible else '超过'}7天退货时限"
            )
        elif order.status.value in {"paid", "shipped"}:
            eligible = True
            explanation = "订单尚未签收，可申请拦截或退款，由客服确认物流状态"
        else:
            eligible = False
            explanation = "订单已关闭，不支持自动发起退款"

        result = RefundEligibility(
            eligible=eligible,
            reason=explanation,
            refundable_amount=order.amount if eligible else 0,
            policy_reference="refund_policy.md#七天无理由退货",
        )
        self.repository.add_audit(
            thread_id=thread_id,
            user_id=user_id,
            action="check_refund_eligibility",
            resource=order_id,
            outcome="eligible" if eligible else "ineligible",
            detail=reason,
        )
        return result.model_dump(mode="json")

    def create_after_sale(
        self,
        order_id: str,
        user_id: str,
        thread_id: str,
        reason: str,
        refundable_amount: float,
        approved: bool,
        reviewer: str,
        idempotency_key: str,
    ) -> dict:
        if not approved:
            raise PermissionError("敏感写操作必须先通过人工审批")
        if self.repository.get_order(order_id, user_id) is None:
            raise PermissionError("订单不存在，或当前用户无权访问该订单")
        ticket = self.repository.create_after_sale(
            order_id=order_id,
            user_id=user_id,
            reason=reason,
            refundable_amount=refundable_amount,
            idempotency_key=idempotency_key,
            reviewer=reviewer,
        )
        self.repository.add_audit(
            thread_id=thread_id,
            user_id=user_id,
            action="create_after_sale",
            resource=ticket.ticket_id,
            outcome="success",
            detail=f"reviewer={reviewer}; idempotency_key={idempotency_key}",
        )
        return ticket.model_dump(mode="json")

    def as_langchain_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool.from_function(
                self.get_order, name="get_order", description="查询当前用户本人的订单详情"
            ),
            StructuredTool.from_function(
                self.get_logistics, name="get_logistics", description="查询当前用户本人的物流轨迹"
            ),
            StructuredTool.from_function(
                self.check_refund_eligibility,
                name="check_refund_eligibility",
                description="根据订单状态和政策判断退款资格",
            ),
            StructuredTool.from_function(
                self.create_after_sale,
                name="create_after_sale",
                description="仅在人工审批后幂等创建售后工单",
            ),
        ]
