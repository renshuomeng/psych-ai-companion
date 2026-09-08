import hashlib
import math
import re
from abc import ABC, abstractmethod
from typing import Iterable

from config import get_settings
from schemas.errors import AppError


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError


def _tokens(text: str) -> Iterable[str]:
    normalized = text.lower()
    for word in re.findall(r"[a-zA-Z0-9_]+", normalized):
        yield word
    chars = [ch for ch in normalized if "\u4e00" <= ch <= "\u9fff"]
    for ch in chars:
        yield ch
    for i in range(len(chars) - 1):
        yield "".join(chars[i : i + 2])


class LocalHashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embedding for offline demos; it is not a random vector generator."""

    def __init__(self, dimensions: int = 384):
        self.dimensions = max(dimensions, 64)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _tokens(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + min(len(token), 4) * 0.05
            vector[index] += sign * weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [round(value / norm, 6) for value in vector]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Real local embedding provider used by the offline RAG V1 build pipeline."""

    def __init__(self, model_name: str, cache_dir: str | None = None, batch_size: int = 16):
        self.model_name = model_name
        self.batch_size = max(int(batch_size or 16), 1)
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:
            raise AppError(
                "embedding_model_download_failed",
                "sentence-transformers is required for RAG V1 local embeddings; no fake embedding fallback is used.",
                "embedding",
                status_code=503,
            ) from exc
        try:
            self.model = SentenceTransformer(model_name, cache_folder=cache_dir)
        except Exception as exc:
            raise AppError(
                "embedding_model_download_failed",
                f"Failed to load embedding model {model_name}: {exc}",
                "embedding",
                status_code=503,
            ) from exc

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [[float(value) for value in row] for row in vectors]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    async def embed_query(self, text: str) -> list[float]:
        return self._encode([text])[0]


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    provider = settings.embedding_provider.strip().lower()
    if provider == "local":
        return LocalHashingEmbeddingProvider(settings.embedding_dimensions)
    raise AppError(
        "embedding_provider_unavailable",
        f"当前未配置可用 embedding provider：{settings.embedding_provider}",
        "embedding",
        status_code=503,
    )


def get_rag_v1_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    provider = settings.rag_embedding_provider.strip().lower()
    if provider in {"local", "sentence_transformers", "sentence-transformers"}:
        settings.resolved_rag_embedding_cache_dir.mkdir(parents=True, exist_ok=True)
        return SentenceTransformerEmbeddingProvider(
            settings.rag_embedding_model,
            cache_dir=str(settings.resolved_rag_embedding_cache_dir),
            batch_size=settings.rag_embedding_batch_size,
        )
    raise AppError(
        "embedding_provider_unavailable",
        f"RAG V1 embedding provider is not supported: {settings.rag_embedding_provider}",
        "embedding",
        status_code=503,
    )


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return float(sum(a * b for a, b in zip(left, right)))
