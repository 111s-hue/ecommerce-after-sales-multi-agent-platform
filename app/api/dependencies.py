from fastapi import HTTPException, Request

from app.services.auth import Identity


def enforce_customer_scope(
    request: Request, identity: Identity, requested_user_id: str | None
) -> str | None:
    if not request.app.state.settings.auth_enabled or identity.role != "customer":
        return requested_user_id
    if requested_user_id and requested_user_id != identity.user_id:
        raise HTTPException(status_code=403, detail="消费者只能访问自己的业务数据")
    return identity.user_id


def safe_limit(limit: int, maximum: int = 500) -> int:
    return min(max(limit, 1), maximum)
