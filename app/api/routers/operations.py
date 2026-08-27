from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import enforce_customer_scope, safe_limit
from app.api.schemas import ApprovalRequest, ChatResponse
from app.services.auth import Identity, current_identity, require_role

router = APIRouter(tags=["operations"])


@router.post("/approvals/{thread_id}", response_model=ChatResponse)
def approve(
    thread_id: str,
    payload: ApprovalRequest,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    require_role(identity, "approver", "admin")
    try:
        return request.app.state.after_sales_graph.resume(
            thread_id=thread_id,
            approved=payload.approved,
            reviewer=payload.reviewer,
            reason=payload.reason,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="审批线程不存在或已结束") from exc


@router.get("/approvals")
def approval_tasks(
    request: Request,
    status: str | None = None,
    limit: int = 100,
    identity: Identity = Depends(current_identity),
) -> list[dict[str, Any]]:
    require_role(identity, "approver", "admin")
    tasks = request.app.state.repository.list_approvals(status=status, limit=safe_limit(limit))
    return [item.model_dump(mode="json") for item in tasks]


@router.get("/orders")
def orders(
    request: Request,
    user_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
    identity: Identity = Depends(current_identity),
) -> list[dict[str, Any]]:
    trusted_user_id = enforce_customer_scope(request, identity, user_id)
    values = request.app.state.repository.list_orders(trusted_user_id, status, safe_limit(limit))
    return [item.model_dump(mode="json") for item in values]


@router.get("/orders/{order_id}")
def get_order(
    order_id: str,
    user_id: str,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    trusted_user_id = enforce_customer_scope(request, identity, user_id)
    order = request.app.state.repository.get_order(order_id, trusted_user_id or user_id)
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在，或当前用户无权访问")
    return order.model_dump(mode="json")


@router.get("/after-sales")
def after_sales(
    request: Request,
    user_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
    identity: Identity = Depends(current_identity),
) -> list[dict[str, Any]]:
    trusted_user_id = enforce_customer_scope(request, identity, user_id)
    values = request.app.state.repository.list_after_sales(
        trusted_user_id, status, safe_limit(limit)
    )
    return [item.model_dump(mode="json") for item in values]


@router.get("/conversations")
def conversations(
    request: Request,
    user_id: str | None = None,
    limit: int = 100,
    identity: Identity = Depends(current_identity),
) -> list[dict[str, Any]]:
    trusted_user_id = enforce_customer_scope(request, identity, user_id)
    values = request.app.state.repository.list_conversations(trusted_user_id, safe_limit(limit))
    return [item.model_dump(mode="json") for item in values]


@router.get("/conversations/{thread_id}/messages")
def conversation_messages(
    thread_id: str,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> list[dict[str, Any]]:
    if identity.role == "customer":
        allowed = request.app.state.repository.list_conversations(identity.user_id, 500)
        if thread_id not in {item.thread_id for item in allowed}:
            raise HTTPException(status_code=404, detail="会话不存在")
    values = request.app.state.repository.list_messages(thread_id)
    return [item.model_dump(mode="json") for item in values]


@router.get("/audit")
def audit_logs(
    request: Request,
    limit: int = 100,
    identity: Identity = Depends(current_identity),
) -> list[dict[str, Any]]:
    require_role(identity, "approver", "admin")
    audits = request.app.state.repository.list_audits(safe_limit(limit))
    return [item.model_dump(mode="json") for item in audits]
