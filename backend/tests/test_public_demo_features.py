from services.auth_service import create_access_token, verify_access_token
from services.rag_service import retrieve_context
from agents.risk_agent import assess_risk, assess_risk_sources


def test_access_token_verification():
    token = create_access_token("session-a", 4_102_444_800)
    assert verify_access_token(token)["sid"] == "session-a"
    assert verify_access_token(token + "tampered") is None


def test_rag_retrieves_sleep_source():
    result = retrieve_context("最近晚上睡不着，想改善睡眠。")
    documents = result["documents"]
    assert documents
    assert documents[0]["source_id"] in {"CCI_SLEEP", "NHS_SLEEP", "kb_sleep_001"}
    if result.get("retrieval_mode") == "rag_v1_hybrid_bilingual":
        assert documents[0].get("citation_label") == "来源1"


def test_negated_suicide_context_is_not_high():
    result = assess_risk("我没有想自杀，只是最近论文压力很大。")
    assert result["level"] == "low"
    assert result["context"] == "negated_high_risk"


def test_reported_friend_suicide_context_is_medium():
    result = assess_risk_sources({"user_text": "朋友说他不想活了，我很担心。"})
    assert result["level"] == "medium"
    assert result["context"] == "reported_or_quoted"
