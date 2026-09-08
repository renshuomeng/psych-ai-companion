import pytest


def test_rag_v1_rewrites_chinese_query_to_bilingual_terms():
    from services.rag_v1_retrieval_service import rewrite_query_multilingual

    result = rewrite_query_multilingual("论文拖延得很严重，晚上也睡不着，怎么办？")

    assert result["contains_chinese"] is True
    assert "academic_stress" in result["matched_topics"]
    assert "sleep" in result["matched_topics"]
    assert "procrastination" in result["expanded_query"]
    assert "sleep hygiene" in result["expanded_query"]


def test_rag_v1_rewrite_infers_specific_populations():
    from services.rag_v1_retrieval_service import rewrite_query_multilingual

    result = rewrite_query_multilingual("退休以后经常一个人在家，觉得很孤独。")

    assert "loneliness" in result["matched_topics"]
    assert "older_adults" in result["implied_populations"]
    assert "social isolation" in result["expanded_query"]


def test_v2_context_boost_prefers_compatible_topics_and_populations():
    from services.rag_v1_retrieval_service import _apply_v2_context_boosts, rewrite_query_multilingual

    rewrite = rewrite_query_multilingual("我很容易生气，和父母说两句就吵起来。")
    items = [
        {
            "chunk_id": "parenting",
            "title": "Parenting",
            "topic_tags": ["parent_child_relationship", "communication"],
            "population_tags": ["parents", "children"],
            "rerank_score": 0.8,
        },
        {
            "chunk_id": "emotion",
            "title": "Emotion regulation",
            "topic_tags": ["emotion_regulation", "distress_tolerance"],
            "population_tags": ["adolescents"],
            "rerank_score": 0.78,
        },
    ]

    boosted = _apply_v2_context_boosts(items, rewrite=rewrite)

    assert boosted[0]["chunk_id"] == "emotion"
    assert boosted[0]["v2_context_boost"] > boosted[1].get("v2_context_boost", 0)


def test_population_filter_removes_mismatched_sources_when_compatible_results_exist():
    from services.rag_v1_retrieval_service import _filter_specific_population_matches, rewrite_query_multilingual

    rewrite = rewrite_query_multilingual("最近加班很多，和同事沟通也累，我感觉快撑不住了。")
    desired = set(rewrite["implied_populations"])
    items = [
        {"chunk_id": "work", "population_tags": ["workers", "adults"], "rerank_score": 0.7},
        {"chunk_id": "parenting", "population_tags": ["parents", "children"], "rerank_score": 0.9},
    ]

    filtered = _filter_specific_population_matches(items, desired)

    assert [item["chunk_id"] for item in filtered] == ["work"]


@pytest.mark.asyncio
async def test_chat_rag_uses_v1_when_index_is_ready():
    from services.rag_service import retrieve_context_async

    result = await retrieve_context_async(
        "我最近论文一直拖延，越拖越焦虑，可以先做什么？",
        top_k=2,
        session_id="test_rag_v1_chat",
        psychological_context={
            "emotion": "anxiety",
            "cause": "academic_pressure",
            "strategy": "problem_solving",
            "risk_level": "low",
        },
    )

    if result["retrieval_status"] == "index_not_ready":
        pytest.skip("RAG V1 index has not been built in this environment.")

    assert result["retrieval_mode"] == "rag_v1_hybrid_bilingual"
    assert result["retrieval_status"] == "success"
    assert result["documents"]
    assert result["documents"][0]["citation_label"] == "来源1"
    assert result["query_rewrite"]["en_terms"]
