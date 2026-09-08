import sys
import types
import zipfile
from pathlib import Path

import pytest

from schemas.errors import AppError
from services.document_parser_service import parse_document
from services.embedding_service import SentenceTransformerEmbeddingProvider
from services.knowledge_cleaning_service import clean_knowledge_text
from services.knowledge_download_service import KnowledgeDownloader, safe_extract_zip, sha256_file
from services.knowledge_source_registry import (
    domain_allowed,
    ensure_registry_directories,
    load_knowledge_source_registry,
)
from services.rag_v1_index_service import build_bm25_index, build_chroma_indexes, query_bm25, query_chroma
from services.rag_v1_pipeline import chunk_sections


def _registry_file(tmp_path: Path) -> Path:
    root = (tmp_path / "kb").as_posix()
    content = f"""
version: 1
registry_name: test_registry
paths:
  root: {root}
  raw_auto: {root}/raw/auto
  raw_manual: {root}/raw/manual
  parsed: {root}/parsed
  cleaned: {root}/cleaned
  chunks_pending: {root}/chunks/pending
  chunks_approved: {root}/chunks/approved
  chunks_rejected: {root}/chunks/rejected
  indexes_chroma: {root}/indexes/chroma
  indexes_bm25: {root}/indexes/bm25
  reports: {root}/reports
manual_drop_zones:
  - id: manual_textbooks
    path: {root}/raw/manual/textbooks
  - id: manual_papers
    path: {root}/raw/manual/papers
  - id: manual_campus
    path: {root}/raw/manual/campus
  - id: manual_cases
    path: {root}/raw/manual/cases
collections:
  professional_knowledge: {{}}
  interventions: {{}}
  helping_skills: {{}}
  campus_support: {{}}
  safety: {{}}
  evidence: {{}}
  governance: {{}}
  case_rag: {{}}
build_policy:
  minimum_delay_seconds_per_domain: 0
  request_timeout_seconds: 5
processing_policy:
  chunking:
    target_chars: 120
    overlap_chars: 20
    min_chars: 20
    max_chars: 220
sources:
  - id: WHO_MHGAP_2023
    enabled: true
    auto_download: true
    organization: WHO
    title: mhGAP
    year: 2023
    source_type: guideline
    target_collection: safety
    topics: [safety]
    language_preference: [en]
    evidence_level: A
    user_facing: false
    official_page_url: https://www.who.int/publications/test
    download:
      mode: html_page
      allowed_domains: [who.int, www.who.int]
      max_assets: 1
"""
    path = tmp_path / "registry.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_registry_loader_and_manual_drop_zones(tmp_path: Path):
    registry = load_knowledge_source_registry(_registry_file(tmp_path))
    assert len(registry.sources) == 1
    assert registry.sources[0].target_collection == "safety"
    ensure_registry_directories(registry)
    assert registry.paths["raw_auto"].exists()
    assert (registry.paths["raw_manual"] / "cases").exists()


def test_domain_allowlist():
    assert domain_allowed("https://www.who.int/a", ["who.int"])
    assert not domain_allowed("https://example.com/a", ["who.int"])


def test_redirect_domain_validation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    registry = load_knowledge_source_registry(_registry_file(tmp_path))
    downloader = KnowledgeDownloader(registry)
    monkeypatch.setattr(downloader, "_check_can_fetch", lambda url: None)
    monkeypatch.setattr(downloader, "_wait_for_domain", lambda url: None)

    class FakeResponse:
        url = "https://evil.example/file.pdf"
        status_code = 200
        headers = {"content-type": "application/pdf"}
        content = b"x"
        text = "x"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(downloader.session, "get", lambda *args, **kwargs: FakeResponse())
    with pytest.raises(AppError) as exc:
        downloader._get("https://www.who.int/publications/test", registry.sources[0])
    assert exc.value.detail.code == "redirect_domain_not_allowed"


def test_sha256_deduplication(tmp_path: Path):
    left = tmp_path / "a.txt"
    right = tmp_path / "b.txt"
    left.write_text("same", encoding="utf-8")
    right.write_text("same", encoding="utf-8")
    assert sha256_file(left) == sha256_file(right)


def test_safe_zip_extract_blocks_zip_slip(tmp_path: Path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("../escape.txt", "nope")
    with pytest.raises(AppError) as exc:
        safe_extract_zip(archive, tmp_path / "out")
    assert exc.value.detail.code == "unsafe_zip_member"


def test_html_cleaner_and_parser(tmp_path: Path):
    path = tmp_path / "page.html"
    path.write_text(
        "<html><head><title>Stress</title><script>x</script></head>"
        "<body><nav>menu</nav><h1>Stress help</h1><p>  Take one small step.  </p>"
        "<footer>footer</footer></body></html>",
        encoding="utf-8",
    )
    parsed = parse_document(path, {"title": "Stress"})
    cleaned, issues = clean_knowledge_text(parsed.raw_text)
    assert "Take one small step." in cleaned
    assert "menu" not in cleaned
    assert issues == []


def test_pdf_parser(tmp_path: Path):
    from pypdf import PdfWriter

    path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with path.open("wb") as handle:
        writer.write(handle)
    parsed = parse_document(path, {"title": "Blank PDF"})
    assert parsed.title == "Blank PDF"


def test_chunker_metadata_preserved_and_safety_separated():
    metadata = {
        "source_id": "WHO_MHGAP_2023",
        "organization": "WHO",
        "title": "mhGAP",
        "year": 2023,
        "source_type": "guideline",
        "target_collection": "safety",
        "topics": ["self_harm", "suicide"],
        "language": "en",
        "evidence_level": "A",
        "user_facing": False,
        "official_page_url": "https://www.who.int/test",
        "downloaded_url": "https://www.who.int/test",
        "sha256": "abc",
        "review_status": "pending",
    }
    chunks = chunk_sections(
        source_id="WHO_MHGAP_2023",
        metadata=metadata,
        sections=[{"section": "Safety", "content": "Step 1 stay with the person. Step 2 contact local emergency support."}],
        chunking_config={"target_chars": 80, "overlap_chars": 10, "min_chars": 10, "max_chars": 160},
    )
    assert chunks
    assert chunks[0]["target_collection"] == "safety"
    assert chunks[0]["user_facing"] is False
    assert chunks[0]["review_status"] == "pending"


def test_embedding_provider_with_fake_sentence_transformer(monkeypatch: pytest.MonkeyPatch):
    fake_module = types.ModuleType("sentence_transformers")

    class FakeSentenceTransformer:
        def __init__(self, *args, **kwargs):
            pass

        def encode(self, texts, **kwargs):
            return [[1.0, 0.0, 0.0] for _ in texts]

    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    provider = SentenceTransformerEmbeddingProvider("fake-model")
    vectors = provider._encode(["hello", "world"])
    assert vectors == [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]


def test_bm25_index(tmp_path: Path):
    chunks = [
        {"chunk_id": "a", "content": "论文 拖延 开始", "source_id": "s1", "title": "A", "section": "S", "target_collection": "interventions"},
        {"chunk_id": "b", "content": "sleep routine", "source_id": "s2", "title": "B", "section": "S", "target_collection": "interventions"},
    ]
    build_bm25_index(chunks, tmp_path)
    results = query_bm25(tmp_path, "论文拖延怎么办", top_k=1)
    assert results[0]["chunk_id"] == "a"


def test_bm25_index_uses_topic_alias_search_text(tmp_path: Path):
    chunks = [
        {
            "chunk_id": "career",
            "content": "Values and problem solving can help when choices feel hard.",
            "source_id": "s1",
            "title": "Problem solving",
            "section": "S",
            "target_collection": "interventions",
            "topic_tags": ["career_uncertainty", "problem_solving"],
            "population_tags": ["young_adults"],
        },
        {
            "chunk_id": "sleep",
            "content": "Sleep hygiene and bedtime routine.",
            "source_id": "s2",
            "title": "Sleep",
            "section": "S",
            "target_collection": "interventions",
            "topic_tags": ["sleep"],
        },
    ]

    build_bm25_index(chunks, tmp_path)
    results = query_bm25(tmp_path, "未来迷茫，不知道以后做什么", top_k=1)

    assert results[0]["chunk_id"] == "career"
    assert "未来迷茫" not in results[0]["content"]


def test_chunker_derives_fine_grained_topic_tags_from_content():
    metadata = {
        "source_id": "UNICEF_PARENTING_MH",
        "organization": "UNICEF",
        "title": "Parent and caregiver mental health support",
        "year": 2026,
        "source_type": "official_web_guide",
        "target_collection": "professional_knowledge",
        "topic_tags": ["parent_child_relationship", "communication"],
        "population_tags": ["parents", "children"],
        "use_mode": "direct_user_support",
        "risk_scope": "normal",
        "review_status": "pending",
    }

    chunks = chunk_sections(
        source_id="UNICEF_PARENTING_MH",
        metadata=metadata,
        sections=[
            {
                "section": "Teen support",
                "content": "How to help your teenager manage a meltdown and express emotions during tough situations.",
            }
        ],
        chunking_config={"target_chars": 200, "overlap_chars": 20, "min_chars": 20, "max_chars": 240},
    )

    assert chunks
    assert "emotion_regulation" in chunks[0]["topic_tags"]
    assert "distress_tolerance" in chunks[0]["topic_tags"]
    assert "adolescents" in chunks[0]["population_tags"]


def test_chroma_persistence(tmp_path: Path):
    chunks = [
        {"chunk_id": "a", "content": "thesis procrastination", "source_id": "s1", "title": "A", "section": "S", "target_collection": "interventions"},
        {"chunk_id": "b", "content": "sleep routine", "source_id": "s2", "title": "B", "section": "S", "target_collection": "interventions"},
    ]
    build_chroma_indexes(chunks, [[1.0, 0.0], [0.0, 1.0]], tmp_path)
    results = query_chroma(tmp_path, [1.0, 0.0], top_k=1, collection="interventions")
    assert results[0]["chunk_id"] == "a"
