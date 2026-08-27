import pytest

from app.config import Settings
from app.infrastructure.repository import SQLAlchemySupportRepository
from app.services.knowledge import KnowledgeService


def test_knowledge_upload_rebuilds_search_index(tmp_path) -> None:
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "base.md").write_text("# 基础政策\n\n## 基础\n\n默认规则。", encoding="utf-8")
    service = KnowledgeService(
        Settings(policy_dir=policy_dir, faiss_index_dir=tmp_path / "indexes")
    )

    document = service.save_markdown(
        "damaged.md",
        "# 破损政策\n\n## 到货破损\n\n到货破损应在24小时内上传照片并转人工审核。".encode(),
    )
    evidence = service.knowledge_base.search("商品到货破损怎么办", top_k=1)

    assert document.name == "damaged.md"
    assert evidence[0].source == "damaged.md"


def test_governed_publication_records_version_review_index_and_release(tmp_path) -> None:
    repository = SQLAlchemySupportRepository("sqlite://")
    repository.init_schema()
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "base.md").write_text("# 基础政策\n\n默认规则。", encoding="utf-8")
    settings = Settings(
        policy_dir=policy_dir,
        faiss_index_dir=tmp_path / "indexes",
    )
    service = KnowledgeService(settings, repository.engine)

    publication = service.publish_markdown(
        tenant_id="tenant-community",
        user_id="usr-admin",
        filename="returns.md",
        content="# 退货政策\n\n## 验收\n\n仓库验收通过后发起退款。".encode(),
    )
    documents = service.list_governed_documents("tenant-community")

    assert publication["status"] == "published"
    assert publication["index_status"] == "succeeded"
    assert publication["version_no"] == 1
    assert documents[0]["version_id"] == publication["version_id"]


def test_document_preview_retirement_and_last_document_guard(tmp_path) -> None:
    repository = SQLAlchemySupportRepository("sqlite://")
    repository.init_schema()
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "base.md").write_text("# 基础政策\n\n默认规则。", encoding="utf-8")
    service = KnowledgeService(
        Settings(policy_dir=policy_dir, faiss_index_dir=tmp_path / "indexes"),
        repository.engine,
    )
    service.publish_markdown(
        tenant_id="tenant-community",
        user_id="usr-admin",
        filename="damaged.md",
        content="# 破损政策\n\n## 到货破损\n\n到货破损需要上传照片。".encode(),
    )

    assert "到货破损" in service.read_document("damaged.md")["content"]
    assert {item["name"] for item in service.list_governed_documents("tenant-community")} == {
        "base.md",
        "damaged.md",
    }

    retired = service.delete_document(
        tenant_id="tenant-community", user_id="usr-admin", filename="damaged.md"
    )
    assert retired["status"] == "retired"
    assert [item["name"] for item in service.list_governed_documents("tenant-community")] == [
        "base.md"
    ]
    with pytest.raises(FileNotFoundError):
        service.read_document("damaged.md")
    with pytest.raises(ValueError, match="至少保留一份"):
        service.delete_document(
            tenant_id="tenant-community", user_id="usr-admin", filename="base.md"
        )
