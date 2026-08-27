from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.infrastructure.repository import SQLAlchemySupportRepository
from app.tools.commerce import CommerceTools

settings = get_settings()
repository = SQLAlchemySupportRepository(settings.database_url)
if settings.environment == "production":
    repository.assert_schema_revision("0003")
else:
    repository.init_schema()
if settings.seed_demo_data:
    repository.seed_demo_data()
commerce = CommerceTools(repository)
mcp = FastMCP(
    "ecommerce-after-sales",
    host=settings.mcp_server_host,
    port=settings.mcp_server_port,
    json_response=True,
)


@mcp.tool()
def get_order(order_id: str, user_id: str, thread_id: str) -> dict:
    """查询当前用户本人的订单。"""
    return commerce.get_order(order_id, user_id, thread_id)


@mcp.tool()
def get_logistics(order_id: str, user_id: str, thread_id: str) -> dict:
    """查询当前用户本人的物流轨迹。"""
    return commerce.get_logistics(order_id, user_id, thread_id)


@mcp.tool()
def check_refund_eligibility(order_id: str, user_id: str, thread_id: str, reason: str) -> dict:
    """根据订单和售后规则判断退款资格。"""
    return commerce.check_refund_eligibility(order_id, user_id, thread_id, reason)


@mcp.tool()
def create_after_sale(
    order_id: str,
    user_id: str,
    thread_id: str,
    reason: str,
    refundable_amount: float,
    approved: bool,
    reviewer: str,
    idempotency_key: str,
) -> dict:
    """人工审批后，以幂等方式创建售后工单。"""
    return commerce.create_after_sale(
        order_id=order_id,
        user_id=user_id,
        thread_id=thread_id,
        reason=reason,
        refundable_amount=refundable_amount,
        approved=approved,
        reviewer=reviewer,
        idempotency_key=idempotency_key,
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
