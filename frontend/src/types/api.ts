import type { Permission, Role } from "../auth/rbac";

export type CheckIn = {
  stress_score: number;
  stress_source: string[];
  stress_sources?: string[];
  preferred_style: string;
};

export type FaceEmotion = {
  label: string;
  confidence: number;
};

export type Emotion = {
  label: string;
  primary_emotion?: string;
  secondary_emotions?: string[];
  intensity: number;
  evidence: string | Array<{ source: string; content: string }>;
  supporting_evidence?: Array<{ source: string; content: string }>;
  conflicting_evidence?: Array<{ source: string; content: string }>;
  uncertainty?: string;
  dimensions?: {
    valence: { score: number; label: string };
    arousal: { score: number; label: string };
    control: { score: number; label: string };
    intensity: { score: number; label: string };
  };
};

export type Risk = {
  level: "low" | "medium" | "high";
  reason: string;
  action: string;
  matched_sources?: string[];
  dimensions?: Record<string, unknown>;
  evidence?: Array<{ source: string; content: string }>;
};

export type Intervention = {
  intervention_id?: string;
  type: string;
  title: string;
  description: string;
  reason?: string;
  source_ids?: string[];
  estimated_minutes?: number;
};

export type PsychologicalState = {
  emotion?: {
    primary?: string;
    secondary?: string[];
    intensity?: number;
    valence?: number;
    arousal?: number;
    control?: number;
  };
  cause?: {
    category?: string;
    specific?: string;
    evidence_terms?: string[];
  };
  needs?: string[];
  stage?: string;
  information_gaps?: string[];
  confidence?: number;
  uncertainty_reason?: string;
  method?: string;
};

export type StrategyPlan = {
  primary_strategy?: string;
  secondary_strategy?: string[];
  should_give_advice?: boolean;
  should_ask_question?: boolean;
  should_use_rag?: boolean;
  response_constraints?: string[];
  reason_codes?: string[];
  confidence?: number;
};

export type RAGRoute = {
  should_retrieve?: boolean;
  collections?: string[];
  query?: string;
  metadata_filter?: Record<string, unknown>;
  top_k?: number;
  reason_codes?: string[];
  fallback?: string;
};

export type KnowledgeSource = {
  source_id: string;
  citation_label?: string;
  title: string;
  organization?: string;
  year?: number | string | null;
  section: string;
  topic?: string;
  topics?: string[];
  content_preview?: string;
  official_page_url?: string;
  downloaded_url?: string;
  updated_at?: string;
  relevance_score?: number;
  evidence_level?: string;
  is_verified?: boolean;
  review_status?: string;
  retrieval_sources?: string[];
  target_collection?: string;
};

export type EvidenceItem = {
  evidence_id: string;
  source: string;
  modality: string;
  observation: string;
  confidence: number;
  is_explicit_user_statement: boolean;
  risk_relevant: boolean;
  timestamp?: Record<string, number>;
};

export type AgentTraceItem =
  | string
  | {
      agent: string;
      status: string;
      summary: string;
    };

export type ChatResponse = {
  emotion: Emotion;
  risk: Risk;
  reply: string;
  interventions: Intervention[];
  agent_trace: AgentTraceItem[];
  provider_metadata?: Record<string, unknown>;
  knowledge_sources?: KnowledgeSource[];
  psychological_state?: PsychologicalState;
  strategy_plan?: StrategyPlan;
  rag_route?: RAGRoute;
};

export type ChatRequest = {
  message: string;
  checkin?: CheckIn | null;
  face_emotion?: FaceEmotion | null;
};

export type FileKind = "image" | "audio" | "video";

export type UploadedFile = {
  file_id: string;
  session_id: string;
  kind: FileKind;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  status: string;
  preview_url: string;
  created_at: string;
};

export type MultimodalChatResponse = {
  session_id: string;
  message_id: string;
  input_modalities: string[];
  attachments: Array<{
    file_id: string;
    kind: FileKind;
    status: string;
    error?: ApiErrorDetail;
  }>;
  transcript: {
    text: string;
    utterances: Array<Record<string, unknown>>;
  };
  media_analysis: {
    image_summaries: Array<Record<string, unknown>>;
    video_summaries: Array<Record<string, unknown>>;
    ocr_text: string[];
    observable_cues: string[];
    visual_affect_candidates?: Array<{
      label: string;
      confidence: number;
      evidence?: string;
    }>;
    uncertainty: string[];
  };
  emotion: Emotion;
  risk: Risk;
  reply: string;
  interventions: Intervention[];
  agent_trace: AgentTraceItem[];
  provider_metadata: Record<string, unknown>;
  knowledge_sources?: KnowledgeSource[];
  evidence?: EvidenceItem[];
  psychological_state?: PsychologicalState;
  strategy_plan?: StrategyPlan;
  rag_route?: RAGRoute;
  retrieval?: {
    retrieval_status?: string;
    retrieved_chunks?: Array<Record<string, unknown>>;
    duration_ms?: number;
  };
  request_metrics?: {
    total_duration_ms?: number;
    stages?: Record<string, number>;
    token_usage?: Record<string, unknown>;
    estimated_cost?: Record<string, unknown>;
  };
};

export type ConversationSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message_at?: string | null;
  is_archived: boolean;
  title_manually_set: boolean;
  last_message_preview: string;
  message_count: number;
};

export type ConversationMessage = {
  id: string;
  message_id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
  sequence: number;
  message_type: "text" | "multimodal" | string;
  attachments: Array<{
    file_id: string;
    kind: FileKind;
    status: string;
    error?: ApiErrorDetail;
  }>;
  metadata: Record<string, unknown>;
};

export type ConversationListResponse = {
  items: ConversationSummary[];
  next_cursor?: string | null;
};

export type ConversationDetailResponse = {
  conversation: ConversationSummary;
  messages: ConversationMessage[];
  has_more_messages: boolean;
};

export type ConversationSendResponse = {
  conversation: ConversationSummary;
  user_message: ConversationMessage;
  assistant_message: ConversationMessage;
  result: MultimodalChatResponse & {
    conversation_id: string;
    input_modalities: string[];
  };
};

export type ApiErrorDetail = {
  code: string;
  message: string;
  stage: string;
  retryable: boolean;
  request_id?: string | null;
  retry_after_seconds?: number | null;
};

export type AuthSessionResponse = {
  authenticated: boolean;
  access_required: boolean;
  expires_at?: string | null;
};

export type AuthUser = {
  id: string;
  username: string;
  email: string;
  role: Role;
  is_active: boolean;
  permissions: Permission[];
  created_at?: string | null;
  updated_at?: string | null;
};

export type AuthMeResponse = {
  authenticated: boolean;
  user: AuthUser | null;
  auth_type: "user" | "public_access" | "local_development" | "none" | string;
};

export type AuthTokenResponse = {
  access_token: string;
  token_type: "bearer" | string;
  expires_at: string;
  user: AuthUser;
};

export type PrivacySummaryResponse = {
  session_id: string;
  retention_hours: number;
  items: string[];
};

export type MemorySnapshot = {
  session_id: string;
  memory_enabled: boolean;
  profile: Record<string, unknown>;
  memory_items: Array<{
    memory_id: string;
    key: string;
    value: unknown;
    confidence: number;
    is_user_confirmed: boolean;
    updated_at: string;
  }>;
  conversation_summary: Record<string, unknown>;
  updated_at?: string | null;
};

export type ReportItem = {
  date: string;
  stress_score: number;
  emotion: string;
};

export type ReportResponse = {
  summary: string;
  items: ReportItem[];
};

export type EvaluationFrameworkMetric = {
  name: string;
  direction: "higher_is_better" | "lower_is_better" | string;
  scale: [number, number];
};

export type EvaluationFramework = {
  name: string;
  official_status: string;
  local_status: string;
  note: string;
  metrics: EvaluationFrameworkMetric[];
};

export type EvaluationSystem = {
  name: string;
  description: string;
};

export type EvaluationRegistryResponse = {
  frameworks: Record<string, EvaluationFramework>;
  systems: Record<string, EvaluationSystem>;
  limits: {
    allow_paid_full_run: boolean;
    smoke_case_limit: number;
  };
};

export type EvaluationAblation = {
  risk: boolean;
  psychological_state: boolean;
  strategy: boolean;
  rag: boolean;
  safety: boolean;
};

export type EvaluationRunRequest = {
  system_id: string;
  frameworks: string[];
  limit: number;
  dry_run: boolean;
  ablation?: EvaluationAblation;
  use_cache?: boolean;
};

export type EvaluationMetricSummary = {
  mean: number;
  median: number;
  std: number;
  n: number;
  direction: string;
  implementation_status: string;
  scale_min: number;
  scale_max: number;
  scorer: string;
};

export type EvaluationRunSummary = {
  run_id: string;
  status: string;
  system_id: string;
  system_name?: string;
  output_dir: string;
  dry_run: boolean;
  case_count: number;
  generated_at: string;
  ablation: EvaluationAblation;
  frameworks: Record<
    string,
    {
      name: string;
      official_status: string;
      local_status: string;
      metrics: Record<string, EvaluationMetricSummary>;
    }
  >;
  system_statistics: {
    case_count: number;
    mean_latency_ms: number;
    median_latency_ms: number;
    error_count: number;
    knowledge_source_cases: number;
    high_risk_cases: number;
  };
  notes?: string[];
  judge?: Record<string, unknown>;
  errors?: Array<Record<string, unknown>>;
};

export type EvaluationRunListResponse = {
  saved_runs?: EvaluationRunSummary[];
  runs: Array<{
    run_id: string;
    status: string;
    summary: EvaluationRunSummary | Record<string, unknown>;
    output_dir: string;
    created_at: string;
  }>;
};

export type EvaluationRunDetailResponse = {
  run_id: string;
  status: string;
  config: Record<string, unknown>;
  summary: EvaluationRunSummary;
  case_scores?: Array<Record<string, unknown>>;
  output_dir: string;
};

export type EvaluationCompareResponse = {
  baseline_run_id: string;
  candidate_run_id: string;
  generated_at: string;
  metric_delta: Record<
    string,
    {
      metrics: Record<
        string,
        {
          baseline_mean: number;
          candidate_mean: number;
          delta: number;
          direction: string;
        }
      >;
    }
  >;
  export_csv: string;
};

export type KnowledgeStatusResponse = {
  registry_name: string;
  version: number;
  collections: string[];
  source_count: number;
  chunk_count: number;
  counters: Record<string, Record<string, number>>;
  production_manifest?: Record<string, unknown>;
};

export type KnowledgeReviewSource = {
  source_id: string;
  title: string;
  organization: string;
  target_collection: string;
  official_page_url: string;
  enabled: boolean;
  auto_download: boolean;
  review_priority: string;
  use_mode: string;
  review_status: string;
  latest_reviewed_by: string;
  latest_review_comment: string;
  chunk_count: number;
  pending_chunks: number;
  approved_chunks: number;
  rejected_chunks: number;
};

export type KnowledgeReviewChunk = {
  chunk_id: string;
  source_id: string;
  title: string;
  section: string;
  topic: string;
  topics: string[];
  target_collection: string;
  use_mode: string;
  risk_scope: string;
  review_priority: string;
  review_status: string;
  reviewed_by: string;
  review_comment: string;
  official_page_url: string;
  downloaded_url: string;
  content_preview: string;
  content?: string;
  char_count: number;
};

export type KnowledgeListResponse<T> = {
  items: T[];
  total: number;
};

export type ProductionStatusResponse = {
  manifest: Record<string, unknown>;
  rollback_manifest: Record<string, unknown>;
};

export type AdminUserUpdate = {
  role?: Role;
  is_active?: boolean;
};

export type AdminSystemStatus = {
  environment: string;
  public_access_enabled: boolean;
  database_url: string;
  models: Record<string, string>;
  secrets: Record<string, { configured: boolean; masked: string }>;
  feature_flags: Record<string, boolean>;
  knowledge_production: Record<string, unknown>;
};

export type AdminAuditLogItem = {
  audit_id: string;
  actor_user_id: string;
  action: string;
  target_type: string;
  target_id: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type HumanEvaluationCase = {
  run_id: string;
  case_id: string;
  case: {
    case_id: string;
    dataset?: string;
    tags?: string[];
    turns?: string[];
  };
  candidate: {
    system_id?: string;
    response: string;
    latency_ms?: number;
    errors?: Array<Record<string, unknown>>;
  };
  scores: Array<Record<string, unknown>>;
};
