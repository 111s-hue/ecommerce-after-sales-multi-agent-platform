from fastapi.testclient import TestClient

from app.main import app


def test_health_and_chat_api(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("POLICY_DIR", "./data/policies")
    monkeypatch.setenv("USE_REDIS_CHECKPOINT", "false")
    monkeypatch.setenv("AUTH_ENABLED", "false")

    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as client:
        health = client.get("/health")
        chat = client.post(
            "/api/v1/chat",
            json={
                "user_id": "U1001",
                "thread_id": "api-logistics-1",
                "query": "ORD-1002 的物流到哪里了",
            },
        )
        selected = client.post(
            "/api/v1/chat",
            json={
                "user_id": "U1001",
                "thread_id": "api-selected-order-1",
                "query": "请解释 ORD-1001 的物流政策",
                "target_agent": "order",
            },
        )

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert chat.status_code == 200
    assert chat.json()["intent"] == "logistics"
    assert selected.status_code == 200
    assert selected.json()["intent"] == "order"


def test_knowledge_document_lifecycle_api(monkeypatch, tmp_path) -> None:
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "base.md").write_text("# 基础政策\n\n默认规则。", encoding="utf-8")
    (policy_dir / "shipping.md").write_text(
        "# 物流政策\n\n## 延迟\n\n延迟订单应主动告知客户。", encoding="utf-8"
    )
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'knowledge-api.db'}")
    monkeypatch.setenv("POLICY_DIR", str(policy_dir))
    monkeypatch.setenv("AUTH_ENABLED", "false")

    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as client:
        listed = client.get("/api/v1/knowledge/documents")
        preview = client.get("/api/v1/knowledge/documents/shipping.md")
        download = client.get("/api/v1/knowledge/documents/shipping.md/download")
        deleted = client.delete("/api/v1/knowledge/documents/shipping.md")
        remaining = client.get("/api/v1/knowledge/documents")
        protected = client.delete("/api/v1/knowledge/documents/base.md")
        audits = client.get("/api/v1/audit")

    assert listed.status_code == 200
    assert {item["name"] for item in listed.json()} == {"base.md", "shipping.md"}
    assert preview.status_code == 200
    assert "延迟订单" in preview.json()["content"]
    assert download.status_code == 200
    assert "attachment" in download.headers["content-disposition"]
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "retired"
    assert [item["name"] for item in remaining.json()] == ["base.md"]
    assert protected.status_code == 409
    assert any(item["action"] == "knowledge.delete" for item in audits.json())


def test_sse_contains_real_node_events(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'sse.db'}")
    monkeypatch.setenv("POLICY_DIR", "./data/policies")
    monkeypatch.setenv("AUTH_ENABLED", "false")

    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "user_id": "U1001",
                "thread_id": "api-stream-1",
                "query": "ORD-1002 的物流到哪里了",
            },
        )

    assert response.status_code == 200
    assert "event: node" in response.text
    assert '"node": "supervisor"' in response.text
    assert '"node": "logistics"' in response.text


def test_jwt_customer_cannot_switch_user_id(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'auth.db'}")
    monkeypatch.setenv("POLICY_DIR", "./data/policies")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "unit-test-secret-at-least-32-bytes")

    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "U1001", "password": "customer123"},
        )
        token = login.json()["access_token"]
        own = client.get(
            "/api/v1/orders/ORD-1001?user_id=U1001",
            headers={"Authorization": f"Bearer {token}"},
        )
        forbidden = client.get(
            "/api/v1/orders/ORD-2001?user_id=U2001",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert login.status_code == 200
    assert own.status_code == 200
    assert forbidden.status_code == 403


def test_operational_endpoints_and_request_tracking(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'operations.db'}")
    monkeypatch.setenv("POLICY_DIR", "./data/policies")
    monkeypatch.setenv("AUTH_ENABLED", "false")

    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as client:
        ready = client.get("/api/v1/health/ready", headers={"X-Request-ID": "test-request-1"})
        orders = client.get("/api/v1/orders?user_id=U1001")
        tickets = client.get("/api/v1/after-sales?user_id=U1001")
        system = client.get("/api/v1/system/info")

    assert ready.status_code == 200
    assert ready.json()["checks"]["database"] is True
    assert ready.headers["X-Request-ID"] == "test-request-1"
    assert "X-Process-Time-Ms" in ready.headers
    assert {item["order_id"] for item in orders.json()} == {"ORD-1001", "ORD-1002"}
    assert tickets.status_code == 200
    assert system.json()["version"] == "1.0.0"


def test_customer_order_collection_is_always_identity_scoped(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'collection-auth.db'}")
    monkeypatch.setenv("POLICY_DIR", "./data/policies")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "unit-test-secret-at-least-32-bytes")

    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "U1001", "password": "customer123"},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        own_orders = client.get("/api/v1/orders", headers=headers)
        switched = client.get("/api/v1/orders?user_id=U2001", headers=headers)

    assert {item["user_id"] for item in own_orders.json()} == {"U1001"}
    assert switched.status_code == 403


def test_role_permissions_are_enforced_by_the_api(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'rbac.db'}")
    monkeypatch.setenv("POLICY_DIR", "./data/policies")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "unit-test-secret-at-least-32-bytes")

    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as client:

        def headers_for(username: str, password: str) -> tuple[dict[str, str], dict]:
            response = client.post(
                "/api/v1/auth/login",
                json={"username": username, "password": password},
            )
            assert response.status_code == 200
            return {"Authorization": f"Bearer {response.json()['access_token']}"}, response.json()

        customer, customer_login = headers_for("U1001", "customer123")
        approver, _ = headers_for("supervisor", "supervisor123")
        admin, _ = headers_for("admin", "admin123")

        assert customer_login["user_id"] == "U1001"
        assert client.get("/api/v1/orders", headers=customer).status_code == 200
        for path in (
            "/api/v1/approvals",
            "/api/v1/knowledge/documents",
            "/api/v1/audit",
            "/api/v1/metrics/summary",
            "/api/v1/metrics/evaluation",
        ):
            assert client.get(path, headers=customer).status_code == 403

        for path in (
            "/api/v1/approvals",
            "/api/v1/knowledge/documents",
            "/api/v1/audit",
            "/api/v1/metrics/summary",
        ):
            assert client.get(path, headers=approver).status_code == 200
        assert client.post("/api/v1/knowledge/rebuild", headers=approver).status_code == 403
        assert client.get("/api/v1/metrics/evaluation", headers=approver).status_code == 403

        assert client.post("/api/v1/knowledge/rebuild", headers=admin).status_code == 200
        assert client.get("/api/v1/metrics/evaluation", headers=admin).status_code == 200


def test_enterprise_refund_api_runs_from_customer_request_to_gateway(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'refund-flow.db'}")
    monkeypatch.setenv("POLICY_DIR", "./data/policies")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "unit-test-secret-at-least-32-bytes")

    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as client:

        def auth(username: str, password: str) -> dict[str, str]:
            response = client.post(
                "/api/v1/auth/login", json={"username": username, "password": password}
            )
            return {"Authorization": f"Bearer {response.json()['access_token']}"}

        customer = auth("U1001", "customer123")
        approver = auth("supervisor", "supervisor123")
        admin = auth("admin", "admin123")
        created = client.post(
            "/api/v1/after-sale-cases",
            headers={**customer, "Idempotency-Key": "api-refund-flow-1001"},
            json={
                "order_id": "ORD-1001",
                "customer_id": "U2001",
                "case_type": "refund_only",
                "reason": "商品存在质量问题",
                "requested_amount": 88,
                "priority": "normal",
            },
        )
        case_id = created.json()["case_id"]
        reviewed = client.post(
            f"/api/v1/after-sale-cases/{case_id}/review",
            headers=approver,
            json={"approved": True, "approved_amount": 80, "reason": "核验通过"},
        )
        refund_id = reviewed.json()["refunds"][0]["refund_id"]
        customer_execution = client.post(
            f"/api/v1/after-sale-cases/{case_id}/refunds/{refund_id}/execute",
            headers=customer,
        )
        executed = client.post(
            f"/api/v1/after-sale-cases/{case_id}/refunds/{refund_id}/execute",
            headers=admin,
        )

    assert created.status_code == 201
    assert created.json()["customer_id"] == "U1001"
    assert reviewed.json()["status"] == "processing"
    assert customer_execution.status_code == 403
    assert executed.status_code == 200
    assert executed.json()["status"] == "completed"
