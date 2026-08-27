from fastapi import APIRouter, Request

from app.api.schemas import LoginRequest, LoginResponse
from app.services.auth import login

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=LoginResponse)
def auth_login(payload: LoginRequest, request: Request) -> dict[str, str | int | list[str]]:
    return login(
        request.app.state.settings,
        request.app.state.identity_service,
        tenant_code=payload.tenant_code,
        username=payload.username,
        password=payload.password,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
