from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from app.domain.models import PolicyEvidence


class DenseEmbedder(Protocol):
    def encode(self, sentences: list[str], **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class MilvusPolicyRecord:
    source: str
    section: str
    content: str

    @property
    def chunk_id(self) -> str:
        raw = f"{self.source}\n{self.section}\n{self.content}".encode()
        return hashlib.sha256(raw).hexdigest()


class MilvusHybridStore:
    """Milvus dense + BM25 hybrid retrieval adapter.

    The heavy dependencies and network connection are created only when the
    ``milvus`` backend is selected. Local tests can therefore keep using the
    dependency-light backend without requiring a running Milvus instance.
    """

    dense_dimensions = 1024

    def __init__(
        self,
        records: Iterable[MilvusPolicyRecord],
        *,
        uri: str,
        token: str,
        collection_name: str,
        tenant_id: str,
        model_name: str,
        client: Any | None = None,
        embedder: DenseEmbedder | None = None,
        sync_on_start: bool = True,
    ) -> None:
        self.records = list(records)
        self.collection_name = collection_name
        self.tenant_id = tenant_id

        if client is None:
            from pymilvus import MilvusClient

            client = MilvusClient(uri=uri, token=token)
        if embedder is None:
            from sentence_transformers import SentenceTransformer

            embedder = SentenceTransformer(model_name)

        self.client = client
        self.embedder = embedder
        self._ensure_collection()
        if sync_on_start:
            self.replace_tenant_records(self.records)

    def _ensure_collection(self) -> None:
        if self.client.has_collection(collection_name=self.collection_name):
            return

        from pymilvus import DataType, Function, FunctionType

        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(
            field_name="chunk_id",
            datatype=DataType.VARCHAR,
            max_length=64,
            is_primary=True,
        )
        schema.add_field(
            field_name="tenant_id",
            datatype=DataType.VARCHAR,
            max_length=128,
            is_partition_key=True,
        )
        schema.add_field(field_name="source", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field(field_name="section", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field(
            field_name="content",
            datatype=DataType.VARCHAR,
            max_length=8192,
            enable_analyzer=True,
        )
        schema.add_field(
            field_name="dense",
            datatype=DataType.FLOAT_VECTOR,
            dim=self.dense_dimensions,
        )
        schema.add_field(field_name="sparse", datatype=DataType.SPARSE_FLOAT_VECTOR)
        schema.add_function(
            Function(
                name="content_bm25",
                input_field_names=["content"],
                output_field_names=["sparse"],
                function_type=FunctionType.BM25,
            )
        )

        indexes = self.client.prepare_index_params()
        indexes.add_index(
            field_name="dense",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 128},
        )
        indexes.add_index(
            field_name="sparse",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="BM25",
            params={"inverted_index_algo": "DAAT_MAXSCORE"},
        )
        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=indexes,
            num_partitions=16,
        )

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self.embedder.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [
            vector.tolist() if hasattr(vector, "tolist") else list(vector) for vector in vectors
        ]

    def replace_tenant_records(self, records: list[MilvusPolicyRecord]) -> None:
        safe_tenant = self.tenant_id.replace('"', '\\"')
        self.client.delete(
            collection_name=self.collection_name,
            filter=f'tenant_id == "{safe_tenant}"',
        )
        if not records:
            return
        vectors = self._encode([f"{item.section} {item.content}" for item in records])
        rows = [
            {
                "chunk_id": item.chunk_id,
                "tenant_id": self.tenant_id,
                "source": item.source,
                "section": item.section,
                "content": item.content,
                "dense": vector,
            }
            for item, vector in zip(records, vectors, strict=True)
        ]
        self.client.upsert(collection_name=self.collection_name, data=rows)

    def search(self, query: str, top_k: int) -> list[PolicyEvidence]:
        from pymilvus import AnnSearchRequest, Function, FunctionType

        query_vector = self._encode([query])[0]
        safe_tenant = self.tenant_id.replace('"', '\\"')
        expr = f'tenant_id == "{safe_tenant}"'
        requests = [
            AnnSearchRequest(
                data=[query_vector],
                anns_field="dense",
                param={"metric_type": "COSINE", "params": {"ef": 64}},
                limit=max(top_k * 3, 12),
                expr=expr,
            ),
            AnnSearchRequest(
                data=[query],
                anns_field="sparse",
                param={"metric_type": "BM25", "params": {}},
                limit=max(top_k * 3, 12),
                expr=expr,
            ),
        ]
        ranker = Function(
            name="rrf",
            input_field_names=[],
            function_type=FunctionType.RERANK,
            params={"reranker": "rrf", "k": 60},
        )
        results = self.client.hybrid_search(
            collection_name=self.collection_name,
            reqs=requests,
            ranker=ranker,
            limit=top_k,
            output_fields=["source", "section", "content", "tenant_id"],
        )
        if not results:
            return []
        evidence: list[PolicyEvidence] = []
        for hit in results[0]:
            entity = hit.get("entity", {}) if isinstance(hit, dict) else hit.entity
            score = hit.get("distance", 0.0) if isinstance(hit, dict) else hit.distance
            evidence.append(
                PolicyEvidence(
                    source=entity["source"],
                    section=entity["section"],
                    content=entity["content"],
                    score=round(float(score), 4),
                )
            )
        return evidence
