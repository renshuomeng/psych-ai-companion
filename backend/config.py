from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8001
    public_base_url: str = ""
    frontend_dist_dir: Path = Field(default=Path("../frontend/dist"))
    serve_frontend: bool = True

    public_access_enabled: bool = False
    public_access_code: str = ""
    public_session_hours: int = 12
    public_session_secret: str = ""
    auth_jwt_secret: str = ""
    auth_access_token_minutes: int = 720
    initial_admin_username: str = ""
    initial_admin_email: str = ""
    initial_admin_password: str = ""

    trusted_hosts: str = "localhost,127.0.0.1,testserver,*.trycloudflare.com"
    trusted_proxy_hosts: str = "127.0.0.1,::1"
    rate_limit_chat_per_minute: int = 10
    rate_limit_upload_per_minute: int = 5
    rate_limit_auth_per_minute: int = 5
    max_active_jobs_per_session: int = 2
    multimodal_job_worker_enabled: bool = True
    multimodal_job_poll_interval_seconds: float = 1.0
    max_daily_requests_per_ip: int = 100
    max_session_attachments: int = 10
    session_retention_hours: int = 24
    cleanup_interval_seconds: int = 3600

    ark_api_key: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    llm_provider: str = "volcengine_ark"
    doubao_default_model_id: str = ""
    doubao_counselor_model_id: str = ""
    doubao_analyzer_model_id: str = ""
    doubao_planner_model_id: str = ""
    doubao_safety_model_id: str = ""
    doubao_default_temperature: float = 0.4
    doubao_counselor_temperature: float | None = None
    doubao_analyzer_temperature: float | None = None
    doubao_planner_temperature: float | None = None
    doubao_safety_temperature: float | None = None
    doubao_max_tokens: int = 700
    doubao_retry_attempts: int = 3
    doubao_timeout_seconds: float | None = None
    doubao_model_id: str = "doubao-seed-2-0-lite-260215"
    doubao_vision_model_id: str = "doubao-seed-2-0-lite-260215"
    doubao_video_model_id: str = "doubao-seed-2-0-lite-260215"

    volc_speech_api_key: str = ""
    volc_speech_resource_id: str = "volc.bigasr.auc_turbo"
    volc_speech_flash_url: str = (
        "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
    )
    volc_speech_app_id: str = ""
    volc_speech_access_key: str = ""

    upload_dir: Path = Field(default=Path("./data/uploads"))
    ffmpeg_path: Path | None = None
    ffprobe_path: Path | None = None
    max_image_mb: int = 10
    max_audio_mb: int = 100
    max_video_mb: int = 50
    max_video_seconds: int = 300
    upload_retention_hours: int = 24

    backend_host: str = "127.0.0.1"
    backend_port: int = 8001
    frontend_origin: str = "http://localhost:5173"
    request_timeout_seconds: int = 120
    enable_dev_mock: bool = False

    database_url: str = f"sqlite:///{BASE_DIR / 'database' / 'psych_ai.sqlite'}"

    rag_enabled: bool = True
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 80
    embedding_provider: str = "local"
    embedding_model: str = "local-hashing-v1"
    embedding_dimensions: int = 384
    chroma_persist_dir: Path = Field(default=Path("./data/chroma_db"))
    rag_collection_name: str = "psych_knowledge"
    rag_vector_top_k: int = 10
    rag_keyword_top_k: int = 10
    rag_final_top_k: int = 4
    rag_min_relevance_score: float = 0.45
    rag_query_rewrite_enabled: bool = True
    rag_rerank_enabled: bool = True
    rag_v1_enabled: bool = True
    rag_v1_bm25_enabled: bool = True
    rag_v1_dense_enabled: bool = True
    rag_v1_use_fallback: bool = True
    rag_index_mode: str = "staging"
    rag_staging_mode: bool = True
    rag_v1_bm25_top_k: int = 16
    rag_v1_dense_top_k: int = 12
    rag_v1_min_relevance_score: float = 0.26
    rag_v1_min_vector_score: float = 0.46
    rag_hybrid_fusion: str = "rrf"
    rag_rrf_k: int = 45
    rag_embedding_provider: str = "local"
    rag_embedding_model: str = "BAAI/bge-m3"
    rag_embedding_cache_dir: Path = Field(default=Path("./data/knowledge_base/models"))
    rag_embedding_batch_size: int = 16
    rag_v1_max_dense_chunks: int = 512
    rag_build_sample_mode: bool = False
    rag_build_sample_limit: int = 512
    retrieval_semantic_weight: float = 0.55
    retrieval_emotion_weight: float = 0.15
    retrieval_cause_weight: float = 0.15
    retrieval_strategy_weight: float = 0.10
    retrieval_risk_weight: float = 0.05

    agent_v2_enabled: bool = True
    psychological_state_analyzer_enabled: bool = True
    strategy_planner_enabled: bool = True
    rag_router_enabled: bool = True
    psy_state_low_confidence_threshold: float = 0.55

    memory_enabled: bool = True
    global_memory_across_conversations: bool = False
    auto_generate_conversation_title: bool = True
    recent_message_limit: int = 10
    summary_trigger_message_count: int = 16
    summary_max_tokens: int = 800
    context_max_input_tokens: int = 12000

    experiment_mode: bool = False
    multimodal_fusion_enabled: bool = True
    safety_llm_review_enabled: bool = True
    eval_allow_paid_full_run: bool = False
    eval_smoke_case_limit: int = 10
    eval_judge_provider: str = "heuristic_local"
    eval_judge_model_id: str = "local_smoke_heuristic_v1"
    cost_currency: str = "CNY"
    doubao_input_price_per_1k: float | None = None
    doubao_output_price_per_1k: float | None = None

    @property
    def resolved_upload_dir(self) -> Path:
        if self.upload_dir.is_absolute():
            return self.upload_dir
        return BASE_DIR / self.upload_dir

    @property
    def resolved_frontend_dist_dir(self) -> Path:
        if self.frontend_dist_dir.is_absolute():
            return self.frontend_dist_dir
        return BASE_DIR / self.frontend_dist_dir

    @property
    def resolved_knowledge_base_dir(self) -> Path:
        return BASE_DIR / "data" / "knowledge_base"

    @property
    def resolved_chroma_persist_dir(self) -> Path:
        if self.chroma_persist_dir.is_absolute():
            return self.chroma_persist_dir
        return BASE_DIR / self.chroma_persist_dir

    @property
    def resolved_rag_embedding_cache_dir(self) -> Path:
        if self.rag_embedding_cache_dir.is_absolute():
            return self.rag_embedding_cache_dir
        return BASE_DIR / self.rag_embedding_cache_dir

    @property
    def effective_rag_index_mode(self) -> str:
        mode = self.rag_index_mode.strip().lower()
        if mode in {"production", "prod", "approved"}:
            return "production"
        if mode in {"staging", "stage", "dev"}:
            return "staging"
        return "staging" if self.rag_staging_mode else "production"

    @property
    def parsed_trusted_hosts(self) -> list[str]:
        return [item.strip() for item in self.trusted_hosts.split(",") if item.strip()]

    @property
    def parsed_trusted_proxy_hosts(self) -> set[str]:
        return {item.strip() for item in self.trusted_proxy_hosts.split(",") if item.strip()}

    @property
    def is_public_mode(self) -> bool:
        return self.app_env in {"public_demo", "production"}

    @property
    def ark_configured(self) -> bool:
        return bool(self.ark_api_key.strip())

    @property
    def effective_doubao_default_model_id(self) -> str:
        return self.doubao_default_model_id.strip() or self.doubao_model_id.strip()

    @property
    def effective_doubao_timeout_seconds(self) -> float:
        return float(self.doubao_timeout_seconds or self.request_timeout_seconds)

    @property
    def effective_doubao_retry_attempts(self) -> int:
        return max(1, int(self.doubao_retry_attempts or 1))

    def doubao_model_for_agent(self, agent_name: str | None = None) -> str:
        normalized = (agent_name or "default").strip().lower()
        if normalized in {"counselor", "counseloragent", "care_psy_counselor"}:
            return self.doubao_counselor_model_id.strip() or self.effective_doubao_default_model_id
        if normalized in {"analyzer", "psychologicalstateanalyzer", "psychological_state_analyzer"}:
            return self.doubao_analyzer_model_id.strip() or self.effective_doubao_default_model_id
        if normalized in {"planner", "strategyplanner", "strategy_planner"}:
            return self.doubao_planner_model_id.strip() or self.effective_doubao_default_model_id
        if normalized in {"safety", "safetyagent", "llmsafetyagent", "llm_safety_agent"}:
            return self.doubao_safety_model_id.strip() or self.effective_doubao_default_model_id
        return self.effective_doubao_default_model_id

    def doubao_temperature_for_agent(self, agent_name: str | None = None) -> float:
        normalized = (agent_name or "default").strip().lower()
        explicit: float | None = None
        if normalized in {"counselor", "counseloragent", "care_psy_counselor"}:
            explicit = self.doubao_counselor_temperature
        elif normalized in {"analyzer", "psychologicalstateanalyzer", "psychological_state_analyzer"}:
            explicit = self.doubao_analyzer_temperature
        elif normalized in {"planner", "strategyplanner", "strategy_planner"}:
            explicit = self.doubao_planner_temperature
        elif normalized in {"safety", "safetyagent", "llmsafetyagent", "llm_safety_agent"}:
            explicit = self.doubao_safety_temperature
        return float(self.doubao_default_temperature if explicit is None else explicit)

    @property
    def speech_configured(self) -> bool:
        return bool(self.volc_speech_api_key.strip()) or bool(
            self.volc_speech_app_id.strip() and self.volc_speech_access_key.strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
