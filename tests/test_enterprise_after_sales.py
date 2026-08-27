from decimal import Decimal

import pytest

from app.infrastructure.repository import SQLAlchemySupportRepository
from app.services.after_sales import AfterSalesService, ConflictError, NotFoundError
from app.services.notifications import NotificationService


@pytest.fixture
def enterprise_service() -> AfterSalesService:
    repository = SQLAlchemySupportRepository("sqlite://")
    repository.init_schema()
    repository.seed_demo_data()
    return AfterSalesService(repository.engine)


def create_case(
    service: AfterSalesService,
    *,
    case_type: str = "refund_only",
    amount: Decimal | None = Decimal("100.00"),
    key: str = "create-case-1001",
) -> dict:
    return service.create_case(
        tenant_id="tenant-community",
        actor_id="U1001",
        actor_role="customer",
        order_id="ORD-1001",
        customer_id="U1001",
        case_type=case_type,
        reason_code="quality_issue",
        reason="商品存在明确质量问题",
        requested_amount=amount,
        priority="normal",
        idempotency_key=key,
    )


def test_create_is_idempotent_and_rejects_cross_customer_access(
    enterprise_service: AfterSalesService,
) -> None:
    first = create_case(enterprise_service)
    second = create_case(enterprise_service)

    assert first["case_id"] == second["case_id"]
    assert first["status"] == "submitted"
    with pytest.raises(NotFoundError):
        enterprise_service.get_case(
            tenant_id="tenant-community",
            case_id=first["case_id"],
            customer_id="U2001",
        )
    notification_service = NotificationService(enterprise_service.engine)
    inbox = notification_service.list_for_recipient(
        tenant_id="tenant-community", recipient_id="U1001"
    )
    assert inbox["unread"] == 1
    assert notification_service.mark_read(
        tenant_id="tenant-community",
        recipient_id="U1001",
        notification_id=inbox["items"][0]["notification_id"],
    )
    assert (
        notification_service.list_for_recipient(tenant_id="tenant-community", recipient_id="U1001")[
            "unread"
        ]
        == 0
    )


def test_same_idempotency_key_cannot_represent_a_different_request(
    enterprise_service: AfterSalesService,
) -> None:
    create_case(enterprise_service)
    with pytest.raises(ConflictError):
        create_case(enterprise_service, amount=Decimal("99.00"))


def test_refund_only_reaches_completed_through_gateway(
    enterprise_service: AfterSalesService,
) -> None:
    case = create_case(enterprise_service)
    reviewed = enterprise_service.review_case(
        tenant_id="tenant-community",
        case_id=case["case_id"],
        actor_id="usr-supervisor",
        approved=True,
        approved_amount=Decimal("80.00"),
        reason="凭证有效",
    )

    assert reviewed["status"] == "processing"
    assert reviewed["refunds"][0]["status"] == "pending"
    completed = enterprise_service.execute_refund(
        tenant_id="tenant-community",
        case_id=case["case_id"],
        refund_id=reviewed["refunds"][0]["refund_id"],
        actor_id="usr-admin",
    )

    assert completed["status"] == "completed"
    assert completed["refunds"][0]["status"] == "succeeded"
    assert completed["refunds"][0]["provider_refund_no"].startswith("SBX-")


def test_return_refund_requires_return_and_inspection_before_refund(
    enterprise_service: AfterSalesService,
) -> None:
    case = create_case(
        enterprise_service,
        case_type="return_refund",
        amount=Decimal("120.00"),
        key="return-case-1001",
    )
    reviewed = enterprise_service.review_case(
        tenant_id="tenant-community",
        case_id=case["case_id"],
        actor_id="usr-supervisor",
        approved=True,
        approved_amount=Decimal("120.00"),
        reason="同意退货退款",
    )
    assert reviewed["status"] == "awaiting_customer_return"
    assert reviewed["returns"][0]["status"] == "awaiting_shipment"

    shipped = enterprise_service.ship_return(
        tenant_id="tenant-community",
        case_id=case["case_id"],
        actor_id="U1001",
        customer_id="U1001",
        carrier="顺丰速运",
        tracking_no="SF-RETURN-1001",
    )
    assert shipped["status"] == "awaiting_receipt"

    inspected = enterprise_service.inspect_return(
        tenant_id="tenant-community",
        case_id=case["case_id"],
        actor_id="usr-supervisor",
        accepted=True,
        notes="验收通过，包装轻微破损扣减 10 元",
        deduction_amount=Decimal("10.00"),
    )
    assert inspected["status"] == "processing"
    assert inspected["refunds"][0]["amount"] == "110.00"


@pytest.mark.parametrize(
    ("case_type", "collection"),
    [
        ("exchange", "exchanges"),
        ("reshipment", "reshipments"),
        ("repair", "repairs"),
        ("compensation", "compensations"),
    ],
)
def test_approval_creates_a_real_fulfillment_record(
    enterprise_service: AfterSalesService, case_type: str, collection: str
) -> None:
    amount = Decimal("50.00") if case_type == "compensation" else None
    case = create_case(
        enterprise_service,
        case_type=case_type,
        amount=amount,
        key=f"create-{case_type}",
    )
    reviewed = enterprise_service.review_case(
        tenant_id="tenant-community",
        case_id=case["case_id"],
        actor_id="usr-supervisor",
        approved=True,
        approved_amount=amount,
        reason="审批通过",
    )

    assert len(reviewed[collection]) == 1
