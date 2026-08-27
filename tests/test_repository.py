from pathlib import Path

from app.infrastructure.repository import SQLAlchemySupportRepository


def test_sqlalchemy_repository_seeds_and_enforces_user_scope(tmp_path: Path) -> None:
    repository = SQLAlchemySupportRepository(f"sqlite:///{tmp_path / 'test.db'}")
    repository.init_schema()
    repository.seed_demo_data()

    assert repository.get_order("ORD-1001", "U1001") is not None
    assert repository.get_order("ORD-2001", "U1001") is None
    assert repository.get_logistics("ORD-1002", "U1001") is not None
    assert repository.healthcheck() is True
    assert {item.order_id for item in repository.list_orders("U1001")} == {
        "ORD-1001",
        "ORD-1002",
    }


def test_sqlalchemy_repository_persists_conversation_and_approval(tmp_path: Path) -> None:
    repository = SQLAlchemySupportRepository(f"sqlite:///{tmp_path / 'workflow.db'}")
    repository.init_schema()
    repository.upsert_conversation(
        thread_id="db-thread-1",
        user_id="U1001",
        title="申请退款",
        status="pending_approval",
        intent="refund",
    )
    repository.add_message(thread_id="db-thread-1", role="user", content="申请退款")
    repository.upsert_approval(
        thread_id="db-thread-1",
        user_id="U1001",
        order_id="ORD-1001",
        action="create_after_sale",
        amount=699,
        payload_json="{}",
    )

    assert repository.list_conversations("U1001")[0].intent == "refund"
    assert repository.list_messages("db-thread-1")[0].content == "申请退款"
    assert repository.list_approvals("pending")[0].amount == 699


def test_sqlalchemy_repository_lists_after_sales_with_scope(tmp_path: Path) -> None:
    repository = SQLAlchemySupportRepository(f"sqlite:///{tmp_path / 'tickets.db'}")
    repository.init_schema()
    repository.seed_demo_data()
    repository.create_after_sale(
        order_id="ORD-1001",
        user_id="U1001",
        reason="商品不合适",
        refundable_amount=699,
        idempotency_key="ticket-list-1",
        reviewer="主管A",
    )

    assert len(repository.list_after_sales("U1001")) == 1
    assert repository.list_after_sales("U2001") == []
