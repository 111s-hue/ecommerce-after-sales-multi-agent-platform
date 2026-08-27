from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.services.auth import Identity, current_identity, require_permission

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    require_permission(identity, "notification.read")
    return request.app.state.notification_service.list_for_recipient(
        tenant_id=identity.tenant_id,
        recipient_id=identity.user_id,
        limit=limit,
    )


@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, bool]:
    require_permission(identity, "notification.read")
    updated = request.app.state.notification_service.mark_read(
        tenant_id=identity.tenant_id,
        recipient_id=identity.user_id,
        notification_id=notification_id,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="通知不存在")
    return {"read": True}
