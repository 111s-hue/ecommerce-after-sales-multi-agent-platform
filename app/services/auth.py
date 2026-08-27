from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi import Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.config import Settings
from app.services.identity import IdentityService


class Identity(BaseModel):
    user_id: str
    role: str
    tenant_id: str = "tenant-community"
    username: str = "development"
    display_name: str = "Development Administrator"
    roles: list[str] = Field(default_factory=lambda: ["admin"])
    permissions: set[str] = Field(default_factory=set)


def login(
    settings: Settings,
    identity_service: IdentityService,
    *,
    tenant_code: str,
    username: str,
    password: str,
    ip_address: str | None,
    user_agent: str | None,
) -> dict[str, str | int | list[str]]:
    user = identity_service.authenticate(
        tenant_code=tenant_code,
        username=username,
        password=password,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    expires = datetime.now(UTC) + timedelta(minutes=settings.access_token_minutes)
    token = jwt.encode(
        {
            "sub": user.user_id,
            "tenant_id": user.tenant_id,
            "username": user.username,
            "roles": user.roles,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": datetime.now(UTC),
            "jti": str(uuid4()),
            "exp": expires,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.access_token_minutes * 60,
        "role": user.primary_role,
        "user_id": user.user_id,
        "tenant_id": user.tenant_id,
        "display_name": user.display_name,
        "permissions": sorted(user.permissions),
    }


def current_identity(
    request: Request, authorization: str | None = Header(default=None)
) -> Identity:
    settings: Settings = request.app.state.settings
    if not settings.auth_enabled:
        return Identity(user_id="development", role="admin", permissions={"*"})
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少访问令牌")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "tenant_id", "jti"]},
        )
        resolved = request.app.state.identity_service.resolve_identity(
            tenant_id=str(payload["tenant_id"]), user_id=str(payload["sub"])
        )
        if resolved is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号已失效")
        return Identity(
            user_id=resolved.user_id,
            role=resolved.primary_role,
            tenant_id=resolved.tenant_id,
            username=resolved.username,
            display_name=resolved.display_name,
            roles=resolved.roles,
            permissions=resolved.permissions,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="访问令牌无效"
        ) from exc


def require_role(identity: Identity, *roles: str) -> None:
    if identity.role not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前角色无权执行该操作")


def require_permission(identity: Identity, permission: str) -> None:
    if "*" not in identity.permissions and permission not in identity.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号缺少所需权限")
