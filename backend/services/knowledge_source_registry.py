from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from schemas.errors import AppError


REGISTRY_DIR = Path(__file__).resolve().parents[1] / "data" / "knowledge_base" / "sources"
V2_REGISTRY_PATH = REGISTRY_DIR / "knowledge_sources.yaml"
V1_REGISTRY_PATH = REGISTRY_DIR / "knowledge_sources_v1.yaml"
DEFAULT_REGISTRY_PATH = V2_REGISTRY_PATH if V2_REGISTRY_PATH.exists() else V1_REGISTRY_PATH


@dataclass(frozen=True)
class KnowledgeSourceEntry:
    id: str
    enabled: bool
    auto_download: bool
    organization: str
    title: str
    target_collection: str
    official_page_url: str
    download: dict[str, Any]
    raw: dict[str, Any]


@dataclass(frozen=True)
class KnowledgeSourceRegistry:
    version: int
    registry_name: str
    root: Path
    paths: dict[str, Path]
    manual_drop_zones: list[dict[str, Any]]
    collections: set[str]
    sources: list[KnowledgeSourceEntry]
    build_policy: dict[str, Any]
    processing_policy: dict[str, Any]
    index_policy: dict[str, Any]

    @property
    def auto_download_sources(self) -> list[KnowledgeSourceEntry]:
        return [source for source in self.sources if source.enabled and source.auto_download]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_domain(domain: str) -> str:
    return domain.strip().lower().removeprefix("www.")


def domain_allowed(url: str, allowed_domains: list[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    host = _normalize_domain(parsed.hostname or "")
    allowed = {_normalize_domain(item) for item in allowed_domains}
    return host in allowed


def _domains_for(url: str) -> list[str]:
    parsed = urlparse(url)
    host = _normalize_domain(parsed.hostname or "")
    if not host:
        return []
    domains = {host, f"www.{host}"}
    if host == "who.int":
        domains.update({"iris.who.int", "tdr.who.int"})
    return sorted(domains)


def _resolve_registry_path(path: str | Path | None) -> Path:
    if path is None:
        return V2_REGISTRY_PATH if V2_REGISTRY_PATH.exists() else V1_REGISTRY_PATH
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = _project_root() / candidate
    return candidate


def _resolve_data_path(value: str, project_root: Path) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate


def _required(source: dict[str, Any], key: str) -> Any:
    value = source.get(key)
    if value is None or value == "":
        raise AppError(
            "knowledge_registry_invalid",
            f"Registry source {source.get('id', '<missing-id>')} is missing required field: {key}",
            "knowledge_registry",
            status_code=400,
        )
    return value


def _validate_url(url: str, *, source_id: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise AppError(
            "knowledge_registry_invalid",
            f"Registry source {source_id} has invalid URL: {url}",
            "knowledge_registry",
            status_code=400,
        )


def _infer_source_authority(raw: dict[str, Any]) -> str:
    organization = str(raw.get("organization") or "").lower()
    evidence_level = str(raw.get("evidence_level") or "").upper()
    if "world health organization" in organization or organization == "who":
        return "international_official"
    if "教育部" in organization or "ministry" in organization:
        return "national_official"
    if "nhs" in organization:
        return "national_health_service"
    if "centre for clinical interventions" in organization or "government" in organization:
        return "clinical_public_service"
    if evidence_level == "A":
        return "high_authority"
    if evidence_level == "B":
        return "public_clinical_resource"
    return "source_unverified"


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value in (None, "", []):
        return []
    return [str(value)]


def _infer_use_mode(raw: dict[str, Any], *, collection: str) -> str:
    source_type = str(raw.get("source_type") or "").lower()
    topics = {str(item) for item in _as_list(raw.get("topic_tags") or raw.get("topics") or raw.get("topic"))}
    if collection == "safety" or topics & {"self_harm", "suicide", "suicidal_thoughts", "suicidal_plan"}:
        return "safety_only"
    if collection == "helping_skills" or "training" in source_type:
        return "helping_skills_only"
    if collection == "governance" or "policy" in source_type or "implementation" in source_type:
        return "agent_policy_only"
    if collection == "evidence" or "guideline" in source_type:
        return "clinical_reference_only"
    sensitive = {"bipolar", "bipolar_disorder", "psychosis", "eating_disorders", "OCD", "BDD", "PTSD", "substance_use", "dementia"}
    if topics & sensitive:
        return "psychoeducation_only"
    return "direct_user_support" if bool(raw.get("user_facing", True)) else "psychoeducation_only"


def _upgrade_v11_source_metadata(raw: dict[str, Any], *, collection: str) -> dict[str, Any]:
    upgraded = dict(raw)
    language_preference = upgraded.get("language_preference") or []
    if isinstance(language_preference, str):
        language_preference = [language_preference]
    topics = _as_list(upgraded.get("topic_tags") or upgraded.get("topics") or upgraded.get("topic"))
    use_mode = str(upgraded.get("use_mode") or _infer_use_mode(upgraded, collection=collection))
    risk_scope = str(upgraded.get("risk_scope") or ("safety_route_only" if collection == "safety" or use_mode == "safety_only" else "normal"))
    clinical_only = bool(upgraded.get("clinical_only", use_mode in {"clinical_reference_only", "evidence_only"}))
    user_facing = bool(
        upgraded.get(
            "user_facing",
            use_mode == "direct_user_support" and collection in {"interventions", "professional_knowledge", "campus_support"},
        )
    )
    if use_mode in {"safety_only", "clinical_reference_only", "evidence_only", "agent_policy_only", "helping_skills_only"}:
        user_facing = False
    upgraded.setdefault("download_status", "unknown")
    upgraded.setdefault("manual_fallback_allowed", True)
    upgraded.setdefault("expected_collection", collection)
    upgraded.setdefault("collection", collection)
    upgraded.setdefault("target_collection", collection)
    upgraded.setdefault("source_authority", _infer_source_authority(upgraded))
    upgraded.setdefault("review_priority", upgraded.get("priority") or "P2")
    upgraded.setdefault("language", language_preference[0] if language_preference else "")
    upgraded.setdefault("language_preference", language_preference or ([upgraded["language"]] if upgraded.get("language") else []))
    upgraded.setdefault("version", "v2")
    upgraded.setdefault("translation_group_id", upgraded.get("id", ""))
    upgraded.setdefault("topics", topics)
    upgraded.setdefault("topic_tags", topics)
    upgraded.setdefault("population_tags", _as_list(upgraded.get("population_tags")) or ["university_students", "young_adults", "adults"])
    upgraded.setdefault("life_stage_tags", _as_list(upgraded.get("life_stage_tags")))
    upgraded["use_mode"] = use_mode
    upgraded["risk_scope"] = risk_scope
    upgraded["clinical_only"] = clinical_only
    upgraded["user_facing"] = user_facing
    upgraded.setdefault("official_url", upgraded.get("official_page_url", ""))
    upgraded.setdefault("download_url", upgraded.get("asset_url") or "")
    upgraded.setdefault("license", upgraded.get("license_note") or "official_public_source_or_local_rag_only")
    upgraded.setdefault("document_hash", "")
    upgraded.setdefault("last_checked_at", "")
    upgraded.setdefault("quality_checked", False)
    upgraded.setdefault("expert_reviewed", False)
    upgraded.setdefault("eligible_for_approval", False)
    upgraded.setdefault("review_status", "pending")
    return upgraded


def load_knowledge_source_registry(path: str | Path | None = None) -> KnowledgeSourceRegistry:
    registry_path = _resolve_registry_path(path)
    if not registry_path.exists():
        raise AppError(
            "knowledge_registry_not_found",
            f"Knowledge source registry not found: {registry_path}",
            "knowledge_registry",
            status_code=404,
        )

    data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    project_root = _project_root()
    raw_paths = data.get("paths") or {}
    if not isinstance(raw_paths, dict) or not raw_paths.get("root"):
        raise AppError(
            "knowledge_registry_invalid",
            "Registry must define paths.root",
            "knowledge_registry",
            status_code=400,
        )
    resolved_paths = {
        str(key): _resolve_data_path(str(value), project_root)
        for key, value in raw_paths.items()
    }
    root = resolved_paths["root"]
    collections_data = data.get("collections") or {}
    collections = set(collections_data.keys() if isinstance(collections_data, dict) else collections_data)
    if not collections:
        raise AppError(
            "knowledge_registry_invalid",
            "Registry must define at least one collection",
            "knowledge_registry",
            status_code=400,
        )

    ids: set[str] = set()
    entries: list[KnowledgeSourceEntry] = []
    for raw in data.get("sources") or []:
        if not isinstance(raw, dict):
            raise AppError(
                "knowledge_registry_invalid",
                "Registry source entries must be mapping objects",
                "knowledge_registry",
                status_code=400,
            )
        source_id = str(raw.get("id") or raw.get("source_id") or "")
        if not source_id:
            source_id = str(_required(raw, "id"))
        if source_id in ids:
            raise AppError(
                "knowledge_registry_invalid",
                f"Duplicate registry source id: {source_id}",
                "knowledge_registry",
                status_code=400,
            )
        ids.add(source_id)
        official_page_url = str(raw.get("official_page_url") or raw.get("official_url") or "")
        if not official_page_url:
            official_page_url = str(_required(raw, "official_page_url"))
        download = raw.get("download") or {
            "mode": "html_page",
            "allowed_domains": _domains_for(official_page_url),
            "max_assets": 1,
        }
        if not isinstance(download, dict):
            raise AppError(
                "knowledge_registry_invalid",
                f"Registry source {source_id} has invalid download config",
                "knowledge_registry",
                status_code=400,
            )
        _validate_url(official_page_url, source_id=source_id)
        allowed_domains = [str(item) for item in download.get("allowed_domains") or []]
        if not allowed_domains:
            allowed_domains = _domains_for(official_page_url)
            download["allowed_domains"] = allowed_domains
        if not allowed_domains:
            raise AppError(
                "knowledge_registry_invalid",
                f"Registry source {source_id} must declare download.allowed_domains",
                "knowledge_registry",
                status_code=400,
            )
        if not domain_allowed(official_page_url, allowed_domains):
            raise AppError(
                "knowledge_registry_invalid",
                f"Registry source {source_id} official_page_url is outside allowed_domains",
                "knowledge_registry",
                status_code=400,
            )
        collection = str(raw.get("target_collection") or raw.get("collection") or raw.get("expected_collection") or "")
        if not collection:
            collection = str(_required(raw, "target_collection"))
        if collection not in collections:
            raise AppError(
                "knowledge_registry_invalid",
                f"Registry source {source_id} has unknown collection: {collection}",
                "knowledge_registry",
                status_code=400,
            )
        upgraded_raw = _upgrade_v11_source_metadata(raw, collection=collection)
        entries.append(
            KnowledgeSourceEntry(
                id=source_id,
                enabled=bool(raw.get("enabled", False)),
                auto_download=bool(raw.get("auto_download", False)),
                organization=str(_required(raw, "organization")),
                title=str(_required(raw, "title")),
                target_collection=collection,
                official_page_url=official_page_url,
                download=download,
                raw=upgraded_raw,
            )
        )

    return KnowledgeSourceRegistry(
        version=int(data.get("version") or 1),
        registry_name=str(data.get("registry_name") or registry_path.stem),
        root=root,
        paths=resolved_paths,
        manual_drop_zones=list(data.get("manual_drop_zones") or []),
        collections=collections,
        sources=entries,
        build_policy=dict(data.get("build_policy") or {}),
        processing_policy=dict(data.get("processing_policy") or {}),
        index_policy=dict(data.get("index_policy") or {}),
    )


def ensure_registry_directories(registry: KnowledgeSourceRegistry) -> dict[str, Path]:
    for path in registry.paths.values():
        path.mkdir(parents=True, exist_ok=True)
    for zone in registry.manual_drop_zones:
        if zone.get("path"):
            _resolve_data_path(str(zone["path"]), _project_root()).mkdir(parents=True, exist_ok=True)
    return registry.paths
