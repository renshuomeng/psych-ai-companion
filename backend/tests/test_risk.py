from agents.risk_agent import assess_risk, assess_risk_sources


def test_high_risk_text():
    result = assess_risk("我不想活了，感觉一切都没有意义。")
    assert result["level"] == "high"
    assert result["action"] == "crisis_referral"


def test_visual_cue_alone_is_not_high_risk():
    result = assess_risk_sources({"image_visual": "画面中有人低头、皱眉，房间较暗。"})
    assert result["level"] == "low"


def test_audio_transcript_high_risk():
    result = assess_risk_sources({"audio_transcript": "我想死，真的撑不住了。"})
    assert result["level"] == "high"
    assert "audio_transcript" in result["matched_sources"]


def test_suicide_debug_terms_trigger_crisis_referral():
    result = assess_risk("我想轻生，已经开始写遗书了。")
    assert result["level"] == "high"
    assert result["action"] == "crisis_referral"
    assert "轻生" in result["matched_terms"]


def test_self_harm_method_debug_terms_trigger_crisis_referral():
    result = assess_risk("我想吞药结束这一切。")
    assert result["level"] == "high"
    assert result["action"] == "crisis_referral"
