from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.enterprise_models import UserCredentialRow
from app.infrastructure.repository import SQLAlchemySupportRepository
from app.services.identity import IdentityService


def test_seeded_passwords_are_argon2_hashed_and_permissions_are_role_based() -> None:
    repository = SQLAlchemySupportRepository("sqlite://")
    repository.init_schema()
    service = IdentityService(repository.engine)
    service.seed_development_identities()

    with Session(repository.engine) as session:
        credential = session.scalar(
            select(UserCredentialRow).where(UserCredentialRow.user_id == "usr-admin")
        )
        assert credential is not None
        assert credential.password_hash.startswith("$argon2")
        assert "admin123" not in credential.password_hash

    admin = service.authenticate(
        tenant_code="community",
        username="admin",
        password="admin123",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    customer = service.authenticate(
        tenant_code="community",
        username="U1001",
        password="customer123",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert admin is not None and "refund.execute" in admin.permissions
    assert customer is not None and "refund.execute" not in customer.permissions


def test_admin_can_create_and_disable_a_role_scoped_user() -> None:
    repository = SQLAlchemySupportRepository("sqlite://")
    repository.init_schema()
    service = IdentityService(repository.engine)
    service.seed_development_identities()

    created = service.create_user(
        tenant_id="tenant-community",
        username="agent01",
        display_name="售后专员 01",
        email="agent01@example.test",
        password="StrongPass-2026",
        role_codes=["approver"],
        actor_id="usr-admin",
    )
    assert created.roles == ["approver"]
    assert "approval.decide" in created.permissions
    assert "knowledge.publish" not in created.permissions

    updated = service.update_user_access(
        tenant_id="tenant-community",
        user_id=created.user_id,
        status="disabled",
        role_codes=["customer"],
        actor_id="usr-admin",
    )
    assert updated.roles == ["customer"]
    assert service.resolve_identity(tenant_id="tenant-community", user_id=created.user_id) is None
