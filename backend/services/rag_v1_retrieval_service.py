from __future__ import annotations

import json
import re
import time
from functools import lru_cache
from typing import Any

from config import get_settings
from database.db import SessionLocal, init_db
from schemas.errors import AppError
from services.embedding_service import get_rag_v1_embedding_provider
from services.knowledge_source_registry import load_knowledge_source_registry
from services.rag_v1_index_service import bm25_dir_for, normalize_index_mode, query_bm25, query_chroma
from services.reranker_service import rerank
from services.vector_store_service import log_retrieval


USER_FACING_COLLECTIONS = {"interventions", "professional_knowledge", "campus_support"}
USER_FACING_USE_MODES = {"direct_user_support"}
ORDINARY_RISK_SCOPES = {"", "normal", "general"}

MEDICATION_TERMS = {
    "药",
    "药物",
    "剂量",
    "吃多少",
    "用量",
    "服用",
    "加量",
    "减量",
    "停药",
    "阿普唑仑",
    "劳拉西泮",
    "舍曲林",
    "氟西汀",
    "帕罗西汀",
    "艾司西酞普兰",
    "佐匹克隆",
    "安眠药",
    "alprazolam",
    "lorazepam",
    "sertraline",
    "fluoxetine",
    "paroxetine",
    "escitalopram",
    "zopiclone",
    "dosage",
    "dose",
}
DIAGNOSIS_TERMS = {
    "诊断",
    "确诊",
    "是不是得了",
    "是不是抑郁症",
    "是不是焦虑症",
    "是不是双相",
    "是不是进食障碍",
    "算强迫症",
    "bpd",
    "bipolar",
    "diagnose",
    "diagnosis",
}
SAFETY_TERMS = {"自杀", "轻生", "自残", "自伤", "结束生命", "suicide", "self-harm", "kill myself"}
DANGEROUS_INSTRUCTION_TERMS = {
    "方法",
    "步骤",
    "教程",
    "最不痛苦",
    "怎么做",
    "教我",
    "how to",
    "method",
    "instructions",
}


QUERY_LEXICON: list[dict[str, Any]] = [
    {
        "topic": "academic_stress",
        "triggers": ["论文", "毕业", "开题", "导师", "课题", "科研", "作业", "学习", "考试", "绩点", "thesis", "study", "exam"],
        "zh_terms": ["学业压力", "任务拆分", "开始行动", "拖延", "完美主义"],
        "en_terms": [
            "academic stress",
            "thesis",
            "dissertation",
            "procrastination",
            "task breakdown",
            "study anxiety",
            "exam anxiety",
            "perfectionism",
        ],
    },
    {
        "topic": "career_anxiety",
        "triggers": [
            "就业",
            "找工作",
            "求职",
            "面试",
            "简历",
            "offer",
            "实习",
            "未来",
            "以后",
            "迷茫",
            "方向",
            "不知道以后",
            "不知道做什么",
            "career",
            "interview",
            "resume",
        ],
        "zh_terms": ["就业焦虑", "求职压力", "未来迷茫", "职业不确定", "问题解决", "不确定感"],
        "en_terms": [
            "career anxiety",
            "career uncertainty",
            "future uncertainty",
            "job search stress",
            "interview anxiety",
            "problem solving",
            "decision making",
            "uncertainty",
            "values",
        ],
    },
    {
        "topic": "sleep",
        "triggers": ["睡眠", "失眠", "睡不着", "熬夜", "噩梦", "入睡", "sleep", "insomnia", "nightmare"],
        "zh_terms": ["睡眠卫生", "睡前程序", "担忧反刍", "放松训练"],
        "en_terms": ["sleep", "insomnia", "sleep hygiene", "bedtime routine", "worry", "rumination", "relaxation"],
    },
    {
        "topic": "relationships",
        "triggers": ["人际", "室友", "朋友", "同学", "恋爱", "分手", "关系", "冲突", "边界", "relationship", "roommate"],
        "zh_terms": ["人际关系", "沟通", "边界", "社会焦虑", "支持系统"],
        "en_terms": [
            "relationships",
            "interpersonal conflict",
            "communication",
            "boundaries",
            "assertiveness",
            "social anxiety",
        ],
    },
    {
        "topic": "school_support",
        "triggers": ["上学", "不想去学校", "学校", "班里", "同学关系", "家长", "作业", "school", "classmate"],
        "zh_terms": ["学校支持", "学生心理健康", "上学适应", "家长支持", "亲子沟通"],
        "en_terms": [
            "school support",
            "student mental health",
            "school adjustment",
            "parent child relationship",
            "family communication",
        ],
    },
    {
        "topic": "loneliness",
        "triggers": ["孤独", "孤单", "没人理解", "没有朋友", "一个人在家", "不愿意出门", "不怎么和朋友联系", "lonely", "loneliness"],
        "zh_terms": ["孤独感", "社会隔离", "社会支持", "自我关怀", "连接感"],
        "en_terms": ["loneliness", "social isolation", "social support", "self compassion", "connection", "behavioural activation"],
    },
    {
        "topic": "anxiety",
        "triggers": ["焦虑", "担心", "紧张", "恐慌", "害怕", "不安", "anxiety", "worry", "panic"],
        "zh_terms": ["焦虑", "担忧", "认知重评", "呼吸放松", "接纳不确定"],
        "en_terms": [
            "anxiety",
            "worry",
            "rumination",
            "cognitive restructuring",
            "breathing",
            "relaxation",
            "accepting uncertainty",
        ],
    },
    {
        "topic": "low_mood",
        "triggers": ["低落", "抑郁", "难受", "无助", "没动力", "累", "崩溃", "depressed", "low mood"],
        "zh_terms": ["低落情绪", "行为激活", "自我关怀", "痛苦耐受"],
        "en_terms": ["low mood", "depression", "behavioural activation", "self compassion", "distress tolerance"],
    },
    {
        "topic": "perfectionism",
        "triggers": ["完美", "必须", "应该", "不够好", "自责", "内耗", "perfectionism", "should"],
        "zh_terms": ["完美主义", "应该化", "自我评价", "核心信念"],
        "en_terms": ["perfectionism", "shoulding", "musting", "self esteem", "core beliefs", "balanced thinking"],
    },
    {
        "topic": "emotion_regulation",
        "triggers": ["生气", "愤怒", "控制不住", "情绪失控", "烦躁", "anger", "emotion regulation"],
        "zh_terms": ["情绪调节", "痛苦耐受", "接地练习", "相反行动"],
        "en_terms": ["emotion regulation", "distress tolerance", "grounding", "acceptance", "opposite action"],
    },
    {
        "topic": "perinatal_support",
        "triggers": ["孕", "产后", "哺乳", "带娃", "新手妈妈", "好妈妈", "想哭", "perinatal", "postpartum", "pregnancy"],
        "zh_terms": ["孕产期", "产后情绪", "亲职压力", "寻求支持", "低落情绪"],
        "en_terms": ["perinatal", "postpartum", "pregnancy", "parenthood", "support", "depression", "depressive feelings"],
    },
    {
        "topic": "caregiver_stress",
        "triggers": ["照护", "照顾老人", "照顾家人", "失智", "阿尔茨海默", "caregiver", "dementia"],
        "zh_terms": ["照护压力", "照护者自我照顾", "社会支持"],
        "en_terms": ["caregiver stress", "dementia", "self care", "family support", "social support"],
    },
    {
        "topic": "grief",
        "triggers": ["去世", "丧亲", "哀伤", "告别", "grief", "bereavement"],
        "zh_terms": ["哀伤", "丧亲", "支持系统", "自我关怀"],
        "en_terms": ["grief", "bereavement", "loss", "support", "self compassion"],
    },
    {
        "topic": "work_stress",
        "triggers": ["职场", "上班", "加班", "领导", "同事", "倦怠", "burnout", "work stress", "workplace"],
        "zh_terms": ["职场压力", "工作倦怠", "工作关系", "问题解决"],
        "en_terms": ["work stress", "burnout", "workplace", "return to work", "problem solving"],
    },
    {
        "topic": "family_parenting",
        "triggers": ["父母", "孩子", "亲子", "家庭", "家长", "作业", "吵架", "parent", "child", "family"],
        "zh_terms": ["亲子关系", "家庭沟通", "家长支持", "照护压力", "边界"],
        "en_terms": ["parent child relationship", "family relationship", "communication", "caregiver support", "parent support"],
    },
    {
        "topic": "depression_psychoeducation",
        "triggers": ["抑郁症", "重度抑郁", "depression", "major depressive"],
        "zh_terms": ["抑郁症", "低落情绪", "专业求助", "一般科普"],
        "en_terms": ["depression", "major depressive disorder", "clinical depression", "professional help", "psychoeducation"],
    },
    {
        "topic": "bipolar_psychoeducation",
        "triggers": ["双相", "躁狂", "情绪高涨", "bipolar", "mania"],
        "zh_terms": ["双相情感障碍", "躁狂", "低落情绪", "专业求助", "一般科普"],
        "en_terms": ["bipolar disorder", "mania", "mood episodes", "professional help", "psychoeducation"],
    },
    {
        "topic": "ocd_psychoeducation",
        "triggers": ["强迫症", "反复检查", "门锁", "ocd", "obsessive"],
        "zh_terms": ["强迫症", "反复检查", "专业求助", "一般科普"],
        "en_terms": ["OCD", "obsessive compulsive disorder", "compulsions", "professional help", "psychoeducation"],
    },
    {
        "topic": "ptsd_psychoeducation",
        "triggers": ["创伤", "ptsd", "创伤后", "trauma"],
        "zh_terms": ["创伤后应激", "创伤反应", "专业求助", "一般科普"],
        "en_terms": ["PTSD", "post traumatic stress", "trauma", "professional help", "psychoeducation"],
    },
    {
        "topic": "neurodevelopment_psychoeducation",
        "triggers": ["adhd", "注意力", "自闭症", "孤独症", "autism"],
        "zh_terms": ["ADHD", "注意力缺陷", "自闭症", "孤独症", "专业求助"],
        "en_terms": ["ADHD", "autism", "neurodevelopment", "professional help", "psychoeducation"],
    },
    {
        "topic": "eating_disorders_psychoeducation",
        "triggers": ["进食障碍", "害怕变胖", "控制饮食", "eating disorder"],
        "zh_terms": ["进食障碍", "身体意象", "专业求助", "一般科普"],
        "en_terms": ["eating disorders", "body image", "professional help", "psychoeducation"],
    },
    {
        "topic": "dementia_psychoeducation",
        "triggers": ["失智", "阿尔茨海默", "认知退化", "dementia"],
        "zh_terms": ["失智", "阿尔茨海默", "照护者支持", "一般科普"],
        "en_terms": ["dementia", "caregiver support", "professional help", "psychoeducation"],
    },
    {
        "topic": "substance_use_support",
        "triggers": ["物质使用", "成瘾", "喝酒", "酒精", "substance", "alcohol"],
        "zh_terms": ["物质使用", "酒精问题", "支持边界", "专业求助"],
        "en_terms": ["substance use", "alcohol use", "support boundaries", "professional help"],
    },
]

QUERY_POPULATION_LEXICON: list[dict[str, Any]] = [
    {"population": "older_adults", "triggers": ["退休", "老人", "老年", "older adult", "retired"]},
    {"population": "children", "triggers": ["孩子", "儿童", "小孩", "刚上学", "children", "child"]},
    {"population": "adolescents", "triggers": ["青少年", "青春期", "中学生", "和父母", "被父母", "父母说", "teen", "adolescent"]},
    {"population": "parents", "triggers": ["家长", "我的孩子", "孩子刚", "作为父母", "作为家长", "parent"]},
    {"population": "pregnant_people", "triggers": ["怀孕", "孕期", "孕妇", "pregnant", "pregnancy"]},
    {"population": "postpartum_people", "triggers": ["产后", "新手妈妈", "postpartum"]},
    {"population": "people_experiencing_grief", "triggers": ["亲人去世", "丧亲", "哀伤", "grief", "bereavement"]},
    {"population": "university_students", "triggers": ["大学", "大学生", "高校", "论文", "导师", "毕业", "university", "college"]},
    {"population": "workers", "triggers": ["上班", "职场", "同事", "领导", "加班", "workplace", "worker"]},
]

TOPIC_COMPATIBILITY: dict[str, set[str]] = {
    "academic_stress": {"academic_stress", "procrastination", "perfectionism", "problem_solving", "action_plan", "planning"},
    "career_anxiety": {"career_anxiety", "career_uncertainty", "uncertainty", "problem_solving", "decision_making"},
    "sleep": {"sleep", "insomnia", "sleep_hygiene", "worry", "relaxation"},
    "relationships": {"relationships", "social_relationships", "communication", "assertiveness", "boundaries"},
    "school_support": {"school_support", "student_mental_health", "campus_support", "parent_child_relationship"},
    "loneliness": {"loneliness", "social_isolation", "social_support", "self_compassion", "behavioural_activation"},
    "anxiety": {"anxiety", "worry", "panic", "relaxation", "accepting_uncertainty", "cognitive_restructuring"},
    "low_mood": {"low_mood", "depression", "depressive_feelings", "behavioural_activation", "self_compassion"},
    "perfectionism": {"perfectionism", "self_criticism", "self_esteem", "core_beliefs", "balanced_thinking"},
    "emotion_regulation": {"emotion_regulation", "distress_tolerance", "anger", "grounding", "acceptance"},
    "perinatal_support": {"perinatal_support", "perinatal", "postpartum", "pregnancy", "depression", "depressive_feelings", "self_compassion"},
    "caregiver_stress": {"caregiver_stress", "caregiver_support", "dementia", "social_support", "self_compassion"},
    "grief": {"grief", "bereavement", "loss", "self_compassion", "social_support"},
    "work_stress": {"work_stress", "burnout", "workplace", "problem_solving"},
    "family_parenting": {"family_parenting", "parent_child_relationship", "family_relationships", "communication", "caregiving_stress"},
    "depression_psychoeducation": {"depression", "depressive_feelings", "low_mood"},
    "bipolar_psychoeducation": {"bipolar_disorder", "mania", "depression"},
    "ocd_psychoeducation": {"ocd", "anxiety"},
    "ptsd_psychoeducation": {"ptsd", "trauma", "grounding"},
    "neurodevelopment_psychoeducation": {"adhd", "autism", "neurodevelopment"},
    "eating_disorders_psychoeducation": {"eating_disorders", "body_image"},
    "dementia_psychoeducation": {"dementia", "caregiver_support"},
    "substance_use_support": {"substance_use", "substance_crisis", "support_boundaries"},
}


PSYCHOLOGICAL_CONTEXT_TERMS = {
    "anxiety": ["anxiety", "worry", "uncertainty", "relaxation"],
    "sadness": ["low mood", "self compassion", "behavioural activation"],
    "anger": ["anger", "emotion regulation", "distress tolerance"],
    "fatigue": ["sleep", "rest", "bedtime routine"],
    "academic_pressure": ["academic stress", "study anxiety", "task breakdown"],
    "career_anxiety": ["career anxiety", "job search stress", "problem solving"],
    "relationship_conflict": ["relationships", "communication", "boundaries"],
    "problem_solving": ["problem solving", "action plan", "small steps"],
    "grounding": ["grounding", "present moment", "breathing"],
    "self_compassion": ["self compassion", "balanced thinking"],
}


def _contains_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        normalized = " ".join(str(item).strip().split())
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(normalized)
    return output


def _context_expansions(psychological_context: dict[str, Any] | None) -> list[str]:
    if not psychological_context:
        return []
    terms: list[str] = []
    for key in ("emotion", "cause", "strategy", "risk_level"):
        value = str(psychological_context.get(key) or "").strip().lower()
        if value in {"", "neutral", "general", "low", "unknown"}:
            continue
        terms.extend(PSYCHOLOGICAL_CONTEXT_TERMS.get(value, []))
    return terms


def rewrite_query_multilingual(
    query: str,
    psychological_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cleaned = " ".join(query.strip().split())
    lower = cleaned.lower()
    zh_terms: list[str] = []
    en_terms: list[str] = []
    topics: list[str] = []

    for entry in QUERY_LEXICON:
        if any(str(trigger).lower() in lower for trigger in entry["triggers"]):
            topics.append(str(entry["topic"]))
            zh_terms.extend(str(item) for item in entry.get("zh_terms", []))
            en_terms.extend(str(item) for item in entry.get("en_terms", []))

    populations: list[str] = []
    for entry in QUERY_POPULATION_LEXICON:
        if any(str(trigger).lower() in lower for trigger in entry["triggers"]):
            populations.append(str(entry["population"]))

    en_terms.extend(_context_expansions(psychological_context))
    zh_terms = _dedupe(zh_terms)
    en_terms = _dedupe(en_terms)
    topics = _dedupe(topics)
    populations = _dedupe(populations)

    query_variants = _dedupe(
        [
            cleaned,
            " ".join(zh_terms),
            " ".join(en_terms),
            " ".join([cleaned, *zh_terms, *en_terms]),
        ]
    )
    expanded_query = query_variants[-1] if query_variants else cleaned

    return {
        "original_query": query,
        "cleaned_query": cleaned,
        "expanded_query": expanded_query,
        "query_variants": query_variants,
        "matched_topics": topics,
        "implied_populations": populations,
        "zh_terms": zh_terms,
        "en_terms": en_terms,
        "translation_strategy": "lexicon_bilingual_expansion" if en_terms else "original_query_only",
        "contains_chinese": _contains_chinese(cleaned),
    }


def _parse_json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    return [item.strip() for item in re.split(r"[,;，；]\s*", text) if item.strip()]


def _normalized_metadata_value(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[\s\-/]+", "_", text)
    return re.sub(r"[^a-z0-9_\u4e00-\u9fff]+", "", text)


def _population_tags_compatible(desired_values: set[str], candidate_values: set[str]) -> bool:
    if not desired_values:
        return True
    if not candidate_values:
        return False
    desired = {_normalized_metadata_value(item) for item in desired_values if str(item).strip()}
    candidate = {_normalized_metadata_value(item) for item in candidate_values if str(item).strip()}
    if desired & candidate:
        return True

    adult_subgroups = {
        "adults",
        "young_adults",
        "university_students",
        "workers",
        "caregivers",
        "family_members_supporting_others",
        "people_experiencing_grief",
        "people_exposed_to_trauma",
    }
    if desired <= adult_subgroups and candidate & {"adults", "young_adults", "university_students"}:
        return True
    if "parents" in desired and candidate & {"parents", "caregivers", "adults"}:
        return True
    if "caregivers" in desired and candidate & {"caregivers", "family_members_supporting_others", "adults"}:
        return True
    return False


def _topic_tags_for_item(item: dict[str, Any]) -> set[str]:
    values = _parse_json_list(item.get("topics")) + _parse_json_list(item.get("topic_tags"))
    if item.get("topic"):
        values.append(str(item.get("topic")))
    return {_normalized_metadata_value(value) for value in values if str(value).strip()}


def _compatible_topics_for_rewrite(rewrite: dict[str, Any]) -> set[str]:
    topics: set[str] = set()
    for topic in rewrite.get("matched_topics", []):
        normalized = _normalized_metadata_value(topic)
        if not normalized:
            continue
        topics.add(normalized)
        topics.update(TOPIC_COMPATIBILITY.get(normalized, set()))
    return topics


def _topic_match_strength(item: dict[str, Any], rewrite: dict[str, Any]) -> float:
    desired_topics = _compatible_topics_for_rewrite(rewrite)
    if not desired_topics:
        return 0.0
    candidate_topics = _topic_tags_for_item(item)
    if not candidate_topics:
        return -0.25
    primary_topics = list(rewrite.get("matched_topics", []))
    if primary_topics:
        primary = _normalized_metadata_value(primary_topics[0])
        primary_targets = {primary, *TOPIC_COMPATIBILITY.get(primary, set())}
        if candidate_topics & primary_targets:
            return 1.25
    if candidate_topics & desired_topics:
        return 1.0
    if any(
        candidate in desired or desired in candidate
        for candidate in candidate_topics
        for desired in desired_topics
        if len(candidate) >= 5 and len(desired) >= 5
    ):
        return 0.55
    return -0.25


def _specific_population_mismatch(desired_values: set[str], candidate_values: set[str]) -> bool:
    if not desired_values or not candidate_values:
        return False
    if _population_tags_compatible(desired_values, candidate_values):
        return False
    broad_adult = {"adults", "young_adults", "university_students"}
    normalized_desired = {_normalized_metadata_value(value) for value in desired_values if str(value).strip()}
    normalized_candidate = {_normalized_metadata_value(value) for value in candidate_values if str(value).strip()}
    specific_groups = {
        "children",
        "adolescents",
        "older_adults",
        "pregnant_people",
        "postpartum_people",
        "parents",
        "caregivers",
        "workers",
        "university_students",
        "people_experiencing_grief",
    }
    if normalized_desired & specific_groups and not (normalized_candidate & broad_adult):
        return True
    return False


def _desired_populations_for_context(
    rewrite: dict[str, Any],
    metadata_filter: dict[str, Any] | None = None,
) -> set[str]:
    desired = set(_parse_json_list((metadata_filter or {}).get("population_tags") or (metadata_filter or {}).get("population")))
    desired.update(str(item) for item in rewrite.get("implied_populations", []) if str(item).strip())
    return desired


def _filter_specific_population_matches(items: list[dict[str, Any]], desired_populations: set[str]) -> list[dict[str, Any]]:
    if not desired_populations:
        return items
    compatible = [
        item
        for item in items
        if _population_tags_compatible(desired_populations, set(_parse_json_list(item.get("population_tags"))))
    ]
    if not compatible:
        return items
    return [
        item
        for item in items
        if not _specific_population_mismatch(desired_populations, set(_parse_json_list(item.get("population_tags"))))
    ]


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _requests_safety_route(collections: list[str] | None, metadata_filter: dict[str, Any] | None) -> bool:
    collection_values = set(collections or [])
    filter_values: set[str] = set()
    for key in ("target_collection", "collection", "collections", "use_mode", "risk_scope"):
        filter_values.update(_parse_json_list((metadata_filter or {}).get(key)))
    return bool(
        "safety" in collection_values
        or "safety" in filter_values
        or "safety_only" in filter_values
        or "safety_route_only" in filter_values
    )


def _requests_psychoeducation_route(collections: list[str] | None, metadata_filter: dict[str, Any] | None) -> bool:
    collection_values = set(collections or [])
    filter_values: set[str] = set()
    for key in ("target_collection", "collection", "collections", "use_mode"):
        filter_values.update(_parse_json_list((metadata_filter or {}).get(key)))
    return "psychoeducation_only" in filter_values and (
        "professional_knowledge" in collection_values or "professional_knowledge" in filter_values
    )


def _ordinary_rag_boundary_reason(
    query: str,
    *,
    collections: list[str] | None = None,
    metadata_filter: dict[str, Any] | None = None,
) -> str:
    if _requests_safety_route(collections, metadata_filter):
        return ""
    normalized = str(query or "").strip().lower()
    if not normalized:
        return ""
    if any(term in normalized for term in SAFETY_TERMS):
        return "safety_route_required"
    if any(term in normalized for term in MEDICATION_TERMS):
        return "medication_or_dosage_out_of_scope"
    if any(term in normalized for term in DIAGNOSIS_TERMS):
        if _requests_psychoeducation_route(collections, metadata_filter):
            return ""
        return "diagnosis_out_of_scope"
    if any(term in normalized for term in DANGEROUS_INSTRUCTION_TERMS) and re.search(
        r"(伤害|危险|违法|中毒|过量|昏迷|weapon|poison|overdose|harm)",
        normalized,
    ):
        return "dangerous_instruction_out_of_scope"
    return ""


def _normalize_candidate(item: dict[str, Any], *, source: str, rank: int | None = None) -> dict[str, Any]:
    normalized = dict(item)
    score = float(normalized.pop("score", 0) or 0)
    if source == "dense":
        normalized["vector_score"] = max(float(normalized.get("vector_score") or 0), score)
        if rank is not None:
            normalized["dense_rank"] = rank
    else:
        normalized["keyword_score"] = max(float(normalized.get("keyword_score") or 0), score)
        if rank is not None:
            normalized["bm25_rank"] = rank
    normalized["retrieval_sources"] = sorted({source, *normalized.get("retrieval_sources", [])})
    normalized["topics"] = _parse_json_list(normalized.get("topics"))
    normalized["topic_tags"] = _parse_json_list(normalized.get("topic_tags") or normalized.get("topics"))
    normalized["population_tags"] = _parse_json_list(normalized.get("population_tags"))
    normalized["life_stage_tags"] = _parse_json_list(normalized.get("life_stage_tags"))
    normalized["user_facing"] = _as_bool(normalized.get("user_facing"), default=True)
    normalized["clinical_only"] = _as_bool(normalized.get("clinical_only"), default=False)
    normalized["exclude_from_index"] = _as_bool(normalized.get("exclude_from_index"), default=False)
    normalized["use_mode"] = str(normalized.get("use_mode") or "direct_user_support")
    normalized["risk_scope"] = str(normalized.get("risk_scope") or "normal")
    normalized["year"] = int(normalized["year"]) if str(normalized.get("year", "")).isdigit() else normalized.get("year")
    normalized["content"] = str(normalized.get("content", "")).strip()
    normalized["target_collection"] = str(normalized.get("target_collection") or "")
    return normalized


def _merge_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in candidates:
        chunk_id = str(item.get("chunk_id") or "")
        if not chunk_id:
            continue
        existing = merged.get(chunk_id)
        if not existing:
            merged[chunk_id] = dict(item)
            continue
        existing["vector_score"] = max(float(existing.get("vector_score") or 0), float(item.get("vector_score") or 0))
        existing["keyword_score"] = max(float(existing.get("keyword_score") or 0), float(item.get("keyword_score") or 0))
        for rank_key in ("dense_rank", "bm25_rank"):
            if item.get(rank_key) is None:
                continue
            if existing.get(rank_key) is None:
                existing[rank_key] = item[rank_key]
            else:
                existing[rank_key] = min(int(existing[rank_key]), int(item[rank_key]))
        existing["retrieval_sources"] = sorted(
            {*(existing.get("retrieval_sources") or []), *(item.get("retrieval_sources") or [])}
        )
    return list(merged.values())


def _apply_rrf_scores(candidates: list[dict[str, Any]], rrf_k: int = 60) -> list[dict[str, Any]]:
    if not candidates:
        return []
    raw_scores: list[float] = []
    for item in candidates:
        score = 0.0
        if item.get("dense_rank") is not None:
            score += 1.0 / (rrf_k + int(item["dense_rank"]))
        if item.get("bm25_rank") is not None:
            score += 1.0 / (rrf_k + int(item["bm25_rank"]))
        item["rrf_score"] = round(score, 8)
        raw_scores.append(score)
    max_score = max(raw_scores or [1.0])
    for item in candidates:
        item["rrf_score_norm"] = round(float(item.get("rrf_score") or 0) / max(max_score, 1e-9), 4)
    return candidates


def _is_user_facing(
    item: dict[str, Any],
    allowed_collections: list[str] | None = None,
    metadata_filter: dict[str, Any] | None = None,
) -> bool:
    collection = str(item.get("target_collection") or "")
    allowed = set(allowed_collections or USER_FACING_COLLECTIONS)
    use_mode = str(item.get("use_mode") or "direct_user_support")
    risk_scope = str(item.get("risk_scope") or "normal")
    if _as_bool(item.get("exclude_from_index"), default=False):
        return False
    if collection == "safety" or use_mode == "safety_only" or risk_scope == "safety_route_only":
        filter_scope = set(_parse_json_list((metadata_filter or {}).get("risk_scope")))
        return collection in allowed and use_mode == "safety_only" and "safety_route_only" in filter_scope
    requested_use_modes = set(_parse_json_list((metadata_filter or {}).get("use_mode")))
    if use_mode == "psychoeducation_only" and "psychoeducation_only" in requested_use_modes:
        return (
            collection in allowed
            and collection in USER_FACING_COLLECTIONS
            and risk_scope in ORDINARY_RISK_SCOPES
            and not _as_bool(item.get("clinical_only"), default=False)
            and not _as_bool(item.get("exclude_from_index"), default=False)
        )
    return (
        collection in allowed
        and collection in USER_FACING_COLLECTIONS
        and use_mode in USER_FACING_USE_MODES
        and risk_scope in ORDINARY_RISK_SCOPES
        and not _as_bool(item.get("clinical_only"), default=False)
        and _as_bool(item.get("user_facing"), default=True)
    )


def _review_allowed(item: dict[str, Any], staging_mode: bool, index_mode: str = "staging") -> bool:
    status = str(item.get("review_status") or "").strip().lower()
    if normalize_index_mode(index_mode) == "production":
        return status in {"approved", "reviewed"}
    if status in {"approved", "reviewed"}:
        return True
    if staging_mode and status not in {"rejected", "blocked"}:
        return True
    return False


def _matches_metadata_filter(item: dict[str, Any], metadata_filter: dict[str, Any] | None = None) -> bool:
    if not metadata_filter:
        return True

    for key, desired in metadata_filter.items():
        if desired in (None, "", []):
            continue
        desired_values = set(_parse_json_list(desired))
        if not desired_values and isinstance(desired, str):
            desired_values = {desired}
        if key in {"target_collection", "collection", "collections"}:
            candidate = str(item.get("target_collection") or "")
            if candidate not in desired_values:
                return False
            continue
        if key in {"topic", "topics"}:
            candidate_values = set(_parse_json_list(item.get("topics")) + _parse_json_list(item.get("topic_tags")))
            if item.get("topic"):
                candidate_values.add(str(item.get("topic")))
            if desired_values and not (candidate_values & desired_values):
                return False
            continue
        if key in {"population", "populations", "population_tags"}:
            candidate_values = set(_parse_json_list(item.get("population_tags")))
            if desired_values and not _population_tags_compatible(desired_values, candidate_values):
                return False
            continue
        if key in {"life_stage", "life_stages", "life_stage_tags"}:
            candidate_values = set(_parse_json_list(item.get("life_stage_tags")))
            if desired_values and not (candidate_values & desired_values):
                return False
            continue
        if key in {"use_mode", "risk_scope"}:
            if str(item.get(key) or "") not in desired_values:
                return False
            continue
        if key == "review_status":
            if str(item.get("review_status") or "") not in desired_values:
                return False
            continue
        candidate_values = set(_parse_json_list(item.get(key)))
        if desired_values and not (candidate_values & desired_values):
            return False
    return True


def _has_direct_term_support(item: dict[str, Any], rewrite: dict[str, Any]) -> bool:
    content = " ".join(
        [
            str(item.get("title", "")),
            str(item.get("section", "")),
            str(item.get("topic", "")),
            " ".join(_parse_json_list(item.get("topics"))),
            " ".join(_parse_json_list(item.get("topic_tags"))),
            " ".join(_parse_json_list(item.get("population_tags"))),
            str(item.get("content", "")),
        ]
    ).lower()
    terms = [*rewrite.get("en_terms", []), *rewrite.get("zh_terms", [])]
    if not terms:
        return True
    normalized_terms = []
    for term in terms:
        normalized_terms.extend(part for part in re.split(r"[\s,/;，；]+", str(term).lower()) if len(part) >= 3)
    return any(term in content for term in normalized_terms)


def _source_document(item: dict[str, Any], index: int) -> dict[str, Any]:
    evidence_level = str(item.get("evidence_level") or "source_unverified")
    organization = str(item.get("organization") or "")
    return {
        "source_id": item.get("source_id"),
        "chunk_id": item.get("chunk_id"),
        "citation_label": f"来源{index}",
        "title": item.get("title"),
        "organization": organization,
        "year": item.get("year"),
        "section": item.get("section"),
        "topic": item.get("topic"),
        "topics": item.get("topics") or [],
        "content": item.get("content"),
        "content_preview": str(item.get("content", ""))[:240],
        "relevance_score": item.get("rerank_score", item.get("semantic_score", 0)),
        "semantic_score": item.get("semantic_score", 0),
        "psychological_score": item.get("psychological_score", 0),
        "evidence_level": evidence_level,
        "is_verified": evidence_level != "source_unverified" and bool(organization),
        "review_status": item.get("review_status", ""),
        "reviewed": str(item.get("review_status") or "").lower() in {"approved", "reviewed"},
        "official_page_url": item.get("official_page_url") or "",
        "downloaded_url": item.get("downloaded_url") or "",
        "retrieval_sources": item.get("retrieval_sources") or [],
        "target_collection": item.get("target_collection"),
        "collection": item.get("collection") or item.get("target_collection"),
        "use_mode": item.get("use_mode", ""),
        "risk_scope": item.get("risk_scope", ""),
        "clinical_only": _as_bool(item.get("clinical_only"), default=False),
        "user_facing": _as_bool(item.get("user_facing"), default=True),
        "population_tags": item.get("population_tags") or [],
        "life_stage_tags": item.get("life_stage_tags") or [],
        "translation_group_id": item.get("translation_group_id", ""),
        "license": item.get("license", ""),
        "language": item.get("language", ""),
        "official_citation_ready": bool(item.get("official_page_url") and item.get("organization")),
    }


def _apply_v2_context_boosts(
    items: list[dict[str, Any]],
    *,
    rewrite: dict[str, Any],
    metadata_filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not items:
        return []
    desired_populations = _desired_populations_for_context(rewrite, metadata_filter)
    for item in items:
        score = float(item.get("rerank_score") or 0)
        boost = 0.0
        if rewrite.get("contains_chinese") and str(item.get("language") or "").lower().startswith("zh"):
            boost += 0.03
        candidate_populations = set(_parse_json_list(item.get("population_tags")))
        if desired_populations and _population_tags_compatible(desired_populations, candidate_populations):
            boost += 0.03
        elif _specific_population_mismatch(desired_populations, candidate_populations):
            boost -= 0.04
        topic_strength = _topic_match_strength(item, rewrite)
        if topic_strength >= 1.2:
            boost += 0.09
        elif topic_strength >= 1.0:
            boost += 0.06
        elif topic_strength > 0:
            boost += 0.03
        elif topic_strength < 0:
            boost -= 0.025
        if boost:
            item["v2_context_boost"] = round(boost, 4)
            item["rerank_score"] = round(min(max(score + boost, 0.0), 1.0), 4)
    return sorted(items, key=lambda row: float(row.get("rerank_score") or 0), reverse=True)


def _dedupe_ranked_content(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        content = str(item.get("content") or "").strip()
        key = str(item.get("content_sha256") or item.get("chunk_sha256") or "").strip()
        if not key and content:
            key = re.sub(r"\s+", " ", content.lower())[:500]
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        deduped.append(item)
    return deduped


def _index_status() -> tuple[Any | None, dict[str, Any]]:
    settings = get_settings()
    index_mode = settings.effective_rag_index_mode
    try:
        registry = load_knowledge_source_registry()
    except Exception as exc:
        return None, {"ready": False, "error": str(exc)}

    bm25_dir = bm25_dir_for(registry.paths["indexes_bm25"], index_mode, require_existing=True)
    chroma_dir = registry.paths["indexes_chroma"]
    bm25_ready = (bm25_dir / "bm25_index.pkl").exists() and (bm25_dir / "documents.jsonl").exists()
    chroma_ready = (chroma_dir / "chroma.sqlite3").exists()
    return registry, {
        "ready": bm25_ready or chroma_ready,
        "index_mode": index_mode,
        "bm25_ready": bm25_ready,
        "chroma_ready": chroma_ready,
        "bm25_dir": bm25_dir.as_posix(),
        "chroma_dir": chroma_dir.as_posix(),
    }


@lru_cache(maxsize=1)
def _cached_rag_v1_embedding_provider():
    return get_rag_v1_embedding_provider()


async def _dense_candidates(
    registry: Any,
    rewrite: dict[str, Any],
    top_k: int,
    collections: list[str] | None = None,
    index_mode: str = "staging",
) -> tuple[list[dict[str, Any]], str]:
    status = "skipped"
    candidates: list[dict[str, Any]] = []
    try:
        provider = _cached_rag_v1_embedding_provider()
        dense_queries = _dedupe(
            [
                rewrite.get("cleaned_query", ""),
                " ".join(rewrite.get("en_terms", [])),
                rewrite.get("expanded_query", ""),
            ]
        )[:3]
        collection_targets = collections or [None]
        for query in dense_queries:
            embedding = await provider.embed_query(query)
            for collection in collection_targets:
                for rank, item in enumerate(
                    query_chroma(
                        registry.paths["indexes_chroma"],
                        embedding,
                        top_k=top_k,
                        collection=collection,
                        index_mode=index_mode,
                    ),
                    start=1,
                ):
                    candidates.append(_normalize_candidate(item, source="dense", rank=rank))
        status = "ok"
    except Exception as exc:
        status = f"error:{type(exc).__name__}"
    return candidates, status


def _bm25_candidates(registry: Any, rewrite: dict[str, Any], top_k: int, index_mode: str = "staging") -> tuple[list[dict[str, Any]], str]:
    try:
        results = query_bm25(bm25_dir_for(registry.paths["indexes_bm25"], index_mode, require_existing=True), rewrite["expanded_query"], top_k=top_k)
        return [_normalize_candidate(item, source="bm25", rank=rank) for rank, item in enumerate(results, start=1)], "ok"
    except Exception as exc:
        return [], f"error:{type(exc).__name__}"


async def retrieve_rag_v1(
    query: str,
    *,
    top_k: int = 3,
    session_id: str = "",
    psychological_context: dict[str, Any] | None = None,
    collections: list[str] | None = None,
    metadata_filter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    index_mode = settings.effective_rag_index_mode
    started = time.perf_counter()
    if not settings.rag_enabled or not settings.rag_v1_enabled:
        return {
            "query": query,
            "rewritten_query": query,
            "retrieved_chunks": [],
            "documents": [],
            "retrieval_status": "disabled",
            "retrieval_mode": "rag_v1_hybrid_bilingual",
            "collections": collections or [],
        }

    registry, status = _index_status()
    rewrite = rewrite_query_multilingual(query, psychological_context)
    if not registry or not status.get("ready"):
        return {
            "query": query,
            "rewritten_query": rewrite["expanded_query"],
            "retrieved_chunks": [],
            "documents": [],
            "retrieval_status": "index_not_ready",
            "retrieval_mode": "rag_v1_hybrid_bilingual",
            "query_rewrite": rewrite,
            "index_status": status,
            "collections": collections or [],
        }

    boundary_reason = _ordinary_rag_boundary_reason(query, collections=collections, metadata_filter=metadata_filter)
    if boundary_reason:
        duration_ms = int((time.perf_counter() - started) * 1000)
        result = {
            "query": query,
            "rewritten_query": rewrite["expanded_query"],
            "retrieved_chunks": [],
            "documents": [],
            "retrieval_status": "insufficient_evidence",
            "retrieval_mode": "rag_v1_hybrid_bilingual",
            "collections": collections or [],
            "metadata_filter": metadata_filter or {},
            "index_mode": index_mode,
            "staging_mode": settings.rag_staging_mode,
            "query_rewrite": rewrite,
            "index_status": {**status, "bm25_status": "skipped_boundary", "dense_status": "skipped_boundary"},
            "psychological_context": psychological_context or {},
            "duration_ms": duration_ms,
            "boundary_reason": boundary_reason,
        }
        try:
            init_db()
            with SessionLocal() as db:
                log_retrieval(db, session_id, query, "insufficient_evidence", result, duration_ms)
        except Exception:
            pass
        return result

    candidates: list[dict[str, Any]] = []
    bm25_status = "skipped"
    dense_status = "skipped"
    if status.get("bm25_ready") and settings.rag_v1_bm25_enabled:
        bm25_items, bm25_status = _bm25_candidates(registry, rewrite, settings.rag_v1_bm25_top_k, index_mode=index_mode)
        candidates.extend(bm25_items)
    if status.get("chroma_ready") and settings.rag_v1_dense_enabled:
        dense_items, dense_status = await _dense_candidates(
            registry,
            rewrite,
            settings.rag_v1_dense_top_k,
            collections=collections,
            index_mode=index_mode,
        )
        candidates.extend(dense_items)

    candidates = [
        item
        for item in _merge_candidates(candidates)
        if item.get("content")
        and _is_user_facing(item, collections, metadata_filter)
        and _review_allowed(item, settings.rag_staging_mode, index_mode=index_mode)
        and _matches_metadata_filter(item, metadata_filter)
        and _has_direct_term_support(item, rewrite)
    ]
    fusion_mode = str(settings.rag_hybrid_fusion or "legacy").strip().lower()
    if fusion_mode == "rrf":
        candidates = _apply_rrf_scores(candidates, settings.rag_rrf_k)
    emotion_aware = bool(psychological_context)
    reranked = rerank(
        rewrite["expanded_query"],
        candidates,
        psychological_context=psychological_context,
        emotion_aware=emotion_aware,
    )
    reranked = _apply_v2_context_boosts(reranked, rewrite=rewrite, metadata_filter=metadata_filter)
    if fusion_mode == "rrf" and reranked:
        max_rerank = max(float(item.get("rerank_score") or 0) for item in reranked) or 1.0
        for item in reranked:
            rrf_score = float(item.get("rrf_score_norm") or 0)
            psychological_score = float(item.get("rerank_score") or 0) / max(max_rerank, 1e-9)
            item["fusion_score"] = round((0.7 * rrf_score) + (0.3 * psychological_score), 4)
            item["rerank_score"] = item["fusion_score"]
        reranked = sorted(reranked, key=lambda item: float(item.get("rerank_score") or 0), reverse=True)
        reranked = _apply_v2_context_boosts(reranked, rewrite=rewrite, metadata_filter=metadata_filter)
    reranked = _dedupe_ranked_content(reranked)
    reranked = _filter_specific_population_matches(
        reranked,
        _desired_populations_for_context(rewrite, metadata_filter),
    )
    selected = [
        item
        for item in reranked
        if float(item.get("rerank_score") or 0) >= settings.rag_v1_min_relevance_score
        and (float(item.get("keyword_score") or 0) > 0 or float(item.get("vector_score") or 0) >= settings.rag_v1_min_vector_score)
    ][: max(top_k, 1)]
    documents = [_source_document(item, index + 1) for index, item in enumerate(selected)]
    status_code = "success" if selected else "insufficient_evidence"
    duration_ms = int((time.perf_counter() - started) * 1000)
    result = {
        "query": query,
        "rewritten_query": rewrite["expanded_query"],
        "retrieved_chunks": selected,
        "documents": documents,
        "retrieval_status": status_code,
        "retrieval_mode": "rag_v1_hybrid_bilingual",
        "collections": collections or [],
        "metadata_filter": metadata_filter or {},
        "index_mode": index_mode,
        "staging_mode": settings.rag_staging_mode,
        "fusion_mode": fusion_mode,
        "query_rewrite": rewrite,
        "index_status": {
            **status,
            "bm25_status": bm25_status,
            "dense_status": dense_status,
        },
        "psychological_context": psychological_context or {},
        "duration_ms": duration_ms,
    }
    try:
        init_db()
        with SessionLocal() as db:
            log_retrieval(db, session_id, query, status_code, result, duration_ms)
    except Exception:
        pass
    return result
