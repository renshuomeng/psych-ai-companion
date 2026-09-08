from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import json
import math
import re
import sys
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import orjson  # type: ignore
except Exception:  # pragma: no cover - optional speed path
    orjson = None


DATASET_DEFAULTS = {
    "cpsdd": {
        "path": r"C:\Users\renshuomeng\Downloads\train.json",
        "target": 1000,
        "candidate": 2000,
        "out_dir": "cpsdd",
        "selected_stem": "cpsdd_selected_1000",
    },
    "psydial_d4": {
        "path": r"C:\Users\renshuomeng\Downloads\PsyDial-D4.json",
        "target": 400,
        "candidate": 800,
        "out_dir": "psydial_d4",
        "selected_stem": "psydial_d4_selected_400",
    },
    "soulchat": {
        "path": r"C:\Users\renshuomeng\Downloads\SoulChatCorpus-sft-multi-Turn.json",
        "target": 600,
        "candidate": 1200,
        "out_dir": "soulchat",
        "selected_stem": "soulchat_selected_600",
    },
}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SYSTEM_PROMPT_PATH = PROJECT_ROOT / "backend" / "prompts" / "system_prompt.txt"

ROLE_USER = {"user", "human", "client", "patient", "seeker", "用户", "求助者", "来访者", "学生"}
ROLE_ASSISTANT = {
    "assistant",
    "bot",
    "gpt",
    "chatgpt",
    "counselor",
    "therapist",
    "psychologist",
    "咨询师",
    "治疗师",
    "助手",
    "老师",
    "小天",
}
ROLE_SOURCE_SYSTEM = {"system", "prompt", "规则", "设定"}

GENERIC_SHORT_RE = re.compile(
    r"^(好的|嗯+|呃+|啊+|是的|可以|没事|没关系|加油|我理解|理解你|不客气|谢谢|明白|继续说|请继续)[。！!,.，\s]*$"
)
HIGH_RISK_RE = re.compile(
    r"(自杀|轻生|想死|不想活|结束生命|伤害自己|自残|割腕|跳楼|吞药|寻死|活不下去|杀了自己|伤害他人|杀人)"
)
SAFETY_RESPONSE_RE = re.compile(
    r"(紧急|立即|马上|急救|120|110|报警|危机|热线|安全计划|不要独自|陪在你身边|联系.{0,8}(家人|朋友|老师|辅导员|医生|心理中心|可信任的人)|专业帮助|现实中的帮助|远离.{0,8}(刀|药|窗|危险))"
)
MEDICATION_DIRECTIVE_RE = re.compile(
    r"((建议|应该|可以|需要|必须).{0,10}(服用|吃|使用|加用).{0,18}(药|抗抑郁|安眠|镇静|抗焦虑|处方))|((增加|减少|调整|停止|停用|停药|换药|加大|减小).{0,8}(剂量|药量|用药|药))"
)
MEDICATION_SAFE_CONTEXT_RE = re.compile(r"(不要自行|不能自行|请咨询|咨询医生|遵医嘱|由医生|专业医生|精神科医生)")
DIAGNOSIS_RE = re.compile(
    r"(你(已经)?(患有|得了|就是|属于).{0,12}(抑郁症|焦虑症|强迫症|双相|精神分裂|创伤后应激|PTSD|进食障碍|人格障碍))|(这说明你有.{0,12}(疾病|障碍|症))"
)
GUARANTEE_RE = re.compile(r"(一定会(好|康复|恢复)|肯定能(治好|恢复|康复)|保证.{0,8}(治好|恢复|康复)|必然.{0,8}(康复|好起来))")
PRO_ONLY_RE = re.compile(r"((我来|现在|马上).{0,12}(催眠|暴露治疗|系统脱敏|EMDR|眼动脱敏|创伤治疗))")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
ID_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
QQ_WECHAT_RE = re.compile(r"((微信|wechat|vx|qq|QQ)[:：号\s]*)([A-Za-z0-9_\-]{5,})")
WHITESPACE_RE = re.compile(r"\s+")
PUNCT_RE = re.compile(r"[\s\W_]+", re.UNICODE)
TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9]+")

PROBLEM_KEYWORDS = [
    ("学习与论文压力", r"(学习|作业|考试|论文|绩点|挂科|课堂|导师|科研|考研|复习)"),
    ("就业与未来焦虑", r"(就业|工作|实习|面试|简历|职业|毕业|未来|offer|招聘)"),
    ("人际关系", r"(朋友|同学|室友|关系|社交|孤立|吵架|矛盾|人际|相处)"),
    ("亲密关系", r"(恋爱|分手|对象|男友|女友|喜欢的人|暧昧|伴侣|感情)"),
    ("家庭压力", r"(父母|家庭|妈妈|爸爸|家里|亲人|原生家庭|家长)"),
    ("睡眠困扰", r"(睡不着|失眠|熬夜|早醒|睡眠|做梦|入睡)"),
    ("孤独与低落", r"(孤独|寂寞|空虚|低落|难过|痛苦|崩溃|无助|绝望)"),
    ("自我与控制感", r"(自卑|自责|内耗|迷茫|意义|价值|控制|失控|拖延)"),
    ("情绪调节", r"(焦虑|紧张|压力|生气|愤怒|烦躁|恐惧|害怕|抑郁)"),
]

FOCUS_KEYWORDS = [
    ("安全支持", r"(自杀|轻生|自残|伤害|不想活|想死|危机)"),
    ("认知重评", r"(想法|认知|看法|评价|灾难化|应该|必须|自责|否定)"),
    ("情绪命名", r"(情绪|感受|难过|焦虑|愤怒|害怕|低落|委屈)"),
    ("行动计划", r"(计划|步骤|尝试|安排|行动|目标|任务|练习)"),
    ("社会支持", r"(朋友|家人|老师|辅导员|同学|心理中心|倾诉|求助)"),
    ("自我接纳", r"(接纳|允许|善待|价值|自我|自卑|自信|内疚)"),
]

STRATEGY_KEYWORDS = [
    ("safety_planning", r"(安全|紧急|热线|120|110|报警|危机|不要独自|远离危险)"),
    ("empathy_validation", r"(能理解|听起来|这很不容易|辛苦|委屈|难受|我在|被看见)"),
    ("open_question", r"(愿意说说|可以讲讲|发生了什么|你觉得|是什么让|能不能告诉我|想先谈)"),
    ("emotion_labeling", r"(你可能感到|这像是|情绪|感受|焦虑|低落|愤怒|害怕)"),
    ("cognitive_reframe", r"(换个角度|想法|证据|是否一定|也许|重新看待|认知)"),
    ("problem_solving", r"(第一步|可以先|计划|列出来|拆分|安排|具体做法|下一步)"),
    ("grounding_relaxation", r"(呼吸|放松|正念|落地|身体扫描|渐进式|五感)"),
    ("psychoeducation", r"(心理学|常见反应|压力反应|情绪调节|机制|研究|说明)"),
    ("resource_referral", r"(辅导员|心理中心|咨询师|医生|专业帮助|学校资源|可信任的人)"),
]


@dataclass
class FilteredRecord:
    source: str
    source_id: str
    original_index: int
    original_hash: str
    group: str
    problem: str
    cause: str
    support_focus: str
    strategy_path: list[str]
    severity: str
    messages: list[dict[str, str]]
    metrics: dict[str, Any]
    quality_score: float
    coverage_score: float
    final_score: float
    exact_hash: str
    normalized_hash: str


def json_dumps(obj: Any, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def json_load_bytes(data: bytes) -> Any:
    if orjson is not None:
        return orjson.loads(data)
    return json.loads(data.decode("utf-8-sig"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def original_hash(obj: Any) -> str:
    try:
        return sha256_text(json_dumps(obj))
    except TypeError:
        return sha256_text(str(obj))


def redact_pii(text: str) -> str:
    text = URL_RE.sub("[URL]", text)
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = PHONE_RE.sub("[PHONE]", text)
    text = ID_RE.sub("[ID]", text)
    text = QQ_WECHAT_RE.sub(lambda m: f"{m.group(1)}[ACCOUNT]", text)
    return text


def clean_text(text: Any) -> str:
    if text is None:
        return ""
    value = str(text).replace("\r\n", "\n").replace("\r", "\n").strip()
    value = redact_pii(value)
    return value


def normalized_for_hash(text: str) -> str:
    return PUNCT_RE.sub("", text.lower())


def estimate_tokens(text: str) -> int:
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin_words = len(re.findall(r"[A-Za-z0-9]+", text))
    other = max(0, len(text) - cjk)
    return max(1, int(cjk * 0.75 + latin_words * 1.2 + other * 0.12))


def iter_json_array(path: Path, chunk_size: int = 1024 * 1024) -> Iterable[Any]:
    decoder = json.JSONDecoder()
    with path.open("r", encoding="utf-8-sig") as f:
        buf = ""
        eof = False
        started = False
        while True:
            if not eof and len(buf) < chunk_size:
                part = f.read(chunk_size)
                if part:
                    buf += part
                else:
                    eof = True

            buf = buf.lstrip()
            if not started:
                if not buf and eof:
                    return
                if buf.startswith("["):
                    buf = buf[1:]
                    started = True
                elif buf.startswith("{"):
                    obj, idx = decoder.raw_decode(buf)
                    if buf[idx:].strip():
                        raise ValueError(f"{path} contains trailing content after a JSON object")
                    if isinstance(obj, dict):
                        for value in obj.values():
                            yield value
                    else:
                        yield obj
                    return
                else:
                    if eof:
                        raise ValueError(f"{path} is not a JSON array or object")
                    continue

            buf = buf.lstrip()
            if buf.startswith(","):
                buf = buf[1:]
                continue
            if buf.startswith("]"):
                return
            if not buf and eof:
                return

            try:
                obj, idx = decoder.raw_decode(buf)
            except json.JSONDecodeError:
                if eof:
                    raise
                part = f.read(chunk_size)
                if part:
                    buf += part
                    continue
                eof = True
                continue

            yield obj
            buf = buf[idx:]


def iter_json_records(path: Path, fast_load_limit_mb: int = 650) -> Iterable[Any]:
    """Iterate top-level records; use direct parsing for medium files and streaming for very large files."""
    if path.stat().st_size <= fast_load_limit_mb * 1024 * 1024:
        data = json_load_bytes(path.read_bytes())
        if isinstance(data, list):
            for item in data:
                yield item
            return
        if isinstance(data, dict):
            for item in data.values():
                yield item
            return
        yield data
        return
    yield from iter_json_array(path)


def compact_label(value: Any, default: str = "unknown") -> str:
    if value is None:
        return default
    if isinstance(value, (list, tuple)):
        parts = [str(v).strip() for v in value if str(v).strip()]
        return "、".join(parts) if parts else default
    text = str(value).strip()
    return text if text else default


def map_role(raw_role: Any, dataset: str, from_cpsdd_speaker: bool = False) -> str | None:
    role = str(raw_role or "").strip()
    role_lower = role.lower()
    if from_cpsdd_speaker:
        if role in {"系统", "咨询师", "治疗师", "老师", "助手"}:
            return "assistant"
        if role in {"用户", "求助者", "来访者", "学生"}:
            return "user"

    if role_lower in ROLE_SOURCE_SYSTEM or role in ROLE_SOURCE_SYSTEM:
        return "source_system"
    if role_lower in ROLE_USER or role in ROLE_USER:
        return "user"
    if role_lower in ROLE_ASSISTANT or role in ROLE_ASSISTANT:
        return "assistant"
    return None


def extract_messages(obj: dict[str, Any], dataset: str) -> tuple[list[dict[str, str]], dict[str, int]]:
    stats = {"empty_raw_messages": 0, "unknown_role_messages": 0, "source_system_messages": 0}
    if dataset == "cpsdd":
        raw_messages = obj.get("dialog") or []
        from_cpsdd_speaker = True
    elif "messages" in obj:
        raw_messages = obj.get("messages") or []
        from_cpsdd_speaker = False
    elif "dialog" in obj:
        raw_messages = obj.get("dialog") or []
        from_cpsdd_speaker = False
    elif "conversation" in obj:
        raw_messages = obj.get("conversation") or []
        from_cpsdd_speaker = False
    elif "dialogue" in obj:
        raw_messages = obj.get("dialogue") or []
        from_cpsdd_speaker = False
    elif ("input" in obj or "question" in obj or "instruction" in obj) and ("output" in obj or "answer" in obj or "response" in obj):
        user_text = obj.get("input") or obj.get("question") or obj.get("instruction")
        assistant_text = obj.get("output") or obj.get("answer") or obj.get("response")
        raw_messages = [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": assistant_text},
        ]
        from_cpsdd_speaker = False
    else:
        return [], {"empty_raw_messages": 0, "unknown_role_messages": 1, "source_system_messages": 0}

    messages: list[dict[str, str]] = []
    if not isinstance(raw_messages, list):
        return [], {"empty_raw_messages": 0, "unknown_role_messages": 1, "source_system_messages": 0}

    for item in raw_messages:
        if isinstance(item, str):
            stats["unknown_role_messages"] += 1
            continue
        if not isinstance(item, dict):
            stats["unknown_role_messages"] += 1
            continue
        raw_role = item.get("speaker", item.get("role", item.get("from", item.get("author"))))
        role = map_role(raw_role, dataset, from_cpsdd_speaker)
        content = clean_text(item.get("content", item.get("text", item.get("value", item.get("message")))))
        if not content:
            stats["empty_raw_messages"] += 1
            continue
        if role == "source_system":
            stats["source_system_messages"] += 1
            continue
        if role not in {"user", "assistant"}:
            stats["unknown_role_messages"] += 1
            continue
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] = messages[-1]["content"].rstrip() + "\n" + content
        else:
            messages.append({"role": role, "content": content})

    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    while messages and messages[-1]["role"] != "assistant":
        messages.pop()

    return messages, stats


def all_text(messages: list[dict[str, str]], role: str | None = None) -> str:
    return "\n".join(m["content"] for m in messages if role is None or m["role"] == role)


def infer_problem_topic(text: str, fallback: str = "通用心理支持") -> str:
    for label, pattern in PROBLEM_KEYWORDS:
        if re.search(pattern, text):
            return label
    return fallback


def infer_support_focus(text: str) -> str:
    found = [label for label, pattern in FOCUS_KEYWORDS if re.search(pattern, text)]
    return "、".join(found[:3]) if found else "情绪支持"


def infer_strategies(messages: list[dict[str, str]], raw_dialog: Any = None) -> list[str]:
    strategies: list[str] = []
    if isinstance(raw_dialog, list):
        for item in raw_dialog:
            if not isinstance(item, dict):
                continue
            annotation = item.get("annotation")
            if isinstance(annotation, dict):
                value = annotation.get("strategy") or annotation.get("strategy_type")
                if value is not None:
                    label = compact_label(value)
                    if label != "unknown":
                        strategies.append(label)

    assistant_text = all_text(messages, "assistant")
    for label, pattern in STRATEGY_KEYWORDS:
        if re.search(pattern, assistant_text):
            strategies.append(label)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in strategies:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped or ["supportive_dialogue"]


def infer_severity(user_text: str) -> str:
    if HIGH_RISK_RE.search(user_text):
        return "high"
    if re.search(r"(绝望|崩溃|活不下去|严重|每天|长期|无法|失控|痛苦|抑郁|焦虑|恐惧|惊恐)", user_text):
        return "medium"
    return "low"


def normalize_record(obj: Any, dataset: str, index: int) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(obj, dict):
        return None, "not_object"

    messages, msg_stats = extract_messages(obj, dataset)
    source_id = f"{dataset}_{obj.get('id', index)}"
    user_text = all_text(messages, "user")
    full_text = all_text(messages)

    if dataset == "cpsdd":
        group = compact_label(obj.get("group"), "unknown_group")
        problem = compact_label(obj.get("problem_type"), infer_problem_topic(user_text))
        cause = compact_label(obj.get("problem_cause"), "unknown_cause")
        support_focus = compact_label(obj.get("problem_focus"), infer_support_focus(full_text))
        raw_path = obj.get("dialog_path")
        strategy_path = [str(v).strip() for v in raw_path] if isinstance(raw_path, list) else []
        inferred = infer_strategies(messages, obj.get("dialog"))
        for item in inferred:
            if item not in strategy_path:
                strategy_path.append(item)
    elif dataset == "soulchat":
        topic = compact_label(obj.get("topic"), infer_problem_topic(user_text))
        group = compact_label(obj.get("group"), "通用人群")
        problem = topic
        cause = compact_label(obj.get("cause"), "unknown_cause")
        support_focus = infer_support_focus(full_text)
        strategy_path = infer_strategies(messages)
    else:
        group = compact_label(obj.get("group"), "通用人群")
        problem = compact_label(obj.get("problem") or obj.get("problem_type") or obj.get("topic"), infer_problem_topic(user_text))
        cause = compact_label(obj.get("cause") or obj.get("problem_cause"), "unknown_cause")
        support_focus = compact_label(obj.get("support_focus") or obj.get("problem_focus"), infer_support_focus(full_text))
        strategy_path = infer_strategies(messages)

    normalized = {
        "source": dataset,
        "source_id": source_id,
        "original_index": index,
        "original_hash": original_hash(obj),
        "group": group,
        "problem": problem,
        "cause": cause,
        "support_focus": support_focus,
        "strategy_path": strategy_path or ["supportive_dialogue"],
        "severity": infer_severity(user_text),
        "messages": messages,
        "normalization_stats": msg_stats,
    }
    return normalized, None


def has_medication_directive(text: str) -> bool:
    if not MEDICATION_DIRECTIVE_RE.search(text):
        return False
    return not MEDICATION_SAFE_CONTEXT_RE.search(text)


def calculate_metrics(norm: dict[str, Any]) -> dict[str, Any]:
    messages = norm["messages"]
    assistant = [m["content"] for m in messages if m["role"] == "assistant"]
    user = [m["content"] for m in messages if m["role"] == "user"]
    full = all_text(messages)
    assistant_text = "\n".join(assistant)
    user_text = "\n".join(user)

    assistant_count = max(1, len(assistant))
    low_info = sum(1 for text in assistant if len(text.strip()) < 12 or GENERIC_SHORT_RE.match(text.strip()))
    repeated_assistant = assistant_count - len(set(normalized_for_hash(text) for text in assistant if text.strip()))
    source_stats = norm.get("normalization_stats", {})
    empty_raw = source_stats.get("empty_raw_messages", 0)
    unknown_role = source_stats.get("unknown_role_messages", 0)
    source_system = source_stats.get("source_system_messages", 0)

    high_risk_user = bool(HIGH_RISK_RE.search(user_text))
    safety_adequate = bool(SAFETY_RESPONSE_RE.search(assistant_text))
    boundary_flags = []
    if has_medication_directive(assistant_text):
        boundary_flags.append("medication_directive")
    if DIAGNOSIS_RE.search(assistant_text):
        boundary_flags.append("direct_diagnosis")
    if GUARANTEE_RE.search(assistant_text):
        boundary_flags.append("recovery_guarantee")
    if PRO_ONLY_RE.search(assistant_text):
        boundary_flags.append("professional_only_procedure")

    return {
        "turn_count": len(messages),
        "assistant_turns": len(assistant),
        "user_turns": len(user),
        "characters": len(full),
        "estimated_tokens": estimate_tokens(full),
        "assistant_mean_chars": round(sum(len(x) for x in assistant) / assistant_count, 2),
        "low_information_ratio": round(low_info / assistant_count, 4),
        "repeated_assistant_ratio": round(max(0, repeated_assistant) / assistant_count, 4),
        "empty_raw_messages": empty_raw,
        "unknown_role_messages": unknown_role,
        "source_system_messages": source_system,
        "high_risk_user": high_risk_user,
        "safety_adequate": safety_adequate,
        "high_risk_immediate_safety": high_risk_immediate_safety(messages),
        "boundary_flags": boundary_flags,
    }


def high_risk_immediate_safety(messages: list[dict[str, str]]) -> bool:
    high_risk_seen = False
    for index, message in enumerate(messages):
        if message["role"] != "user" or not HIGH_RISK_RE.search(message["content"]):
            continue
        high_risk_seen = True
        for later in messages[index + 1 : index + 3]:
            if later["role"] == "assistant":
                if SAFETY_RESPONSE_RE.search(later["content"]):
                    break
                return False
        else:
            return False
    return high_risk_seen


def filter_reason(norm: dict[str, Any], metrics: dict[str, Any]) -> str | None:
    messages = norm["messages"]
    if len(messages) < 2:
        return "broken_conversation"
    if not any(m["role"] == "user" for m in messages):
        return "no_user_message"
    if not any(m["role"] == "assistant" for m in messages):
        return "no_assistant_message"
    if metrics["unknown_role_messages"] > max(2, len(messages) * 0.3):
        return "role_mapping_failed"
    if metrics["assistant_turns"] == 0:
        return "assistant_empty"
    if metrics["low_information_ratio"] >= 0.7:
        return "low_information"
    if metrics["assistant_mean_chars"] < 16 and metrics["turn_count"] < 8:
        return "assistant_too_short"
    if metrics["estimated_tokens"] < 80:
        return "too_short_for_sft"
    if metrics["estimated_tokens"] > 5200:
        return "too_long_for_single_sft_sample"
    if metrics["boundary_flags"]:
        return "unsafe_boundary_" + "|".join(metrics["boundary_flags"])
    if metrics["high_risk_user"] and not metrics.get("high_risk_immediate_safety"):
        return "high_risk_without_safety_response"
    return None


def percentile(values: list[int], pct: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    pos = (len(values) - 1) * pct / 100.0
    lower = int(math.floor(pos))
    upper = int(math.ceil(pos))
    if lower == upper:
        return float(values[lower])
    return float(values[lower] + (values[upper] - values[lower]) * (pos - lower))


def percentiles(values: list[int]) -> dict[str, float]:
    return {f"p{p}": round(percentile(values, p), 2) for p in [1, 5, 50, 90, 95, 99]}


def label_values(norm: dict[str, Any]) -> list[tuple[str, str]]:
    pairs = [
        ("group", norm.get("group", "unknown")),
        ("problem", norm.get("problem", "unknown")),
        ("cause", norm.get("cause", "unknown")),
        ("support_focus", norm.get("support_focus", "unknown")),
        ("severity", norm.get("severity", "unknown")),
    ]
    for strategy in norm.get("strategy_path") or []:
        pairs.append(("strategy", strategy))
    return [(field, compact_label(value)) for field, value in pairs if compact_label(value) != "unknown"]


def score_record(norm: dict[str, Any], metrics: dict[str, Any], eligible_label_counts: dict[str, Counter], pct: dict[str, dict[str, float]]) -> tuple[float, float, float]:
    quality = 30.0
    quality -= metrics["low_information_ratio"] * 12
    quality -= metrics["repeated_assistant_ratio"] * 8
    if metrics["assistant_mean_chars"] < 30:
        quality -= 4
    if metrics["unknown_role_messages"]:
        quality -= min(5, metrics["unknown_role_messages"])
    if metrics["high_risk_user"] and metrics["safety_adequate"]:
        quality += 1.5
    quality = max(0.0, min(30.0, quality))

    strategy_count = len(set(norm.get("strategy_path") or []))
    if strategy_count == 0:
        strategy = 6.0
    elif strategy_count == 1:
        strategy = 12.0
    elif strategy_count <= 4:
        strategy = 17.0 + strategy_count * 0.5
    else:
        strategy = 20.0

    rarity_scores = []
    for field, value in label_values(norm):
        counts = eligible_label_counts.get(field, Counter())
        total = sum(counts.values()) or 1
        freq = counts.get(value, 0)
        rarity_scores.append(math.log((total + 1) / (freq + 1) + 1) / math.log(total + 1))
    coverage = 8.0 + 12.0 * (sum(rarity_scores) / len(rarity_scores) if rarity_scores else 0.25)
    coverage = max(0.0, min(20.0, coverage))

    turns = metrics["turn_count"]
    if 6 <= turns <= 24:
        depth = 15.0
    elif 4 <= turns < 6 or 24 < turns <= 36:
        depth = 12.0
    elif turns > 36:
        depth = 8.0
    else:
        depth = 7.0

    natural = 10.0
    full = all_text(norm["messages"])
    if re.search(r"(###|<\|end|用户：|助手：|Assistant:|Human:)", full):
        natural -= 2.0
    if len(re.findall(r"[A-Za-z]{12,}", full)) > 10:
        natural -= 1.0
    if metrics["source_system_messages"]:
        natural -= min(1.0, metrics["source_system_messages"] * 0.2)
    natural -= metrics["repeated_assistant_ratio"] * 3
    natural = max(0.0, min(10.0, natural))

    token_pcts = pct.get("estimated_tokens", {})
    token_count = metrics["estimated_tokens"]
    p5 = token_pcts.get("p5", 80)
    p50 = token_pcts.get("p50", 600)
    p95 = token_pcts.get("p95", 2500)
    if p5 <= token_count <= p95:
        length = 4.0
        if abs(token_count - p50) <= max(120, p50 * 0.75):
            length = 5.0
    else:
        length = 2.0

    final = quality + strategy + coverage + depth + natural + length
    return round(quality, 3), round(coverage, 3), round(max(0.0, min(100.0, final)), 3)


def make_hashes(messages: list[dict[str, str]]) -> tuple[str, str]:
    exact = sha256_text(json_dumps(messages))
    normalized = normalized_for_hash(all_text(messages))
    norm_hash = sha256_text(normalized)
    return exact, norm_hash


def simhash(text: str) -> int:
    tokens = TOKEN_RE.findall(text.lower())
    if len(tokens) > 320:
        step = max(1, len(tokens) // 320)
        tokens = tokens[::step][:320]
    features = tokens[:]
    features.extend("".join(tokens[i : i + 2]) for i in range(min(160, max(0, len(tokens) - 1))))
    vector = [0] * 32
    for token in features:
        h = zlib.crc32(token.encode("utf-8")) & 0xFFFFFFFF
        for bit in range(32):
            vector[bit] += 1 if (h >> bit) & 1 else -1
    value = 0
    for bit, score in enumerate(vector):
        if score >= 0:
            value |= 1 << bit
    return value


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


class Deduper:
    def __init__(self) -> None:
        self.exact: dict[str, str] = {}
        self.normalized: dict[str, str] = {}
        self.buckets: dict[tuple[int, int], list[tuple[int, str]]] = defaultdict(list)
        self.clusters: list[dict[str, Any]] = []

    def check(self, record: dict[str, Any], exact_hash: str, normalized_hash: str) -> str | None:
        sid = record["source_id"]
        if exact_hash in self.exact:
            self.clusters.append({"duplicate": sid, "duplicate_of": self.exact[exact_hash], "method": "exact_hash"})
            return self.exact[exact_hash]
        if normalized_hash in self.normalized:
            self.clusters.append({"duplicate": sid, "duplicate_of": self.normalized[normalized_hash], "method": "normalized_hash"})
            return self.normalized[normalized_hash]

        sh = simhash(normalized_for_hash(all_text(record["messages"])))
        for bucket_idx in range(4):
            key = (bucket_idx, (sh >> (bucket_idx * 8)) & 0xFF)
            for other_hash, other_sid in self.buckets.get(key, [])[:50]:
                if hamming(sh, other_hash) <= 2:
                    self.clusters.append({"duplicate": sid, "duplicate_of": other_sid, "method": "simhash32_hamming_le_2"})
                    return other_sid

        self.exact[exact_hash] = sid
        self.normalized[normalized_hash] = sid
        for bucket_idx in range(4):
            key = (bucket_idx, (sh >> (bucket_idx * 8)) & 0xFF)
            self.buckets[key].append((sh, sid))
        return None


def ark_messages(messages: list[dict[str, str]], system_prompt: str) -> list[dict[str, str]]:
    output = [{"role": "system", "content": system_prompt.strip()}]
    for message in messages:
        if message["role"] in {"user", "assistant"} and message["content"].strip():
            output.append({"role": message["role"], "content": message["content"].strip()})
    return output


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json_dumps(row) + "\n")
            count += 1
    return count


def write_duplicate_clusters(path: Path, clusters: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["duplicate", "duplicate_of", "method"])
        writer.writeheader()
        writer.writerows(clusters)


def update_best_by_label(store: dict[tuple[str, str], list[tuple[float, str, dict[str, Any]]]], record: dict[str, Any], limit: int = 5) -> None:
    for field, value in label_values(record):
        key = (field, value)
        heap = store[key]
        item = (record["final_score"], record["source_id"], record)
        if len(heap) < limit:
            heapq.heappush(heap, item)
        elif item[0] > heap[0][0]:
            heapq.heapreplace(heap, item)


def pool_add(heap: list[tuple[float, int, str, dict[str, Any]]], record: dict[str, Any], limit: int) -> None:
    item = (record["final_score"], -record["original_index"], record["source_id"], record)
    if len(heap) < limit:
        heapq.heappush(heap, item)
    elif item[0] > heap[0][0]:
        heapq.heapreplace(heap, item)


def build_pool(global_heap: list[tuple[float, int, str, dict[str, Any]]], label_best: dict[tuple[str, str], list[tuple[float, str, dict[str, Any]]]]) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for _, _, _, record in global_heap:
        records[record["source_id"]] = record
    for heap in label_best.values():
        for _, _, record in heap:
            records[record["source_id"]] = record
    return sorted(records.values(), key=lambda r: (-r["final_score"], r["source_id"]))


def selected_label_set(records: list[dict[str, Any]]) -> set[tuple[str, str]]:
    labels: set[tuple[str, str]] = set()
    for record in records:
        labels.update(label_values(record))
    return labels


def select_balanced(records: list[dict[str, Any]], target: int) -> list[dict[str, Any]]:
    if len(records) <= target:
        return records

    records = sorted(records, key=lambda r: (-r["final_score"], r["source_id"]))
    all_labels = selected_label_set(records)
    field_cardinality = Counter(field for field, _ in all_labels)
    field_caps = {
        field: max(3, math.ceil(target / max(1, cardinality) * 1.8))
        for field, cardinality in field_cardinality.items()
        if cardinality >= 3 and field not in {"severity"}
    }
    severity_caps = {"high": max(1, math.ceil(target * 0.12))}

    def can_add(record: dict[str, Any], counts: dict[str, Counter], strict: bool = True) -> bool:
        severity = compact_label(record.get("severity"))
        severity_cap = severity_caps.get(severity)
        if severity_cap and counts["severity"][severity] >= severity_cap:
            return False
        if not strict:
            return True
        for field, value in label_values(record):
            cap = field_caps.get(field)
            if cap and counts[field][value] >= cap:
                return False
        return True

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    counts: dict[str, Counter] = defaultdict(Counter)

    primary_field = "group"
    if len({r.get("group") for r in records}) <= 1 and len({r.get("problem") for r in records}) > 1:
        primary_field = "problem"
    preserve_target = int(target * 0.6)
    strata: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        strata[compact_label(record.get(primary_field))].append(record)

    total = len(records)
    quotas = {
        key: max(1, round(len(value) / total * preserve_target))
        for key, value in strata.items()
    }
    while sum(quotas.values()) > preserve_target:
        key = max(quotas, key=quotas.get)
        if quotas[key] > 1:
            quotas[key] -= 1
        else:
            break

    for key, quota in sorted(quotas.items(), key=lambda item: (-item[1], item[0])):
        added = 0
        for record in strata[key]:
            if added >= quota or len(selected) >= preserve_target:
                break
            if record["source_id"] in selected_ids:
                continue
            if can_add(record, counts, strict=True):
                selected.append(record)
                selected_ids.add(record["source_id"])
                for field, value in label_values(record):
                    counts[field][value] += 1
                added += 1

    uncovered = all_labels - selected_label_set(selected)
    correction_target = target - len(selected)
    while len(selected) < target and correction_target > 0:
        best: tuple[float, dict[str, Any]] | None = None
        for record in records:
            if record["source_id"] in selected_ids:
                continue
            if not can_add(record, counts, strict=True):
                continue
            gain = len(set(label_values(record)) & uncovered)
            score = gain * 1000 + record["coverage_score"] * 10 + record["final_score"]
            if best is None or score > best[0]:
                best = (score, record)
        if best is None:
            break
        record = best[1]
        selected.append(record)
        selected_ids.add(record["source_id"])
        for field, value in label_values(record):
            counts[field][value] += 1
        uncovered -= set(label_values(record))
        correction_target -= 1

    for strict in [True, False]:
        if len(selected) >= target:
            break
        for record in records:
            if len(selected) >= target:
                break
            if record["source_id"] in selected_ids:
                continue
            if not can_add(record, counts, strict=strict):
                continue
            selected.append(record)
            selected_ids.add(record["source_id"])
            for field, value in label_values(record):
                counts[field][value] += 1

    return sorted(selected[:target], key=lambda r: (-r["final_score"], r["source_id"]))


def manifest_row(norm: dict[str, Any] | None, metrics: dict[str, Any] | None, status: str, reason: str, dataset: str, index: int) -> dict[str, Any]:
    if norm is None:
        return {
            "source_id": f"{dataset}_{index}",
            "status": status,
            "exclude_reason": reason,
            "group": "",
            "problem": "",
            "cause": "",
            "support_focus": "",
            "strategy_path": "",
            "turn_count": 0,
            "characters": 0,
            "estimated_tokens": 0,
            "quality_score": "",
            "coverage_score": "",
            "final_score": "",
        }
    metrics = metrics or {}
    return {
        "source_id": norm["source_id"],
        "status": status,
        "exclude_reason": reason,
        "group": norm.get("group", ""),
        "problem": norm.get("problem", ""),
        "cause": norm.get("cause", ""),
        "support_focus": norm.get("support_focus", ""),
        "strategy_path": "|".join(norm.get("strategy_path") or []),
        "turn_count": metrics.get("turn_count", 0),
        "characters": metrics.get("characters", 0),
        "estimated_tokens": metrics.get("estimated_tokens", 0),
        "quality_score": norm.get("quality_score", ""),
        "coverage_score": norm.get("coverage_score", ""),
        "final_score": norm.get("final_score", ""),
    }


def write_manifest(path: Path, rows: list[dict[str, Any]], selected_ids: set[str], candidate_ids: set[str]) -> None:
    fieldnames = [
        "source_id",
        "status",
        "exclude_reason",
        "group",
        "problem",
        "cause",
        "support_focus",
        "strategy_path",
        "turn_count",
        "characters",
        "estimated_tokens",
        "quality_score",
        "coverage_score",
        "final_score",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            source_id = row["source_id"]
            output = dict(row)
            if source_id in selected_ids:
                output["status"] = "selected"
                output["exclude_reason"] = ""
            elif source_id in candidate_ids and output["status"] == "eligible":
                output["status"] = "candidate"
            writer.writerow(output)


def distribution(records: list[dict[str, Any]], field: str, topn: int = 20) -> dict[str, int]:
    counter: Counter = Counter()
    for record in records:
        if field == "strategy":
            counter.update(record.get("strategy_path") or [])
        else:
            counter[compact_label(record.get(field))] += 1
    return dict(counter.most_common(topn))


def process_dataset(
    dataset: str,
    raw_path: Path,
    target: int,
    candidate_target: int,
    output_root: Path,
    system_prompt: str,
    prior_selected_norm_hashes: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized_dir = output_root / "training" / "normalized"
    processed_dir = output_root / "training" / "processed" / DATASET_DEFAULTS[dataset]["out_dir"]
    report_dir = output_root / "training" / "reports"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    normalized_path = normalized_dir / f"{dataset}_normalized.jsonl"
    schema_report_path = report_dir / f"{dataset}_schema_report.json"

    raw_count = 0
    normalized_count = 0
    first_keys: list[str] = []
    key_counts: Counter = Counter()
    role_counts: Counter = Counter()
    reject_counts: Counter = Counter()
    eligible_label_counts: dict[str, Counter] = defaultdict(Counter)
    lengths: dict[str, list[int]] = defaultdict(list)
    normalized_error_examples: list[dict[str, Any]] = []

    with normalized_path.open("w", encoding="utf-8", newline="\n") as nf:
        for index, obj in enumerate(iter_json_records(raw_path)):
            raw_count += 1
            if raw_count % 10000 == 0:
                print(f"[{dataset}] pass1 scanned {raw_count}", flush=True)
            if isinstance(obj, dict):
                key_counts.update(obj.keys())
                if not first_keys:
                    first_keys = list(obj.keys())
            norm, err = normalize_record(obj, dataset, index)
            if err:
                reject_counts[err] += 1
                if len(normalized_error_examples) < 5:
                    normalized_error_examples.append({"index": index, "reason": err})
                continue
            normalized_count += 1
            for message in norm["messages"]:
                role_counts[message["role"]] += 1
            nf.write(json_dumps(norm) + "\n")
            metrics = calculate_metrics(norm)
            reason = filter_reason(norm, metrics)
            if reason:
                reject_counts[reason] += 1
                continue
            for name in ["turn_count", "characters", "estimated_tokens"]:
                lengths[name].append(int(metrics[name]))
            for field, value in label_values(norm):
                eligible_label_counts[field][value] += 1

    pct = {name: percentiles(values) for name, values in lengths.items()}

    schema_report = {
        "dataset": dataset,
        "raw_file": str(raw_path),
        "raw_count": raw_count,
        "normalized_count": normalized_count,
        "first_item_keys": first_keys,
        "top_level_key_counts": dict(key_counts.most_common(30)),
        "role_counts_after_normalization": dict(role_counts),
        "first_pass_reject_counts": dict(reject_counts.most_common()),
        "length_percentiles_after_hard_filters": pct,
        "eligible_label_counts_top20": {field: dict(counter.most_common(20)) for field, counter in eligible_label_counts.items()},
        "normalization_error_examples": normalized_error_examples,
        "normalized_jsonl": str(normalized_path),
    }
    schema_report_path.write_text(json_dumps(schema_report, pretty=True), encoding="utf-8")

    deduper = Deduper()
    manifest_rows: list[dict[str, Any]] = []
    global_heap: list[tuple[float, int, str, dict[str, Any]]] = []
    label_best: dict[tuple[str, str], list[tuple[float, str, dict[str, Any]]]] = defaultdict(list)
    scored_eligible = 0
    duplicate_count = 0
    cross_dataset_duplicate_count = 0
    second_pass_reject_counts: Counter = Counter()
    pool_limit = max(candidate_target * 6, target * 12, 3000)

    for index, obj in enumerate(iter_json_records(raw_path)):
        if (index + 1) % 10000 == 0:
            print(f"[{dataset}] pass2 scored {index + 1}", flush=True)
        norm, err = normalize_record(obj, dataset, index)
        if err:
            manifest_rows.append(manifest_row(None, None, "excluded", err, dataset, index))
            second_pass_reject_counts[err] += 1
            continue
        metrics = calculate_metrics(norm)
        reason = filter_reason(norm, metrics)
        if reason:
            manifest_rows.append(manifest_row(norm, metrics, "excluded", reason, dataset, index))
            second_pass_reject_counts[reason] += 1
            continue

        exact_hash, normalized_hash = make_hashes(norm["messages"])
        duplicate_of = deduper.check(norm, exact_hash, normalized_hash)
        if duplicate_of:
            duplicate_count += 1
            manifest_rows.append(manifest_row(norm, metrics, "duplicate", f"duplicate_of:{duplicate_of}", dataset, index))
            continue
        if normalized_hash in prior_selected_norm_hashes:
            cross_dataset_duplicate_count += 1
            manifest_rows.append(manifest_row(norm, metrics, "duplicate", "cross_dataset_duplicate_selected_before", dataset, index))
            continue

        quality, coverage, final = score_record(norm, metrics, eligible_label_counts, pct)
        record = FilteredRecord(
            source=norm["source"],
            source_id=norm["source_id"],
            original_index=norm["original_index"],
            original_hash=norm["original_hash"],
            group=norm["group"],
            problem=norm["problem"],
            cause=norm["cause"],
            support_focus=norm["support_focus"],
            strategy_path=norm["strategy_path"],
            severity=norm["severity"],
            messages=norm["messages"],
            metrics=metrics,
            quality_score=quality,
            coverage_score=coverage,
            final_score=final,
            exact_hash=exact_hash,
            normalized_hash=normalized_hash,
        ).__dict__
        scored_eligible += 1
        manifest_rows.append(manifest_row(record, metrics, "eligible", "", dataset, index))
        pool_add(global_heap, record, pool_limit)
        update_best_by_label(label_best, record)

    pool = build_pool(global_heap, label_best)
    candidates = select_balanced(pool, min(candidate_target, len(pool)))
    selected = select_balanced(candidates, min(target, len(candidates)))
    selected_ids = {r["source_id"] for r in selected}
    candidate_ids = {r["source_id"] for r in candidates}

    selected_stem = DATASET_DEFAULTS[dataset]["selected_stem"]
    selected_json = processed_dir / f"{selected_stem}.json"
    selected_jsonl = processed_dir / f"{selected_stem}.jsonl"
    ark_jsonl = processed_dir / f"{selected_stem}_ark.jsonl"
    candidate_jsonl = processed_dir / f"{dataset}_candidate_{len(candidates)}.jsonl"
    manifest_path = processed_dir / f"{dataset}_selection_manifest.csv"
    duplicate_clusters_path = processed_dir / f"{dataset}_duplicate_clusters.csv"
    manual_review_path = report_dir / f"{dataset}_manual_review_100.jsonl"
    report_path = report_dir / f"{dataset}_selection_report.md"

    selected_json.write_text(json_dumps(selected, pretty=True), encoding="utf-8")
    write_jsonl(selected_jsonl, selected)
    write_jsonl(candidate_jsonl, candidates)
    write_jsonl(ark_jsonl, ({"messages": ark_messages(record["messages"], system_prompt)} for record in selected))
    review_records = sorted(selected, key=lambda r: (r["final_score"], r["source_id"]))[:100]
    write_jsonl(manual_review_path, review_records)
    write_duplicate_clusters(duplicate_clusters_path, deduper.clusters)
    write_manifest(manifest_path, manifest_rows, selected_ids, candidate_ids)

    report = build_report(
        dataset=dataset,
        raw_path=raw_path,
        raw_count=raw_count,
        normalized_count=normalized_count,
        reject_counts=second_pass_reject_counts,
        duplicate_count=duplicate_count,
        cross_dataset_duplicate_count=cross_dataset_duplicate_count,
        scored_eligible=scored_eligible,
        candidate_count=len(candidates),
        selected=selected,
        pct=pct,
        output_paths={
            "normalized_jsonl": normalized_path,
            "selected_json": selected_json,
            "selected_jsonl": selected_jsonl,
            "ark_jsonl": ark_jsonl,
            "candidate_jsonl": candidate_jsonl,
            "manifest_csv": manifest_path,
            "duplicate_clusters_csv": duplicate_clusters_path,
            "manual_review_100_jsonl": manual_review_path,
            "schema_report_json": schema_report_path,
        },
    )
    report_path.write_text(report, encoding="utf-8")

    summary = {
        "dataset": dataset,
        "raw_count": raw_count,
        "normalized_count": normalized_count,
        "rejected_count": sum(second_pass_reject_counts.values()),
        "reject_counts": dict(second_pass_reject_counts.most_common()),
        "duplicate_count": duplicate_count,
        "cross_dataset_duplicate_count": cross_dataset_duplicate_count,
        "scored_eligible": scored_eligible,
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "length_percentiles": pct,
        "outputs": {key: str(value) for key, value in output_paths_for_summary(processed_dir, report_dir, normalized_path, schema_report_path, selected_stem, dataset, len(candidates)).items()},
        "selected_distribution": {
            "group": distribution(selected, "group"),
            "problem": distribution(selected, "problem"),
            "cause": distribution(selected, "cause"),
            "support_focus": distribution(selected, "support_focus"),
            "strategy": distribution(selected, "strategy"),
            "severity": distribution(selected, "severity"),
        },
    }
    return selected, summary


def output_paths_for_summary(
    processed_dir: Path,
    report_dir: Path,
    normalized_path: Path,
    schema_report_path: Path,
    selected_stem: str,
    dataset: str,
    candidate_count: int,
) -> dict[str, Path]:
    return {
        "normalized_jsonl": normalized_path,
        "selected_json": processed_dir / f"{selected_stem}.json",
        "selected_jsonl": processed_dir / f"{selected_stem}.jsonl",
        "ark_jsonl": processed_dir / f"{selected_stem}_ark.jsonl",
        "candidate_jsonl": processed_dir / f"{dataset}_candidate_{candidate_count}.jsonl",
        "manifest_csv": processed_dir / f"{dataset}_selection_manifest.csv",
        "duplicate_clusters_csv": processed_dir / f"{dataset}_duplicate_clusters.csv",
        "manual_review_100_jsonl": report_dir / f"{dataset}_manual_review_100.jsonl",
        "schema_report_json": schema_report_path,
        "selection_report_md": report_dir / f"{dataset}_selection_report.md",
    }


def build_report(
    dataset: str,
    raw_path: Path,
    raw_count: int,
    normalized_count: int,
    reject_counts: Counter,
    duplicate_count: int,
    cross_dataset_duplicate_count: int,
    scored_eligible: int,
    candidate_count: int,
    selected: list[dict[str, Any]],
    pct: dict[str, dict[str, float]],
    output_paths: dict[str, Path],
) -> str:
    selected_tokens = [int(r["metrics"]["estimated_tokens"]) for r in selected]
    selected_turns = [int(r["metrics"]["turn_count"]) for r in selected]
    avg_score = round(sum(r["final_score"] for r in selected) / len(selected), 3) if selected else 0
    lines = [
        f"# {dataset} SFT Selection Report",
        "",
        "## Summary",
        "",
        f"- Raw file: `{raw_path}`",
        f"- Raw records: {raw_count}",
        f"- Normalized records: {normalized_count}",
        f"- Rejected records: {sum(reject_counts.values())}",
        f"- In-dataset duplicates: {duplicate_count}",
        f"- Cross-dataset duplicates against earlier selected sets: {cross_dataset_duplicate_count}",
        f"- Scored eligible records: {scored_eligible}",
        f"- Candidate records: {candidate_count}",
        f"- Final selected records: {len(selected)}",
        f"- Average final score: {avg_score}",
        "",
        "## Length Distribution After Hard Filters",
        "",
        "```json",
        json_dumps(pct, pretty=True),
        "```",
        "",
        "## Reject Reasons",
        "",
    ]
    if reject_counts:
        for reason, count in reject_counts.most_common():
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Final Distribution",
            "",
            "### Group",
            "",
        ]
    )
    for field in ["group", "problem", "cause", "support_focus", "strategy", "severity"]:
        lines.append(f"### {field}")
        lines.append("")
        dist = distribution(selected, field, topn=30)
        if not dist:
            lines.append("- None")
        for key, count in dist.items():
            lines.append(f"- {key}: {count}")
        lines.append("")

    lines.extend(
        [
            "## Final Length Stats",
            "",
            f"- Selected estimated-token percentiles: `{json_dumps(percentiles(selected_tokens))}`",
            f"- Selected turn-count percentiles: `{json_dumps(percentiles(selected_turns))}`",
            "",
            "## Output Files",
            "",
        ]
    )
    for name, path in output_paths.items():
        lines.append(f"- {name}: `{path}`")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- The source files were read only and were not modified.",
            "- Ark JSONL contains only `messages`; metadata stays in the selected JSON/JSONL and manifest.",
            "- Token counts are local estimates because no tokenizer dependency is required for this data-preparation step.",
            "- No paid LLM review or rewriting was performed.",
        ]
    )
    return "\n".join(lines) + "\n"


def validate_ark_jsonl(path: Path) -> dict[str, Any]:
    count = 0
    errors: list[str] = []
    role_counts: Counter = Counter()
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            count += 1
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_no}: {exc}")
                continue
            messages = item.get("messages")
            if not isinstance(messages, list) or len(messages) < 3:
                errors.append(f"line {line_no}: messages missing or too short")
                continue
            if messages[0].get("role") != "system":
                errors.append(f"line {line_no}: first message is not system")
            if messages[-1].get("role") != "assistant":
                errors.append(f"line {line_no}: last message is not assistant")
            for message in messages:
                role = message.get("role")
                content = message.get("content")
                role_counts[role] += 1
                if role not in {"system", "user", "assistant"}:
                    errors.append(f"line {line_no}: invalid role {role!r}")
                if not isinstance(content, str) or not content.strip():
                    errors.append(f"line {line_no}: empty content")
    return {"path": str(path), "line_count": count, "role_counts": dict(role_counts), "error_count": len(errors), "errors": errors[:20]}


def read_system_prompt(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return (
        "你是一个安全型 AI 心理陪伴与自助调节助手，不是医生。"
        "禁止医学诊断、药物建议和治疗承诺。高危表达优先建议现实中的即时帮助。"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare high-quality SFT datasets for CARE-Psy Ark fine-tuning.")
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--system-prompt", type=Path, default=DEFAULT_SYSTEM_PROMPT_PATH)
    parser.add_argument("--cpsdd-path", type=Path, default=Path(DATASET_DEFAULTS["cpsdd"]["path"]))
    parser.add_argument("--psydial-path", type=Path, default=Path(DATASET_DEFAULTS["psydial_d4"]["path"]))
    parser.add_argument("--soulchat-path", type=Path, default=Path(DATASET_DEFAULTS["soulchat"]["path"]))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    datasets = [
        ("cpsdd", args.cpsdd_path),
        ("psydial_d4", args.psydial_path),
        ("soulchat", args.soulchat_path),
    ]
    for dataset, path in datasets:
        if not path.exists():
            raise FileNotFoundError(f"{dataset} raw file not found: {path}")

    system_prompt = read_system_prompt(args.system_prompt)
    summaries: list[dict[str, Any]] = []
    selected_norm_hashes: set[str] = set()
    combined_ark_rows: list[dict[str, Any]] = []

    for dataset, raw_path in datasets:
        cfg = DATASET_DEFAULTS[dataset]
        print(f"[{dataset}] processing {raw_path}", flush=True)
        selected, summary = process_dataset(
            dataset=dataset,
            raw_path=raw_path,
            target=int(cfg["target"]),
            candidate_target=int(cfg["candidate"]),
            output_root=args.output_root,
            system_prompt=system_prompt,
            prior_selected_norm_hashes=selected_norm_hashes,
        )
        for record in selected:
            selected_norm_hashes.add(record["normalized_hash"])
            combined_ark_rows.append({"messages": ark_messages(record["messages"], system_prompt)})
        summaries.append(summary)
        print(f"[{dataset}] selected {summary['selected_count']} / target {cfg['target']}", flush=True)

    processed_root = args.output_root / "training" / "processed"
    report_root = args.output_root / "training" / "reports"
    ark_dir = processed_root / "ark"
    ark_dir.mkdir(parents=True, exist_ok=True)
    combined_path = ark_dir / "care_psy_sft_selected_2000_ark.jsonl"
    write_jsonl(combined_path, combined_ark_rows)
    validations = []
    for summary in summaries:
        validations.append(validate_ark_jsonl(Path(summary["outputs"]["ark_jsonl"])))
    validations.append(validate_ark_jsonl(combined_path))

    summary_path = report_root / "sft_selection_summary.json"
    summary_md_path = report_root / "sft_selection_summary.md"
    summary_payload = {
        "system_prompt_path": str(args.system_prompt),
        "system_prompt": system_prompt,
        "datasets": summaries,
        "combined_ark_jsonl": str(combined_path),
        "ark_validations": validations,
    }
    summary_path.write_text(json_dumps(summary_payload, pretty=True), encoding="utf-8")
    summary_lines = [
        "# CARE-Psy SFT Dataset Selection Summary",
        "",
        f"- System prompt path: `{args.system_prompt}`",
        f"- Combined Ark JSONL: `{combined_path}`",
        f"- Combined records: {len(combined_ark_rows)}",
        "",
        "## Dataset Outputs",
        "",
    ]
    for summary in summaries:
        summary_lines.extend(
            [
                f"### {summary['dataset']}",
                "",
                f"- Raw records: {summary['raw_count']}",
                f"- Normalized records: {summary['normalized_count']}",
                f"- Scored eligible records: {summary['scored_eligible']}",
                f"- Candidate records: {summary['candidate_count']}",
                f"- Final selected records: {summary['selected_count']}",
                f"- Selected JSON: `{summary['outputs']['selected_json']}`",
                f"- Selected JSONL: `{summary['outputs']['selected_jsonl']}`",
                f"- Ark JSONL: `{summary['outputs']['ark_jsonl']}`",
                f"- Report: `{summary['outputs']['selection_report_md']}`",
                "",
            ]
        )
    summary_lines.extend(
        [
            "## Ark Validation",
            "",
            "```json",
            json_dumps(validations, pretty=True),
            "```",
        ]
    )
    summary_md_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(f"[done] summary: {summary_md_path}", flush=True)
    print(f"[done] combined ark: {combined_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
