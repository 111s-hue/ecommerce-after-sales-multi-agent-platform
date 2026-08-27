from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import Field

from app.api.schemas import StrictRequest
from app.services.auth import Identity, current_identity, require_permission

router = APIRouter(prefix="/users", tags=["identity"])


class CreateUserRequest(StrictRequest):
    username: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=2, max_length=128)
    email: str | None = Field(default=None, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=12, max_length=128)
    roles: list[Literal["admin", "approver", "customer"]] = Field(min_length=1)


class UpdateUserAccessRequest(StrictRequest):
    status: Literal["active", "disabled"]
    roles: list[Literal["admin", "approver", "customer"]] = Field(min_length=1)


@router.get("/me")
def me(identity: Identity = Depends(current_identity)) -> dict[str, Any]:
    return identity.model_dump(mode="json")


@router.get("")
def list_users(
    request: Request, identity: Identity = Depends(current_identity)
) -> list[dict[str, Any]]:
    require_permission(identity, "user.manage")
    return request.app.state.identity_service.list_users(identity.tenant_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserRequest,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    require_permission(identity, "user.manage")
    try:
        created = request.app.state.identity_service.create_user(
            tenant_id=identity.tenant_id,
            username=payload.username,
            display_name=payload.display_name,
            email=str(payload.email) if payload.email else None,
            password=payload.password,
            role_codes=list(payload.roles),
            actor_id=identity.user_id,
        )
        return created.model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/{user_id}/access")
def update_user_access(
    user_id: str,
    payload: UpdateUserAccessRequest,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    require_permission(identity, "user.manage")
    try:
        updated = request.app.state.identity_service.update_user_access(
            tenant_id=identity.tenant_id,
            user_id=user_id,
            status=payload.status,
            role_codes=list(payload.roles),
            actor_id=identity.user_id,
        )
        return updated.model_dump(mode="json")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
