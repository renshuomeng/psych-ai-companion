from agents.emotion_agent import analyze_emotion, infer_visual_emotion


def test_visual_happy_cue_can_drive_emotion_when_text_is_neutral():
    visual = infer_visual_emotion(["人物嘴角上扬，露出笑容。"], [])
    result = analyze_emotion("请分析这张照片。", face_emotion=visual)
    assert result["label"] == "joy"
    assert result["intensity"] >= 0.5
    assert result["dimensions"]["valence"]["label"] == "positive"


def test_visual_angry_candidate_can_drive_emotion_when_text_is_neutral():
    visual = infer_visual_emotion(
        [],
        [{"label": "anger", "confidence": 0.78, "evidence": "皱眉、咬牙、表情紧绷"}],
    )
    result = analyze_emotion("这个视频是我现在的状态，请分析一下。", face_emotion=visual)
    assert result["label"] == "anger"
    assert "视觉表情线索" in result["evidence"]
    assert result["dimensions"]["arousal"]["label"] == "high"


def test_text_emotion_takes_priority_over_visual_cue():
    visual = infer_visual_emotion(["人物露出笑容。"], [])
    result = analyze_emotion("最近论文压力很大。", face_emotion=visual)
    assert result["label"] == "anxiety"
    assert result["dimensions"]["control"]["label"] == "low"


def test_high_distress_text_is_not_neutral():
    result = analyze_emotion("我很绝望，甚至想要轻生")
    assert result["label"] == "sadness"
    assert result["intensity"] >= 0.9
    assert result["dimensions"]["valence"]["label"] == "negative"
    assert result["dimensions"]["control"]["label"] == "low"
    assert result["risk_relevant"] is True


def test_negated_self_harm_text_does_not_force_high_distress():
    result = analyze_emotion("我没有想过自杀，只是最近论文压力很大。")
    assert result["label"] == "anxiety"
    assert result["risk_relevant"] is False
