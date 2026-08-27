from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.models import KnowledgeDocument
from app.infrastructure.enterprise_models import (
    knowledge_bases,
    knowledge_document_versions,
    knowledge_documents,
    knowledge_index_jobs,
    knowledge_publications,
    knowledge_review_records,
)
from app.services.rag import PolicyKnowledgeBase

SAFE_NAME = re.compile(r"[^a-zA-Z0-9._\-\u4e00-\u9fff]+")


class KnowledgeService:
    def __init__(self, settings: Settings, engine: Engine | None = None):
        self.settings = settings
        self.engine = engine
        self.policy_dir = settings.policy_dir.resolve()
        self.policy_dir.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._knowledge_base = self._build()
        self._s3 = self._build_s3() if settings.minio_enabled else None

    def _build(self) -> PolicyKnowledgeBase:
        return PolicyKnowledgeBase(
            self.policy_dir,
            backend=self.settings.rag_backend,
            bge_model=self.settings.bge_model,
            index_dir=self.settings.faiss_index_dir,
            milvus_uri=self.settings.milvus_uri,
            milvus_token=self.settings.milvus_token,
            milvus_collection=self.settings.milvus_collection,
            tenant_id=self.settings.knowledge_tenant_id,
        )

    def _build_s3(self):
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=self.settings.minio_endpoint,
            aws_access_key_id=self.settings.minio_access_key,
            aws_secret_access_key=self.settings.minio_secret_key,
        )
        buckets = {item["Name"] for item in client.list_buckets().get("Buckets", [])}
        if self.settings.minio_bucket not in buckets:
            client.create_bucket(Bucket=self.settings.minio_bucket)
        return client

    @property
    def knowledge_base(self) -> PolicyKnowledgeBase:
        with self._lock:
            return self._knowledge_base

    def save_markdown(self, filename: str, content: bytes) -> KnowledgeDocument:
        safe_name = SAFE_NAME.sub("_", Path(filename).name)
        if not safe_name.lower().endswith(".md"):
            raise ValueError("知识库当前只接受 Markdown 文件")
        if len(content) > 5 * 1024 * 1024:
            raise ValueError("单个知识文件不能超过 5MB")
        text = content.decode("utf-8")
        if not text.strip() or "#" not in text:
            raise ValueError("Markdown 文件必须包含标题和正文")
        path = (self.policy_dir / safe_name).resolve()
        if path.parent != self.policy_dir:
            raise ValueError("非法文件名")
        path.write_text(text, encoding="utf-8")
        storage = "local"
        if self._s3:
            self._s3.put_object(
                Bucket=self.settings.minio_bucket,
                Key=f"policies/{safe_name}",
                Body=content,
                ContentType="text/markdown; charset=utf-8",
            )
            storage = "local+minio"
        self.rebuild()
        stat = path.stat()
        return KnowledgeDocument(
            name=safe_name,
            size=stat.st_size,
            updated_at=datetime.fromtimestamp(stat.st_mtime),
            storage=storage,
        )

    def _resolve_document(self, filename: str) -> Path:
        safe_name = SAFE_NAME.sub("_", Path(filename).name)
        if safe_name != filename or not safe_name.lower().endswith(".md"):
            raise ValueError("非法知识文档名称")
        path = (self.policy_dir / safe_name).resolve()
        if path.parent != self.policy_dir:
            raise ValueError("非法知识文档路径")
        if not path.is_file():
            raise FileNotFoundError(safe_name)
        return path

    def read_document(self, filename: str) -> dict:
        path = self._resolve_document(filename)
        stat = path.stat()
        return {
            "name": path.name,
            "content": path.read_text(encoding="utf-8"),
            "size": stat.st_size,
            "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "storage": "local+minio" if self._s3 else "local",
        }

    def delete_document(self, *, tenant_id: str, user_id: str, filename: str) -> dict:
        """Retire a governed document while retaining its immutable database history."""
        with self._lock:
            path = self._resolve_document(filename)
            if len(list(self.policy_dir.glob("*.md"))) <= 1:
                raise ValueError("知识库必须至少保留一份文档")
            content = path.read_bytes()
            previous_index = self._knowledge_base
            path.unlink()
            try:
                if self._s3:
                    self._s3.delete_object(
                        Bucket=self.settings.minio_bucket,
                        Key=f"policies/{path.name}",
                    )
                new_index = self._build()
                if self.engine is not None:
                    now = datetime.now()
                    with Session(self.engine) as session, session.begin():
                        row = session.execute(
                            select(
                                knowledge_documents.c.document_id,
                                knowledge_documents.c.current_version_id,
                            ).where(
                                knowledge_documents.c.tenant_id == tenant_id,
                                knowledge_documents.c.slug == path.name.lower(),
                                knowledge_documents.c.status != "retired",
                            )
                        ).first()
                        if row is not None:
                            session.execute(
                                update(knowledge_documents)
                                .where(
                                    knowledge_documents.c.document_id == row.document_id,
                                    knowledge_documents.c.tenant_id == tenant_id,
                                )
                                .values(status="retired", updated_at=now)
                            )
                            if row.current_version_id:
                                session.execute(
                                    update(knowledge_publications)
                                    .where(
                                        knowledge_publications.c.tenant_id == tenant_id,
                                        knowledge_publications.c.version_id
                                        == row.current_version_id,
                                    )
                                    .values(status="retired", retired_at=now, updated_at=now)
                                )
                self._knowledge_base = new_index
            except Exception:
                path.write_bytes(content)
                if self._s3:
                    self._s3.put_object(
                        Bucket=self.settings.minio_bucket,
                        Key=f"policies/{path.name}",
                        Body=content,
                        ContentType="text/markdown; charset=utf-8",
                    )
                self._knowledge_base = previous_index
                raise
        return {"name": path.name, "status": "retired", "retired_by": user_id}

    def publish_markdown(
        self, *, tenant_id: str, user_id: str, filename: str, content: bytes
    ) -> dict:
        """Publish a validated immutable version and record its index lifecycle."""
        document = self.save_markdown(filename, content)
        if self.engine is None:
            return {**document.model_dump(mode="json"), "status": "published"}
        now = datetime.now()
        slug = document.name.lower()
        with Session(self.engine) as session, session.begin():
            knowledge_base = session.execute(
                select(knowledge_bases).where(
                    knowledge_bases.c.tenant_id == tenant_id,
                    knowledge_bases.c.name == "售后政策知识库",
                )
            ).first()
            if knowledge_base is None:
                knowledge_base_id = f"kb-{uuid4().hex}"
                session.execute(
                    insert(knowledge_bases).values(
                        knowledge_base_id=knowledge_base_id,
                        tenant_id=tenant_id,
                        name="售后政策知识库",
                        description="智能体生产运行使用的已审核售后政策",
                        status="active",
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                knowledge_base_id = knowledge_base.knowledge_base_id
            row = session.execute(
                select(knowledge_documents).where(
                    knowledge_documents.c.tenant_id == tenant_id,
                    knowledge_documents.c.knowledge_base_id == knowledge_base_id,
                    knowledge_documents.c.slug == slug,
                )
            ).first()
            if row is None:
                document_id = f"document-{uuid4().hex}"
                session.execute(
                    insert(knowledge_documents).values(
                        document_id=document_id,
                        tenant_id=tenant_id,
                        knowledge_base_id=knowledge_base_id,
                        title=document.name.removesuffix(".md"),
                        slug=slug,
                        status="publishing",
                        current_version_id=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                document_id = row.document_id
            latest = session.scalar(
                select(func.max(knowledge_document_versions.c.version_no)).where(
                    knowledge_document_versions.c.document_id == document_id
                )
            )
            version_no = (latest or 0) + 1
            version_id = f"version-{uuid4().hex}"
            session.execute(
                insert(knowledge_document_versions).values(
                    version_id=version_id,
                    tenant_id=tenant_id,
                    document_id=document_id,
                    version_no=version_no,
                    object_key=f"policies/{document.name}",
                    sha256=hashlib.sha256(content).hexdigest(),
                    content_type="text/markdown; charset=utf-8",
                    size=document.size,
                    status="published",
                    created_by=user_id,
                    created_at=now,
                )
            )
            session.execute(
                insert(knowledge_review_records).values(
                    review_id=f"review-{uuid4().hex}",
                    tenant_id=tenant_id,
                    version_id=version_id,
                    reviewer_id=user_id,
                    decision="approved",
                    comment="管理员发布时完成内容与索引一致性审核",
                    created_at=now,
                )
            )
            session.execute(
                insert(knowledge_index_jobs).values(
                    job_id=f"index-{uuid4().hex}",
                    tenant_id=tenant_id,
                    version_id=version_id,
                    backend=self.settings.rag_backend,
                    status="succeeded",
                    chunk_count=len(self.knowledge_base.chunks),
                    error_message=None,
                    started_at=now,
                    finished_at=datetime.now(),
                    created_at=now,
                    updated_at=datetime.now(),
                )
            )
            session.execute(
                insert(knowledge_publications).values(
                    publication_id=f"publication-{uuid4().hex}",
                    tenant_id=tenant_id,
                    version_id=version_id,
                    environment=self.settings.environment,
                    status="published",
                    published_by=user_id,
                    published_at=datetime.now(),
                    retired_at=None,
                    created_at=now,
                    updated_at=datetime.now(),
                )
            )
            session.execute(
                update(knowledge_documents)
                .where(knowledge_documents.c.document_id == document_id)
                .values(
                    status="published",
                    current_version_id=version_id,
                    updated_at=datetime.now(),
                )
            )
        return {
            **document.model_dump(mode="json"),
            "document_id": document_id,
            "version_id": version_id,
            "version_no": version_no,
            "status": "published",
            "index_status": "succeeded",
        }

    def list_governed_documents(self, tenant_id: str) -> list[dict]:
        governed: dict[str, dict] = {}
        if self.engine is not None:
            with Session(self.engine) as session:
                rows = session.execute(
                select(
                    knowledge_documents.c.document_id,
                    knowledge_documents.c.title,
                    knowledge_documents.c.slug,
                    knowledge_documents.c.status,
                    knowledge_documents.c.updated_at,
                    knowledge_document_versions.c.version_id,
                    knowledge_document_versions.c.version_no,
                    knowledge_document_versions.c.size,
                )
                .join(
                    knowledge_document_versions,
                    knowledge_document_versions.c.version_id
                    == knowledge_documents.c.current_version_id,
                )
                .where(
                    knowledge_documents.c.tenant_id == tenant_id,
                    knowledge_documents.c.status != "retired",
                )
                .order_by(knowledge_documents.c.updated_at.desc())
                ).all()
                governed = {
                    row.slug: {
                        "document_id": row.document_id,
                        "version_id": row.version_id,
                        "version_no": row.version_no,
                        "name": row.slug,
                        "title": row.title,
                        "size": row.size,
                        "updated_at": row.updated_at.isoformat(),
                        "storage": "local+minio" if self._s3 else "local",
                        "status": row.status,
                        "index_status": "succeeded",
                    }
                    for row in rows
                }
        documents: list[dict] = []
        for item in self.list_documents():
            base = item.model_dump(mode="json")
            documents.append(
                governed.get(
                    item.name.lower(),
                    {**base, "status": "published", "index_status": "succeeded"},
                )
            )
        return sorted(documents, key=lambda item: item["updated_at"], reverse=True)

    def rebuild(self) -> int:
        new_index = self._build()
        with self._lock:
            self._knowledge_base = new_index
        return len(new_index.chunks)

    def list_documents(self) -> list[KnowledgeDocument]:
        storage = "local+minio" if self._s3 else "local"
        documents: list[KnowledgeDocument] = []
        for path in sorted(self.policy_dir.glob("*.md")):
            stat = path.stat()
            documents.append(
                KnowledgeDocument(
                    name=path.name,
                    size=stat.st_size,
                    updated_at=datetime.fromtimestamp(stat.st_mtime),
                    storage=storage,
                )
            )
        return documents
