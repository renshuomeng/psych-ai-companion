from __future__ import annotations

import json
import math
import pickle
import re
from pathlib import Path
from typing import Any

from schemas.errors import AppError


STAGING_COLLECTIONS = {
    "professional_knowledge": "psych_professional_knowledge_staging",
    "interventions": "psych_interventions_staging",
    "helping_skills": "psych_helping_skills_staging",
    "campus_support": "psych_campus_support_staging",
    "safety": "psych_safety_staging",
    "evidence": "psych_evidence_staging",
    "governance": "psych_governance_staging",
    "case_rag": "psych_case_rag_staging",
}


PRODUCTION_COLLECTIONS = {
    collection: name.replace("_staging", "_production")
    for collection, name in STAGING_COLLECTIONS.items()
}


TOPIC_SEARCH_ALIASES = {
    "academic_stress": ["学业压力", "论文压力", "考试压力", "学习焦虑", "academic pressure", "study stress"],
    "career_anxiety": ["就业焦虑", "求职压力", "未来焦虑", "职业焦虑", "job search stress"],
    "career_uncertainty": ["未来迷茫", "职业不确定", "不知道以后", "不知道做什么", "future uncertainty"],
    "uncertainty": ["不确定感", "无法确定", "未来不确定", "uncertainty"],
    "problem_solving": ["问题解决", "拆解问题", "行动计划", "problem solving", "action plan"],
    "planning": ["计划", "规划", "任务拆分", "planning"],
    "action_plan": ["行动计划", "下一步", "小步骤", "action plan", "small steps"],
    "relationships": ["人际关系", "关系困扰", "同学关系", "朋友关系", "relationships"],
    "social_relationships": ["人际关系", "同伴关系", "同学关系", "social relationships"],
    "communication": ["沟通", "表达", "倾听", "communication"],
    "active_listening": ["积极倾听", "陪伴", "倾听", "active listening"],
    "empathy": ["共情", "理解", "empathy"],
    "parent_child_relationship": ["亲子关系", "家长支持", "父母孩子", "parent child relationship"],
    "family_relationships": ["家庭关系", "家庭沟通", "family relationships"],
    "caregiver_support": ["照护者支持", "家人支持", "caregiver support"],
    "school_support": ["学校支持", "上学适应", "不想去学校", "school support"],
    "student_mental_health": ["学生心理健康", "校园心理健康", "student mental health"],
    "campus_support": ["校园支持", "学校心理支持", "campus support"],
    "loneliness": ["孤独", "孤独感", "一个人在家", "loneliness"],
    "social_isolation": ["社会隔离", "不愿意出门", "不和朋友联系", "social isolation"],
    "social_support": ["社会支持", "支持系统", "朋友支持", "social support"],
    "self_compassion": ["自我关怀", "自我慈悲", "温和对待自己", "self compassion"],
    "self_criticism": ["自责", "责怪自己", "自我批评", "self criticism"],
    "shame": ["羞耻感", "不够好", "shame"],
    "low_mood": ["低落情绪", "情绪低落", "没动力", "low mood"],
    "depression": ["抑郁", "抑郁症", "depression", "major depressive disorder"],
    "depressive_feelings": ["低落", "想哭", "绝望", "depressive feelings"],
    "anxiety": ["焦虑", "担忧", "紧张", "anxiety"],
    "anxiety_disorders": ["焦虑症", "焦虑障碍", "anxiety disorders"],
    "panic": ["惊恐", "心跳很快", "喘不过气", "panic"],
    "bipolar_disorder": ["双相", "双相情感障碍", "bipolar disorder"],
    "mania": ["躁狂", "情绪高涨", "精力异常", "mania"],
    "ocd": ["强迫症", "反复检查", "OCD", "obsessive compulsive disorder"],
    "ptsd": ["创伤后应激", "PTSD", "噩梦", "post traumatic stress"],
    "adhd": ["多动症", "注意力缺陷", "ADHD"],
    "autism": ["自闭症", "孤独症", "autism"],
    "eating_disorders": ["进食障碍", "控制饮食", "害怕变胖", "eating disorders"],
    "dementia": ["失智", "阿尔茨海默", "认知退化", "dementia"],
    "substance_use": ["物质使用", "成瘾", "酒精问题", "substance use"],
    "emotion_regulation": ["情绪调节", "情绪失控", "emotion regulation"],
    "distress_tolerance": ["痛苦耐受", "稳定下来", "distress tolerance"],
    "anger": ["愤怒", "生气", "anger"],
    "sleep": ["睡眠", "失眠", "睡不着", "sleep"],
    "insomnia": ["失眠", "入睡困难", "insomnia"],
    "sleep_hygiene": ["睡眠卫生", "睡前程序", "sleep hygiene"],
    "worry": ["担忧", "反刍", "停不下来", "worry"],
    "perinatal": ["孕产期", "怀孕", "产后", "perinatal"],
    "postpartum": ["产后", "postpartum"],
    "pregnancy": ["怀孕", "孕期", "pregnancy"],
    "perinatal_crisis": ["孕产期危机", "产后危机", "perinatal crisis"],
    "self_harm": ["自伤", "自残", "self harm"],
    "suicidal_thoughts": ["轻生念头", "自杀念头", "suicidal thoughts"],
    "minor_safeguarding": ["未成年人保护", "青少年自伤", "minor safeguarding"],
    "harm_to_others": ["伤害他人", "攻击冲动", "harm to others"],
    "domestic_violence": ["家庭暴力", "伴侣威胁", "domestic violence"],
    "substance_crisis": ["酒后失控", "物质危机", "substance crisis"],
    "severe_psychosis": ["幻听", "命令我伤害", "severe psychosis"],
}

POPULATION_SEARCH_ALIASES = {
    "university_students": ["大学生", "学生", "高校学生", "college students", "university students"],
    "young_adults": ["青年", "年轻人", "young adults"],
    "adults": ["成人", "成年人", "adults"],
    "children": ["儿童", "孩子", "children"],
    "adolescents": ["青少年", "青春期", "adolescents"],
    "parents": ["父母", "家长", "parents"],
    "caregivers": ["照护者", "照顾者", "caregivers"],
    "older_adults": ["老人", "老年人", "退休", "older adults"],
    "workers": ["职场人", "上班族", "workers"],
    "pregnant_people": ["孕妇", "怀孕", "pregnant people"],
    "postpartum_people": ["产后", "新手妈妈", "postpartum people"],
    "family_members_supporting_others": ["家人支持", "朋友陪伴", "family support"],
    "people_exposed_to_trauma": ["经历创伤的人", "创伤经历", "people exposed to trauma"],
}


def normalize_index_mode(index_mode: str | None = None) -> str:
    mode = str(index_mode or "staging").strip().lower()
    if mode in {"production", "prod", "approved"}:
        return "production"
    return "staging"


def collection_name_for(collection: str, index_mode: str | None = None) -> str:
    mode = normalize_index_mode(index_mode)
    mapping = PRODUCTION_COLLECTIONS if mode == "production" else STAGING_COLLECTIONS
    return mapping.get(collection, f"psych_{collection}_{mode}")


def bm25_dir_for(root: Path, index_mode: str | None = None, *, require_existing: bool = False) -> Path:
    mode = normalize_index_mode(index_mode)
    mode_dir = root / mode
    if require_existing:
        if (mode_dir / "bm25_index.pkl").exists() and (mode_dir / "documents.jsonl").exists():
            return mode_dir
        if mode == "staging" and (root / "bm25_index.pkl").exists() and (root / "documents.jsonl").exists():
            return root
    return mode_dir


def tokenize_for_bm25(text: str) -> list[str]:
    normalized = text.lower()
    tokens = re.findall(r"[a-z0-9_]+", normalized)
    if re.search(r"[\u4e00-\u9fff]", normalized):
        chars = [ch for ch in normalized if "\u4e00" <= ch <= "\u9fff"]
        try:
            import jieba

            tokens.extend(item.strip() for item in jieba.lcut(normalized) if item.strip())
        except Exception:
            pass
        tokens.extend(chars)
        tokens.extend("".join(chars[index : index + 2]) for index in range(max(0, len(chars) - 1)))
    return [token for token in tokens if token.strip()]


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value in (None, "", []):
        return []
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,;，；]\s*", value) if item.strip()]
    return [str(value)]


def _alias_key(value: str) -> str:
    return re.sub(r"[\s\-]+", "_", value.strip().lower())


def _aliases_for(values: list[str], mapping: dict[str, list[str]]) -> list[str]:
    aliases: list[str] = []
    for value in values:
        key = _alias_key(str(value))
        aliases.append(str(value))
        aliases.append(key)
        aliases.append(key.replace("_", " "))
        aliases.extend(mapping.get(key, []))
    seen: set[str] = set()
    output: list[str] = []
    for alias in aliases:
        cleaned = " ".join(str(alias).strip().split())
        if not cleaned:
            continue
        normalized = cleaned.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        output.append(cleaned)
    return output


def _bm25_search_text(chunk: dict[str, Any]) -> str:
    topics = _as_list(chunk.get("topic_tags") or chunk.get("topics") or chunk.get("topic"))
    if chunk.get("topic"):
        topics.append(str(chunk["topic"]))
    populations = _as_list(chunk.get("population_tags"))
    life_stages = _as_list(chunk.get("life_stage_tags"))
    fields = [
        chunk.get("content", ""),
        chunk.get("title", ""),
        chunk.get("section", ""),
        chunk.get("source_id", ""),
        chunk.get("organization", ""),
        chunk.get("target_collection", ""),
        chunk.get("use_mode", ""),
        chunk.get("risk_scope", ""),
        " ".join(_aliases_for(topics, TOPIC_SEARCH_ALIASES)),
        " ".join(_aliases_for(populations, POPULATION_SEARCH_ALIASES)),
        " ".join(life_stages),
    ]
    return " ".join(str(field) for field in fields if str(field).strip())


def build_bm25_index(chunks: list[dict[str, Any]], index_dir: Path) -> dict[str, Any]:
    try:
        from rank_bm25 import BM25Okapi
    except Exception as exc:
        raise AppError(
            "bm25_dependency_missing",
            "rank_bm25 is required to build the BM25 index",
            "rag_v1_index",
            status_code=503,
        ) from exc
    index_dir.mkdir(parents=True, exist_ok=True)
    tokenized = [tokenize_for_bm25(_bm25_search_text(chunk)) for chunk in chunks]
    model = BM25Okapi(tokenized) if tokenized else None
    with (index_dir / "bm25_index.pkl").open("wb") as handle:
        pickle.dump(model, handle)
    (index_dir / "documents.jsonl").write_text(
        "\n".join(json.dumps(chunk, ensure_ascii=False) for chunk in chunks) + ("\n" if chunks else ""),
        encoding="utf-8",
    )
    metadata = {
        "status": "ready",
        "documents": len(chunks),
        "average_tokens": round(sum(len(tokens) for tokens in tokenized) / max(len(tokenized), 1), 2),
    }
    (index_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata


def load_bm25_index(index_dir: Path) -> tuple[Any, list[dict[str, Any]]]:
    with (index_dir / "bm25_index.pkl").open("rb") as handle:
        model = pickle.load(handle)
    docs = [
        json.loads(line)
        for line in (index_dir / "documents.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return model, docs


def query_bm25(index_dir: Path, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    model, docs = load_bm25_index(index_dir)
    if model is None or not docs:
        return []
    query_tokens = tokenize_for_bm25(query)
    scores = model.get_scores(query_tokens)
    ranked = sorted(enumerate(scores), key=lambda item: float(item[1]), reverse=True)[:top_k]
    if ranked and all(float(score) <= 0 for _, score in ranked):
        query_set = set(query_tokens)
        overlap_scores = [
            (index, len(query_set & set(tokenize_for_bm25(_bm25_search_text(doc)))))
            for index, doc in enumerate(docs)
        ]
        ranked = sorted(overlap_scores, key=lambda item: int(item[1]), reverse=True)[:top_k]
    results: list[dict[str, Any]] = []
    max_score = max([float(score) for _, score in ranked] or [1.0])
    for index, score in ranked:
        if float(score) <= 0:
            continue
        chunk = docs[index]
        results.append({**chunk, "score": round(float(score) / max(max_score, 1e-6), 4), "raw_score": float(score)})
    return results


def _chroma_metadata(chunk: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(chunk)
    metadata.pop("content", None)
    for key, value in list(metadata.items()):
        if isinstance(value, (list, dict)):
            metadata[key] = json.dumps(value, ensure_ascii=False)
        elif value is None:
            metadata[key] = ""
    return metadata


def build_chroma_indexes(
    chunks: list[dict[str, Any]],
    embeddings: list[list[float]],
    persist_dir: Path,
    collections: list[str] | None = None,
    index_mode: str = "staging",
) -> dict[str, Any]:
    if len(chunks) != len(embeddings):
        raise AppError(
            "embedding_count_mismatch",
            "Chunk count and embedding count do not match",
            "rag_v1_index",
            status_code=500,
        )
    try:
        import chromadb
        from chromadb.config import Settings
    except Exception as exc:
        raise AppError(
            "chroma_dependency_missing",
            "chromadb is required to build Chroma staging indexes",
            "rag_v1_index",
            status_code=503,
        ) from exc
    persist_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(persist_dir),
        settings=Settings(anonymized_telemetry=False),
    )
    by_collection: dict[str, list[tuple[dict[str, Any], list[float]]]] = {}
    for chunk, embedding in zip(chunks, embeddings):
        collection = str(chunk.get("target_collection") or "professional_knowledge")
        by_collection.setdefault(collection, []).append((chunk, embedding))

    status: dict[str, Any] = {}
    mode = normalize_index_mode(index_mode)
    expected_collections = list(collections or by_collection.keys())
    for collection in expected_collections:
        items = by_collection.get(collection, [])
        name = collection_name_for(collection, mode)
        try:
            client.delete_collection(name)
        except Exception:
            pass
        chroma_collection = client.get_or_create_collection(name=name, metadata={"collection": collection, "stage": mode})
        if items:
            for start in range(0, len(items), 500):
                batch = items[start : start + 500]
                chroma_collection.add(
                    ids=[chunk["chunk_id"] for chunk, _ in batch],
                    documents=[chunk["content"] for chunk, _ in batch],
                    metadatas=[_chroma_metadata(chunk) for chunk, _ in batch],
                    embeddings=[embedding for _, embedding in batch],
                )
        status[name] = {"collection": collection, "count": len(items), "status": "ready"}
    return status


def query_chroma(
    persist_dir: Path,
    query_embedding: list[float],
    top_k: int = 5,
    collection: str | None = None,
    index_mode: str = "staging",
) -> list[dict[str, Any]]:
    try:
        import chromadb
        from chromadb.config import Settings
    except Exception as exc:
        raise AppError(
            "chroma_dependency_missing",
            "chromadb is required to query Chroma staging indexes",
            "rag_v1_index",
            status_code=503,
        ) from exc
    client = chromadb.PersistentClient(
        path=str(persist_dir),
        settings=Settings(anonymized_telemetry=False),
    )
    mode = normalize_index_mode(index_mode)
    names = [collection_name_for(collection, mode)] if collection else [
        item.name for item in client.list_collections() if item.name.endswith(f"_{mode}")
    ]
    results: list[dict[str, Any]] = []
    for name in names:
        try:
            coll = client.get_collection(name)
            data = coll.query(query_embeddings=[query_embedding], n_results=top_k)
        except Exception:
            continue
        ids = data.get("ids", [[]])[0]
        docs = data.get("documents", [[]])[0]
        metadatas = data.get("metadatas", [[]])[0]
        distances = data.get("distances", [[]])[0]
        for chunk_id, doc, metadata, distance in zip(ids, docs, metadatas, distances):
            score = 1.0 / (1.0 + math.sqrt(max(float(distance), 0.0)))
            results.append({**(metadata or {}), "chunk_id": chunk_id, "content": doc, "score": round(score, 4), "collection_name": name})
    return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]
