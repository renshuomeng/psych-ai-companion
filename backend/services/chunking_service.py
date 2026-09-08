import hashlib
import re
from typing import Any

from config import get_settings


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_sentences(text: str) -> list[str]:
    pieces = re.split(r"(?<=[。！？!?；;])\s*", text.strip())
    return [piece.strip() for piece in pieces if piece.strip()]


def _window_text(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    sentences = _split_sentences(text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) <= size:
            current = f"{current}{sentence}" if current else sentence
            continue
        if current:
            chunks.append(current)
            tail = current[-overlap:] if overlap > 0 else ""
            current = f"{tail}{sentence}"
        else:
            chunks.append(sentence[:size])
            current = sentence[max(0, size - overlap) :]
    if current:
        chunks.append(current[: size + overlap])
    return chunks


def chunk_document(
    source_id: str,
    title: str,
    topic: str,
    sections: list[dict[str, str]],
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    size = max(settings.rag_chunk_size, 120)
    overlap = min(max(settings.rag_chunk_overlap, 0), size // 2)
    chunks: list[dict[str, Any]] = []
    normalized_metadata = metadata or {}
    psychological_fields = {
        "emotion": normalized_metadata.get("emotion", []),
        "cause": normalized_metadata.get("cause", ""),
        "strategy": normalized_metadata.get("strategy", []),
        "risk_level": normalized_metadata.get("risk_level", "low"),
        "intervention": normalized_metadata.get("intervention", []),
    }

    for section in sections:
        section_title = section.get("section") or title
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", section.get("content", "")) if p.strip()]
        buffer = ""
        for paragraph in paragraphs:
            candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
            if len(candidate) <= size:
                buffer = candidate
                continue
            if buffer:
                for piece in _window_text(buffer, size, overlap):
                    chunks.append(
                        {
                            "source_id": source_id,
                            "title": title,
                            "section": section_title,
                            "topic": topic,
                            "content": piece,
                            "metadata": normalized_metadata,
                            **psychological_fields,
                        }
                    )
            buffer = paragraph
        if buffer:
            for piece in _window_text(buffer, size, overlap):
                chunks.append(
                    {
                        "source_id": source_id,
                        "title": title,
                        "section": section_title,
                        "topic": topic,
                        "content": piece,
                        "metadata": normalized_metadata,
                        **psychological_fields,
                    }
                )

    for index, chunk in enumerate(chunks):
        digest = content_hash(f"{source_id}:{index}:{chunk['content']}")[:16]
        chunk["chunk_index"] = index
        chunk["chunk_id"] = f"{source_id}_{index:04d}_{digest}"
        chunk["content_hash"] = content_hash(chunk["content"])
    return chunks
