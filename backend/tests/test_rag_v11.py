from pathlib import Path

from services.rag_v1_index_service import bm25_dir_for
from services.rag_v1_pipeline import chunk_sections
from services.rag_v1_retrieval_service import _apply_rrf_scores, _review_allowed


def test_chunker_adds_v11_metadata():
    metadata = {
        "source_id": "CCI_PROCRASTINATION",
        "organization": "CCI",
        "title": "Procrastination",
        "year": 2025,
        "source_type": "workbook_and_sheets",
        "target_collection": "interventions",
        "topics": ["procrastination", "academic_stress"],
        "language": "en",
        "evidence_level": "B",
        "source_authority": "clinical_public_service",
        "review_priority": "P0",
        "user_facing": True,
        "official_page_url": "https://example.test",
        "downloaded_url": "https://example.test/file.pdf",
        "sha256": "abcdef123456",
        "review_status": "pending",
    }
    chunks = chunk_sections(
        source_id="CCI_PROCRASTINATION",
        metadata=metadata,
        sections=[{"section": "Worksheet", "content": "Step 1 choose one small task. Step 2 start for ten minutes."}],
        chunking_config={"target_chars": 100, "overlap_chars": 10, "min_chars": 10, "max_chars": 150},
    )

    assert chunks
    assert chunks[0]["content_sha256"] == chunks[0]["chunk_sha256"]
    assert chunks[0]["document_id"].startswith("CCI_PROCRASTINATION_")
    assert chunks[0]["chunk_type"] == "worksheet"
    assert chunks[0]["expected_collection"] == "interventions"
    assert chunks[0]["source_authority"] == "clinical_public_service"


def test_production_review_gate_excludes_pending():
    pending = {"review_status": "pending"}
    approved = {"review_status": "approved"}
    rejected = {"review_status": "rejected"}

    assert _review_allowed(pending, staging_mode=True, index_mode="staging") is True
    assert _review_allowed(approved, staging_mode=False, index_mode="production") is True
    assert _review_allowed(pending, staging_mode=True, index_mode="production") is False
    assert _review_allowed(rejected, staging_mode=True, index_mode="staging") is False


def test_rrf_scores_prefer_cross_signal_candidates():
    candidates = [
        {"chunk_id": "dense-only", "dense_rank": 1},
        {"chunk_id": "cross", "dense_rank": 2, "bm25_rank": 2},
        {"chunk_id": "bm25-only", "bm25_rank": 1},
    ]

    scored = _apply_rrf_scores(candidates, rrf_k=60)
    by_id = {item["chunk_id"]: item for item in scored}

    assert by_id["cross"]["rrf_score_norm"] > by_id["dense-only"]["rrf_score_norm"]
    assert by_id["cross"]["rrf_score_norm"] > by_id["bm25-only"]["rrf_score_norm"]


def test_bm25_dir_for_keeps_staging_root_backward_compatibility(tmp_path: Path):
    (tmp_path / "bm25_index.pkl").write_bytes(b"fake")
    (tmp_path / "documents.jsonl").write_text("{}", encoding="utf-8")

    assert bm25_dir_for(tmp_path, "staging", require_existing=True) == tmp_path
    assert bm25_dir_for(tmp_path, "production") == tmp_path / "production"
