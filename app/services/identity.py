from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pwdlib import PasswordHash
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.enterprise_models import (
    LoginEventRow,
    PermissionRow,
    RolePermissionRow,
    RoleRow,
    TenantRow,
    UserAccountRow,
    UserCredentialRow,
    UserRoleRow,
)

PASSWORD_HASH = PasswordHash.recommended()
MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15

PERMISSIONS = {
    "dashboard.read": ("运营总览", "dashboard", "read"),
    "agent.run": ("运行智能体", "agent", "run"),
    "approval.read": ("查看审批", "approval", "read"),
    "approval.decide": ("处理审批", "approval", "decide"),
    "order.read": ("查看订单", "order", "read"),
    "after_sale.read": ("查看售后", "after_sale", "read"),
    "after_sale.write": ("处理售后", "after_sale", "write"),
    "refund.read": ("查看退款", "refund", "read"),
    "refund.execute": ("执行退款", "refund", "execute"),
    "conversation.read": ("查看会话", "conversation", "read"),
    "conversation.write": ("接管会话", "conversation", "write"),
    "knowledge.read": ("查看知识", "knowledge", "read"),
    "knowledge.review": ("审核知识", "knowledge", "review"),
    "knowledge.publish": ("发布知识", "knowledge", "publish"),
    "audit.read": ("查看审计", "audit", "read"),
    "quality.read": ("查看质检", "quality", "read"),
    "quality.manage": ("管理质检", "quality", "manage"),
    "notification.read": ("查看通知", "notification", "read"),
    "user.manage": ("管理用户", "user", "manage"),
    "system.manage": ("系统管理", "system", "manage"),
}

ROLE_PERMISSIONS = {
    "admin": set(PERMISSIONS),
    "approver": {
        "dashboard.read",
        "agent.run",
        "approval.read",
        "approval.decide",
        "order.read",
        "after_sale.read",
        "after_sale.write",
        "refund.read",
        "conversation.read",
        "conversation.write",
        "knowledge.read",
        "knowledge.review",
        "audit.read",
        "quality.read",
        "notification.read",
    },
    "customer": {
        "agent.run",
        "order.read",
        "after_sale.read",
        "after_sale.write",
        "refund.read",
        "conversation.read",
        "notification.read",
    },
}


class UserIdentity(BaseModel):
    user_id: str
    tenant_id: str
    username: str
    display_name: str
    roles: list[str]
    permissions: set[str]

    @property
    def primary_role(self) -> str:
        for role in ("admin", "approver", "customer"):
            if role in self.roles:
                return role
        return self.roles[0] if self.roles else "customer"


class IdentityService:
    def __init__(self, engine):
        self.engine = engine

    def seed_development_identities(self) -> None:
        now = datetime.now()
        tenant_id = "tenant-community"
        with Session(self.engine) as session:
            if session.get(TenantRow, tenant_id) is None:
                session.add(
                    TenantRow(
                        tenant_id=tenant_id,
                        code="community",
                        name="社区演示组织",
                        status="active",
                        created_at=now,
                        updated_at=now,
                    )
                )
            permission_rows: dict[str, PermissionRow] = {}
            for code, (name, resource, action) in PERMISSIONS.items():
                permission_id = f"perm-{code.replace('.', '-')}"
                row = session.get(PermissionRow, permission_id)
                if row is None:
                    row = PermissionRow(
                        permission_id=permission_id,
                        code=code,
                        name=name,
                        resource=resource,
                        action=action,
                    )
                    session.add(row)
                permission_rows[code] = row
            role_rows: dict[str, RoleRow] = {}
            for code, name in (
                ("admin", "系统管理员"),
                ("approver", "售后主管"),
                ("customer", "消费者"),
            ):
                role_id = f"role-{code}"
                row = session.get(RoleRow, role_id)
                if row is None:
                    row = RoleRow(
                        role_id=role_id,
                        tenant_id=tenant_id,
                        code=code,
                        name=name,
                        description=f"系统内置{name}角色",
                        is_system=True,
                        created_at=now,
                    )
                    session.add(row)
                role_rows[code] = row
            session.flush()
            for role_code, permission_codes in ROLE_PERMISSIONS.items():
                for permission_code in permission_codes:
                    key = (
                        role_rows[role_code].role_id,
                        permission_rows[permission_code].permission_id,
                    )
                    if session.get(RolePermissionRow, key) is None:
                        session.add(RolePermissionRow(role_id=key[0], permission_id=key[1]))

            users = (
                ("usr-admin", "admin", "平台管理员", "admin", "admin123"),
                ("usr-supervisor", "supervisor", "售后主管", "approver", "supervisor123"),
                ("U1001", "U1001", "消费者 U1001", "customer", "customer123"),
            )
            for user_id, username, display_name, role_code, password in users:
                if session.get(UserAccountRow, user_id) is None:
                    session.add(
                        UserAccountRow(
                            user_id=user_id,
                            tenant_id=tenant_id,
                            username=username,
                            display_name=display_name,
                            status="active",
                            failed_login_count=0,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    session.add(
                        UserCredentialRow(
                            user_id=user_id,
                            password_hash=PASSWORD_HASH.hash(password),
                            password_changed_at=now,
                            must_change_password=False,
                        )
                    )
                    session.add(
                        UserRoleRow(
                            tenant_id=tenant_id,
                            user_id=user_id,
                            role_id=role_rows[role_code].role_id,
                            granted_by="system-seed",
                            granted_at=now,
                        )
                    )
            session.commit()

    def authenticate(
        self,
        *,
        tenant_code: str,
        username: str,
        password: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> UserIdentity | None:
        now = datetime.now()
        with Session(self.engine) as session:
            tenant = session.scalar(select(TenantRow).where(TenantRow.code == tenant_code))
            user = None
            if tenant and tenant.status == "active":
                user = session.scalar(
                    select(UserAccountRow).where(
                        UserAccountRow.tenant_id == tenant.tenant_id,
                        UserAccountRow.username == username,
                    )
                )
            outcome = "invalid_credentials"
            if user and user.status == "active":
                if user.locked_until and user.locked_until > now:
                    outcome = "locked"
                else:
                    credential = session.get(UserCredentialRow, user.user_id)
                    if credential and PASSWORD_HASH.verify(password, credential.password_hash):
                        user.failed_login_count = 0
                        user.locked_until = None
                        user.last_login_at = now
                        user.updated_at = now
                        outcome = "success"
                    else:
                        user.failed_login_count += 1
                        if user.failed_login_count >= MAX_FAILED_LOGINS:
                            user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            session.add(
                LoginEventRow(
                    event_id=str(uuid4()),
                    tenant_id=tenant.tenant_id if tenant else "unknown",
                    user_id=user.user_id if user else None,
                    username=username[:64],
                    outcome=outcome,
                    ip_address=(ip_address or "")[:64] or None,
                    user_agent=(user_agent or "")[:512] or None,
                    created_at=now,
                )
            )
            session.commit()
            if outcome != "success" or user is None:
                return None
            return self._identity(session, user)

    def resolve_identity(self, *, tenant_id: str, user_id: str) -> UserIdentity | None:
        with Session(self.engine) as session:
            user = session.scalar(
                select(UserAccountRow).where(
                    UserAccountRow.user_id == user_id,
                    UserAccountRow.tenant_id == tenant_id,
                    UserAccountRow.status == "active",
                )
            )
            return self._identity(session, user) if user else None

    def list_users(self, tenant_id: str) -> list[dict]:
        with Session(self.engine) as session:
            users = session.scalars(
                select(UserAccountRow)
                .where(UserAccountRow.tenant_id == tenant_id)
                .order_by(UserAccountRow.created_at.desc())
            ).all()
            result: list[dict] = []
            for user in users:
                resolved = self._identity(session, user)
                result.append(
                    {
                        "user_id": user.user_id,
                        "username": user.username,
                        "display_name": user.display_name,
                        "email": user.email,
                        "status": user.status,
                        "last_login_at": user.last_login_at,
                        "created_at": user.created_at,
                        "roles": resolved.roles,
                        "permissions": sorted(resolved.permissions),
                    }
                )
            return result

    def create_user(
        self,
        *,
        tenant_id: str,
        username: str,
        display_name: str,
        email: str | None,
        password: str,
        role_codes: list[str],
        actor_id: str,
    ) -> UserIdentity:
        now = datetime.now()
        with Session(self.engine) as session, session.begin():
            existing = session.scalar(
                select(UserAccountRow.user_id).where(
                    UserAccountRow.tenant_id == tenant_id,
                    UserAccountRow.username == username,
                )
            )
            if existing:
                raise ValueError("用户名已存在")
            roles = session.scalars(
                select(RoleRow).where(RoleRow.tenant_id == tenant_id, RoleRow.code.in_(role_codes))
            ).all()
            if not roles or {role.code for role in roles} != set(role_codes):
                raise ValueError("包含无效角色")
            user_id = f"usr-{uuid4().hex}"
            user = UserAccountRow(
                user_id=user_id,
                tenant_id=tenant_id,
                username=username,
                display_name=display_name,
                email=email,
                status="active",
                failed_login_count=0,
                created_at=now,
                updated_at=now,
            )
            session.add(user)
            session.add(
                UserCredentialRow(
                    user_id=user_id,
                    password_hash=PASSWORD_HASH.hash(password),
                    password_changed_at=now,
                    must_change_password=True,
                )
            )
            session.add_all(
                [
                    UserRoleRow(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        role_id=role.role_id,
                        granted_by=actor_id,
                        granted_at=now,
                    )
                    for role in roles
                ]
            )
            session.flush()
            return self._identity(session, user)

    def update_user_access(
        self,
        *,
        tenant_id: str,
        user_id: str,
        status: str,
        role_codes: list[str],
        actor_id: str,
    ) -> UserIdentity:
        now = datetime.now()
        with Session(self.engine) as session, session.begin():
            user = session.scalar(
                select(UserAccountRow).where(
                    UserAccountRow.tenant_id == tenant_id,
                    UserAccountRow.user_id == user_id,
                )
            )
            if user is None:
                raise LookupError("用户不存在")
            if user.user_id == actor_id and (status != "active" or "admin" not in role_codes):
                raise ValueError("不能停用自己或移除自己的管理员角色")
            roles = session.scalars(
                select(RoleRow).where(RoleRow.tenant_id == tenant_id, RoleRow.code.in_(role_codes))
            ).all()
            if not roles or {role.code for role in roles} != set(role_codes):
                raise ValueError("包含无效角色")
            user.status = status
            user.updated_at = now
            for assignment in session.scalars(
                select(UserRoleRow).where(
                    UserRoleRow.tenant_id == tenant_id, UserRoleRow.user_id == user_id
                )
            ).all():
                session.delete(assignment)
            session.add_all(
                [
                    UserRoleRow(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        role_id=role.role_id,
                        granted_by=actor_id,
                        granted_at=now,
                    )
                    for role in roles
                ]
            )
            session.flush()
            return self._identity(session, user)

    @staticmethod
    def _identity(session: Session, user: UserAccountRow) -> UserIdentity:
        roles = session.scalars(
            select(RoleRow.code)
            .join(UserRoleRow, UserRoleRow.role_id == RoleRow.role_id)
            .where(UserRoleRow.user_id == user.user_id, UserRoleRow.tenant_id == user.tenant_id)
        ).all()
        permissions = session.scalars(
            select(PermissionRow.code)
            .join(RolePermissionRow, RolePermissionRow.permission_id == PermissionRow.permission_id)
            .join(UserRoleRow, UserRoleRow.role_id == RolePermissionRow.role_id)
            .where(UserRoleRow.user_id == user.user_id, UserRoleRow.tenant_id == user.tenant_id)
            .distinct()
        ).all()
        return UserIdentity(
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            username=user.username,
            display_name=user.display_name,
            roles=list(roles),
            permissions=set(permissions),
        )


def utc_now() -> datetime:
    return datetime.now(UTC)
