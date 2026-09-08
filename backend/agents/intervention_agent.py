import uuid
from typing import Any


INTERVENTION_LIBRARY = {
    "joy": [
        {
            "type": "strengthen_positive",
            "title": "记录积极线索",
            "description": "记下此刻让你感觉轻松或开心的一件小事，帮助自己保留这个积极线索。",
        },
        {
            "type": "gratitude_note",
            "title": "一句感谢",
            "description": "给自己或他人写一句简短感谢，延长这份正向体验。",
        },
        {
            "type": "gentle_plan",
            "title": "安排下一步",
            "description": "趁状态较稳定，安排一个小而具体的下一步任务，不需要过度消耗自己。",
        },
    ],
    "anxiety": [
        {
            "type": "breathing",
            "title": "3 分钟呼吸练习",
            "description": "吸气 4 秒，停顿 2 秒，呼气 6 秒，重复 5 轮。",
        },
        {
            "type": "task_breakdown",
            "title": "把任务拆到下一步",
            "description": "只写下接下来 15 分钟能完成的一件小事，不要求一次解决全部压力。",
        },
        {
            "type": "reframing",
            "title": "认知重评",
            "description": "把“我肯定不行”改写成“我正在处理一个有难度的任务，可以先做一小段”。",
        },
    ],
    "sadness": [
        {
            "type": "journal",
            "title": "情绪日记",
            "description": "用三句话写下此刻发生了什么、你的感受、你希望被怎样支持。",
        },
        {
            "type": "companionship",
            "title": "温和陪伴",
            "description": "允许自己先不急着振作，做一件低负担的小事，比如喝水或整理桌面。",
        },
        {
            "type": "social_support",
            "title": "联系一个朋友",
            "description": "给可信任的人发一句简单消息：我今天有点难受，能不能陪我聊 10 分钟？",
        },
    ],
    "anger": [
        {
            "type": "pause",
            "title": "暂停练习",
            "description": "先离开刺激源 3 分钟，避免在情绪高点立刻回复或做决定。",
        },
        {
            "type": "body_relax",
            "title": "身体放松",
            "description": "从肩膀、手掌到下颌逐步放松，观察身体哪里最紧。",
        },
        {
            "type": "trigger_note",
            "title": "写下触发点",
            "description": "记录让你生气的具体事件、你的期待、以及可以沟通的一句话。",
        },
    ],
    "fatigue": [
        {
            "type": "short_rest",
            "title": "短时休息",
            "description": "设置 10 分钟计时器，闭眼休息或离开屏幕，不用在休息时继续自责。",
        },
        {
            "type": "sleep_relax",
            "title": "睡前放松",
            "description": "睡前减少刺激性信息输入，尝试缓慢呼吸或轻柔拉伸。",
        },
        {
            "type": "low_intensity",
            "title": "低强度活动",
            "description": "做一件不消耗太多意志力的活动，例如散步、洗脸或简单收纳。",
        },
    ],
    "neutral": [
        {
            "type": "grounding",
            "title": "一分钟落地练习",
            "description": "说出你现在看见的 3 件物品、听见的 2 种声音、身体感到的 1 个触点。",
        }
    ],
    "loneliness": [
        {
            "type": "social_support",
            "title": "低负担联系",
            "description": "给一个可信任的人发一句很短的消息：我今天有点孤单，方便陪我聊几分钟吗？",
        },
        {
            "type": "companionship",
            "title": "陪伴式行动",
            "description": "做一件带有连接感的小事，比如去公共空间坐 10 分钟或给自己准备一杯热水。",
        },
    ],
    "stress": [
        {
            "type": "task_breakdown",
            "title": "5 分钟任务拆分",
            "description": "写下今天最小的一步，只保留一个动作，暂时不处理整个问题。",
        },
        {
            "type": "grounding",
            "title": "一分钟落地",
            "description": "说出眼前 3 件物品、听到的 2 种声音和身体 1 个触点，先把注意力拉回当下。",
        },
    ],
}


def recommend_interventions(
    emotion: dict[str, Any],
    checkin: dict[str, Any] | None = None,
    risk: dict[str, Any] | None = None,
    memory: dict[str, Any] | None = None,
    knowledge_sources: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if risk and risk.get("level") == "high":
        return [
            {
                "intervention_id": uuid.uuid4().hex,
                "type": "crisis_referral",
                "title": "危机转介优先",
                "description": "请优先联系身边可信任的人、学校辅导员、当地紧急服务或危机支持。",
                "reason": "当前风险等级为 high，普通练习不能替代现实支持。",
                "source_ids": [],
                "estimated_minutes": 1,
            }
        ]

    label = str(emotion.get("label", "neutral"))
    interventions = list(INTERVENTION_LIBRARY.get(label, INTERVENTION_LIBRARY["neutral"]))

    sources = []
    if checkin:
        sources = checkin.get("stress_sources") or checkin.get("stress_source", [])
    if "睡眠" in sources and label != "fatigue":
        interventions.append(
            {
                "type": "sleep_relax",
                "title": "睡眠困扰缓冲",
                "description": "今晚先做 5 分钟放松呼吸，暂时把未完成事项写到纸上，留到明天处理。",
            }
        )

    profile = (memory or {}).get("profile", {}) if memory else {}
    disliked = [str(item) for item in profile.get("disliked_interventions", []) or []]
    preferred = [str(item) for item in profile.get("preferred_interventions", []) or []]

    filtered = []
    for item in interventions:
        text = f"{item.get('type', '')}{item.get('title', '')}{item.get('description', '')}"
        if any(word and word in text for word in disliked):
            continue
        filtered.append(item)
    if not filtered:
        filtered = interventions[:1]

    source_ids = [str(item.get("source_id")) for item in knowledge_sources or [] if item.get("source_id")]
    personalized: list[dict[str, Any]] = []
    for item in filtered[:3]:
        is_preferred = any(word and word in f"{item['type']}{item['title']}" for word in preferred)
        personalized.append(
            {
                "intervention_id": uuid.uuid4().hex,
                **item,
                "reason": "结合当前情绪、压力来源和知识库建议生成；"
                + ("该方法与用户过往偏好一致。" if is_preferred else "暂未发现用户明确排斥该方法。"),
                "source_ids": source_ids[:3],
                "estimated_minutes": 5 if item["type"] in {"task_breakdown", "grounding"} else 10,
            }
        )

    return personalized
