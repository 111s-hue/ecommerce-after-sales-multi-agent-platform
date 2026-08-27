from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from app.domain.models import PolicyEvidence
from app.services.milvus_store import MilvusHybridStore, MilvusPolicyRecord


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    latin = re.findall(r"[a-z0-9_-]+", lowered)
    chinese = re.findall(r"[\u4e00-\u9fff]", lowered)
    bigrams = ["".join(chinese[i : i + 2]) for i in range(max(0, len(chinese) - 1))]
    return latin + chinese + bigrams


@dataclass(frozen=True)
class PolicyChunk:
    source: str
    section: str
    content: str


class HashedDenseIndex:
    """Dependency-light semantic-ish index used when BGE is not installed."""

    dimensions = 384

    def __init__(self, chunks: list[PolicyChunk]):
        self.chunks = chunks
        self.matrix = np.vstack(
            [self._embed(f"{chunk.section} {chunk.content}") for chunk in chunks]
        )

    def _embed(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dimensions, dtype=np.float32)
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "little") % self.dimensions
            vector[index] += 1.0
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector

    def scores(self, query: str) -> np.ndarray:
        return self.matrix @ self._embed(query)


class BGEFaissIndex:
    """Optional production adapter. Imports large dependencies only when selected."""

    def __init__(self, chunks: list[PolicyChunk], model_name: str, index_dir: Path | None = None):
        import faiss
        from sentence_transformers import SentenceTransformer

        self.chunks = chunks
        self.faiss = faiss
        self.model = SentenceTransformer(model_name)
        fingerprint = hashlib.sha256(
            json.dumps(
                [chunk.__dict__ for chunk in chunks], ensure_ascii=False, sort_keys=True
            ).encode("utf-8")
        ).hexdigest()
        index_path = index_dir / "policies.faiss" if index_dir else None
        manifest_path = index_dir / "policies.manifest.json" if index_dir else None
        if (
            index_path
            and manifest_path
            and index_path.exists()
            and manifest_path.exists()
            and json.loads(manifest_path.read_text(encoding="utf-8")).get("fingerprint")
            == fingerprint
        ):
            self.index = faiss.read_index(str(index_path))
        else:
            vectors = self.model.encode(
                [f"{chunk.section} {chunk.content}" for chunk in chunks],
                normalize_embeddings=True,
                show_progress_bar=False,
            ).astype("float32")
            self.index = faiss.IndexFlatIP(vectors.shape[1])
            self.index.add(vectors)
            if index_path and manifest_path:
                index_dir.mkdir(parents=True, exist_ok=True)
                faiss.write_index(self.index, str(index_path))
                manifest_path.write_text(
                    json.dumps(
                        {"fingerprint": fingerprint, "chunks": len(chunks)},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

    def scores(self, query: str) -> np.ndarray:
        vector = self.model.encode([query], normalize_embeddings=True).astype("float32")
        distances, indices = self.index.search(vector, len(self.chunks))
        scores = np.zeros(len(self.chunks), dtype=np.float32)
        for index, score in zip(indices[0], distances[0], strict=True):
            if index >= 0:
                scores[index] = score
        return scores


class PolicyKnowledgeBase:
    def __init__(
        self,
        policy_dir: Path,
        *,
        backend: str = "hybrid-lite",
        bge_model: str = "BAAI/bge-m3",
        index_dir: Path | None = None,
        milvus_uri: str = "http://localhost:19530",
        milvus_token: str = "root:Milvus",
        milvus_collection: str = "after_sales_policies",
        tenant_id: str = "demo",
    ):
        self.chunks = self._load_chunks(policy_dir)
        if not self.chunks:
            raise ValueError(f"政策目录中没有可用 Markdown 文档: {policy_dir}")
        self.remote: MilvusHybridStore | None = None
        if backend == "milvus":
            self.remote = MilvusHybridStore(
                [MilvusPolicyRecord(**chunk.__dict__) for chunk in self.chunks],
                uri=milvus_uri,
                token=milvus_token,
                collection_name=milvus_collection,
                tenant_id=tenant_id,
                model_name=bge_model,
            )
            self.bm25 = None
            self.dense = None
        else:
            self.bm25 = BM25Okapi(
                [tokenize(f"{chunk.section} {chunk.content}") for chunk in self.chunks]
            )
            self.dense = (
                BGEFaissIndex(self.chunks, bge_model, index_dir)
                if backend == "bge-faiss"
                else HashedDenseIndex(self.chunks)
            )

    @staticmethod
    def _load_chunks(policy_dir: Path) -> list[PolicyChunk]:
        chunks: list[PolicyChunk] = []
        for path in sorted(policy_dir.glob("*.md")):
            current_section = path.stem
            buffer: list[str] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("#"):
                    if buffer:
                        content = "\n".join(buffer).strip()
                        if content:
                            chunks.append(PolicyChunk(path.name, current_section, content))
                    current_section = line.lstrip("# ").strip()
                    buffer = []
                else:
                    buffer.append(line)
            content = "\n".join(buffer).strip()
            if content:
                chunks.append(PolicyChunk(path.name, current_section, content))
        return chunks

    @staticmethod
    def _normalize(values: np.ndarray) -> np.ndarray:
        if len(values) == 0:
            return values
        low, high = float(values.min()), float(values.max())
        if math.isclose(low, high):
            return np.ones_like(values) if high > 0 else np.zeros_like(values)
        return (values - low) / (high - low)

    @staticmethod
    def rewrite_query(query: str) -> str:
        replacements = {
            "七天": "7天 无理由 退货",
            "多久": "时效 天数",
            "运费谁出": "退货 运费 责任",
        }
        rewritten = query
        for source, target in replacements.items():
            rewritten = rewritten.replace(source, target)
        return rewritten

    def search(self, query: str, top_k: int = 4) -> list[PolicyEvidence]:
        rewritten = self.rewrite_query(query)
        if self.remote is not None:
            return self.remote.search(rewritten, top_k)
        assert self.bm25 is not None
        assert self.dense is not None
        bm25_scores = np.asarray(self.bm25.get_scores(tokenize(rewritten)), dtype=np.float32)
        dense_scores = np.asarray(self.dense.scores(rewritten), dtype=np.float32)
        # Reciprocal-rank-style fusion plus normalized semantic score.
        bm25_rank = np.argsort(np.argsort(-bm25_scores))
        dense_rank = np.argsort(np.argsort(-dense_scores))
        fused = 1 / (60 + bm25_rank) + 1 / (60 + dense_rank)
        fused += 0.15 * self._normalize(bm25_scores) + 0.15 * self._normalize(dense_scores)
        indices = np.argsort(-fused)[:top_k]
        return [
            PolicyEvidence(
                source=self.chunks[index].source,
                section=self.chunks[index].section,
                content=self.chunks[index].content,
                score=round(float(fused[index]), 4),
            )
            for index in indices
            if fused[index] > 0
        ]
