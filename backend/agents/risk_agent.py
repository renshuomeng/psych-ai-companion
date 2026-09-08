HIGH_RISK_KEYWORDS = [
    "不想活",
    "自杀",
    "轻生",
    "死了算了",
    "活着没意思",
    "活不下去",
    "结束生命",
    "结束自己",
    "结束这一切",
    "自我了断",
    "想死",
    "伤害自己",
    "自残",
    "割腕",
    "吞药",
    "上吊",
    "跳楼",
    "跳河",
    "跳桥",
    "跳海",
    "寻死",
    "遗书",
    "再也不想醒来",
    "不想再撑",
    "不想撑",
    "撑不下去",
    "不再撑下去",
    "杀人",
    "报复社会",
    "伤害别人",
    "伤害他人",
    "kill myself",
    "suicide",
    "end my life",
    "hurt myself",
    "harm myself",
    "want to die",
]

SAFETY_DEBUG_PHRASES = [
    "我有自杀的想法，怕自己会伤害自己。",
    "我想轻生，已经开始写遗书了。",
    "我想吞药结束这一切。",
    "我想从楼上跳下去。",
    "我想报复社会，伤害别人。",
]

MEDIUM_RISK_KEYWORDS = [
    "崩溃",
    "撑不住",
    "绝望",
    "失控",
    "严重失眠",
    "很痛苦",
]


NEGATION_PREFIXES = ["没有", "没", "并不", "不是", "不"]
REPORT_CONTEXT_MARKERS = [
    "朋友说",
    "同学说",
    "室友说",
    "新闻",
    "小说",
    "电影",
    "台词",
    "歌词",
    "引用",
    "转述",
    "看到别人说",
    "有人说",
    "my friend said",
    "news said",
    "quote",
]
DIRECT_INTENT_MARKERS = ["我想", "我要", "我准备", "我计划", "我打算", "现在就", "已经", "i want", "i will", "i plan"]
PLAN_MARKERS = ["准备", "计划", "打算", "已经", "写遗书", "选好了", "决定", "plan", "decided"]
TIMEFRAME_MARKERS = ["今晚", "今天", "现在", "马上", "明天", "这周", "凌晨", "一会儿", "tonight", "today", "now", "soon"]
MEANS_MARKERS = ["药", "刀", "绳", "楼", "桥", "河", "海", "煤气", "遗书", "车", "pills", "knife", "rope"]
HARM_TO_OTHERS_MARKERS = ["杀人", "报复社会", "伤害别人", "伤害他人", "弄死"]


def _is_negated(text: str, keyword: str) -> bool:
    if keyword == "不想活":
        return any(phrase in text for phrase in ["没有不想活", "不是不想活", "并不是不想活"])
    index = text.find(keyword)
    if index < 0:
        return False
    window = text[max(0, index - 8) : index + len(keyword) + 8]
    if any(f"{prefix}{keyword}" in window for prefix in NEGATION_PREFIXES):
        return True
    if any(prefix in window[:8] for prefix in ["没有", "没", "并不"]):
        return True
    if any(phrase in window for phrase in ["没有自杀的想法", "没有伤害自己的想法", "不想死"]):
        return True
    return False


def _is_report_or_quote_context(text: str) -> bool:
    normalized = text.lower()
    if not any(marker.lower() in normalized for marker in REPORT_CONTEXT_MARKERS):
        return False
    if any(marker in normalized for marker in ["小说", "电影", "台词", "歌词", "引用", "quote"]):
        return True
    return not any(marker.lower() in normalized for marker in DIRECT_INTENT_MARKERS)


def _risk_dimensions(text: str, matched_high: list[str], negated: bool, reported: bool) -> dict[str, object]:
    normalized = text.lower()
    means_terms = [word for word in MEANS_MARKERS if word.lower() in normalized]
    timeframe_terms = [word for word in TIMEFRAME_MARKERS if word.lower() in normalized]
    plan_terms = [word for word in PLAN_MARKERS if word.lower() in normalized]
    harm_to_others = any(word in text for word in HARM_TO_OTHERS_MARKERS)
    ideation = bool(matched_high) and not negated
    plan = bool(plan_terms) and ideation
    means_access: object = "present" if means_terms and ideation else "unknown"
    if not ideation:
        means_access = "none"
    immediacy = "high" if ideation and timeframe_terms else "medium" if ideation else "low"
    return {
        "ideation": ideation,
        "plan": plan,
        "timeframe_present": bool(timeframe_terms) and ideation,
        "means_access": means_access,
        "immediacy": immediacy,
        "harm_to_others": harm_to_others and not negated,
        "negated": negated,
        "quotation_or_reference": reported,
        "third_party_report": reported,
        "matched_plan_terms": plan_terms,
        "matched_timeframe_terms": timeframe_terms,
        "matched_means_terms": means_terms,
    }


def _evidence_for_sources(sources: dict[str, str], terms: list[str]) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    for source, text in sources.items():
        for term in terms:
            normalized = text.lower()
            if term.lower() in normalized:
                index = normalized.find(term.lower())
                window = text[max(0, index - 30) : index + len(term) + 30]
                evidence.append({"source": source, "content": window})
                break
    return evidence


def assess_risk_sources(sources: dict[str, str]) -> dict[str, object]:
    normalized_sources = {
        source: text.strip() for source, text in sources.items() if text and text.strip()
    }
    combined = "\n".join(normalized_sources.values())
    combined_for_match = combined.lower()

    matched_high = [
        word
        for word in HIGH_RISK_KEYWORDS
        if word.lower() in combined_for_match and not _is_negated(combined_for_match, word.lower())
    ]
    negated_high = [
        word
        for word in HIGH_RISK_KEYWORDS
        if word.lower() in combined_for_match and _is_negated(combined_for_match, word.lower())
    ]
    if matched_high:
        matched_sources = [
            source
            for source, text in normalized_sources.items()
            if any(word.lower() in text.lower() for word in matched_high)
        ]
        reported = all(_is_report_or_quote_context(normalized_sources[source]) for source in matched_sources)
        dimensions = _risk_dimensions(combined, matched_high, False, reported)
        evidence = _evidence_for_sources(normalized_sources, matched_high)
        if reported:
            return {
                "level": "medium",
                "reason": "检测到转述或引用中的高危表达，需要温和确认当事人当前安全",
                "action": "support_with_monitoring",
                "matched_sources": matched_sources,
                "matched_terms": matched_high,
                "context": "reported_or_quoted",
                "dimensions": dimensions,
                "evidence": evidence,
            }
        return {
            "level": "high",
            "reason": "检测到可能的自伤、自杀或伤害他人表达",
            "action": "crisis_referral",
            "matched_sources": matched_sources,
            "matched_terms": matched_high,
            "dimensions": dimensions,
            "evidence": evidence,
        }

    matched_medium = [word for word in MEDIUM_RISK_KEYWORDS if word in combined]
    if matched_medium:
        matched_sources = [
            source
            for source, text in normalized_sources.items()
            if any(word in text for word in matched_medium)
        ]
        dimensions = _risk_dimensions(combined, [], False, False)
        return {
            "level": "medium",
            "reason": f"检测到明显痛苦或失控相关表达：{', '.join(matched_medium)}",
            "action": "support_with_monitoring",
            "matched_sources": matched_sources,
            "matched_terms": matched_medium,
            "dimensions": {**dimensions, "immediacy": "low"},
            "evidence": _evidence_for_sources(normalized_sources, matched_medium),
        }

    dimensions = _risk_dimensions(combined, negated_high, bool(negated_high), False)
    return {
        "level": "low",
        "reason": "没有出现自伤、自杀或伤害他人的当前意图表达"
        if negated_high
        else "没有出现自伤、自杀或伤害他人的表达",
        "action": "normal_support",
        "matched_sources": [],
        "matched_terms": [],
        "context": "negated_high_risk" if negated_high else "none",
        "dimensions": dimensions,
        "evidence": _evidence_for_sources(normalized_sources, negated_high) if negated_high else [],
    }


def assess_risk(message: str) -> dict[str, object]:
    return assess_risk_sources({"user_text": message})
