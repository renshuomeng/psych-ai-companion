import type {
  ApiErrorDetail,
  AdminAuditLogItem,
  AdminSystemStatus,
  AdminUserUpdate,
  AuthMeResponse,
  AuthSessionResponse,
  AuthTokenResponse,
  AuthUser,
  ChatRequest,
  ChatResponse,
  ConversationDetailResponse,
  ConversationListResponse,
  ConversationSendResponse,
  ConversationSummary,
  MultimodalChatResponse,
  MemorySnapshot,
  PsychologicalState,
  PrivacySummaryResponse,
  RAGRoute,
  ReportResponse,
  StrategyPlan,
  EvaluationCompareResponse,
  EvaluationRegistryResponse,
  EvaluationRunDetailResponse,
  EvaluationRunListResponse,
  EvaluationRunRequest,
  EvaluationRunSummary,
  HumanEvaluationCase,
  KnowledgeListResponse,
  KnowledgeReviewChunk,
  KnowledgeReviewSource,
  KnowledgeStatusResponse,
  ProductionStatusResponse,
} from "../types/api";
import type { Role } from "../auth/rbac";

function normalizeApiBase(value: string | undefined): string {
  const raw = (value || "/api").trim().replace(/\/+$/, "");
  return raw || "/api";
}

export const API_BASE_URL = normalizeApiBase(import.meta.env.VITE_API_BASE_URL);
export const AUTH_TOKEN_STORAGE_KEY = "psych-ai-auth-token";

export function apiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (API_BASE_URL.endsWith("/api")) {
    return `${API_BASE_URL}${normalizedPath}`;
  }
  return `${API_BASE_URL}/api${normalizedPath}`;
}

export function getStoredAuthToken(): string {
  return localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) || "";
}

export function storeAuthToken(token: string): void {
  localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
}

export function clearStoredAuthToken(): void {
  localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
}

export function authHeaders(): Record<string, string> {
  const token = getStoredAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit & { timeoutMs?: number } = {},
): Promise<Response> {
  const { timeoutMs = 15000, signal, ...fetchInit } = init;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => {
    controller.abort(new DOMException(`请求超过 ${timeoutMs}ms 未返回`, "TimeoutError"));
  }, timeoutMs);

  if (signal) {
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener("abort", () => controller.abort(), { once: true });
    }
  }

  try {
    return await fetch(input, { ...fetchInit, signal: controller.signal });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export function conversationOwnerId(): string {
  const key = "psych-ai-owner-id";
  const existing = localStorage.getItem(key);
  if (existing) return existing;
  const next = crypto.randomUUID();
  localStorage.setItem(key, next);
  return next;
}

export function ownerHeaders(): Record<string, string> {
  return { ...authHeaders(), "X-Conversation-Owner": conversationOwnerId() };
}

export class ApiError extends Error {
  detail: ApiErrorDetail;

  constructor(detail: ApiErrorDetail) {
    super(detail.message);
    this.detail = detail;
  }
}

export async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    if (payload?.error) {
      throw new ApiError(payload.error);
    }
    throw new Error(`Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function getHealth(): Promise<{
  status: string;
  service: string;
  dependencies?: Record<string, unknown>;
}> {
  const response = await fetch(apiUrl("/health"), { credentials: "include", headers: authHeaders() });
  return parseJsonResponse(response);
}

export async function sendChat(payload: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(apiUrl("/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
}

export async function sendMultimodalChat(payload: {
  session_id: string;
  message: string;
  file_ids: string[];
  checkin?: ChatRequest["checkin"];
}): Promise<MultimodalChatResponse> {
  const response = await fetch(apiUrl("/chat/multimodal"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
}

export async function createConversation(title?: string): Promise<ConversationSummary> {
  const response = await fetch(apiUrl("/conversations"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...ownerHeaders() },
    credentials: "include",
    body: JSON.stringify({ title }),
  });
  return parseJsonResponse(response);
}

export async function listConversations(search?: string): Promise<ConversationListResponse> {
  const suffix = search?.trim() ? `?search=${encodeURIComponent(search.trim())}` : "";
  const response = await fetch(apiUrl(`/conversations${suffix}`), {
    headers: ownerHeaders(),
    credentials: "include",
  });
  return parseJsonResponse(response);
}

export async function getConversation(conversationId: string): Promise<ConversationDetailResponse> {
  const response = await fetch(apiUrl(`/conversations/${encodeURIComponent(conversationId)}`), {
    headers: ownerHeaders(),
    credentials: "include",
  });
  return parseJsonResponse(response);
}

export async function renameConversation(
  conversationId: string,
  title: string,
): Promise<ConversationSummary> {
  const response = await fetch(apiUrl(`/conversations/${encodeURIComponent(conversationId)}`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...ownerHeaders() },
    credentials: "include",
    body: JSON.stringify({ title }),
  });
  return parseJsonResponse(response);
}

export async function deleteConversation(conversationId: string): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl(`/conversations/${encodeURIComponent(conversationId)}`), {
    method: "DELETE",
    headers: ownerHeaders(),
    credentials: "include",
  });
  return parseJsonResponse(response);
}

export async function sendConversationMessage(payload: {
  conversation_id: string;
  content: string;
  file_ids: string[];
  checkin?: ChatRequest["checkin"];
  client_message_id?: string;
}): Promise<ConversationSendResponse> {
  const response = await fetch(apiUrl(`/conversations/${encodeURIComponent(payload.conversation_id)}/messages`), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...ownerHeaders() },
    credentials: "include",
    body: JSON.stringify({
      content: payload.content,
      file_ids: payload.file_ids,
      checkin: payload.checkin,
      client_message_id: payload.client_message_id,
    }),
  });
  return parseJsonResponse(response);
}

export async function getReport(): Promise<ReportResponse> {
  const response = await fetch(apiUrl("/report"), { credentials: "include", headers: ownerHeaders() });
  return parseJsonResponse(response);
}

export async function getAuthSession(): Promise<AuthSessionResponse> {
  const response = await fetchWithTimeout(apiUrl("/auth/session"), { credentials: "include", timeoutMs: 12000 });
  return parseJsonResponse(response);
}

export async function submitAccessCode(accessCode: string): Promise<AuthSessionResponse> {
  const response = await fetch(apiUrl("/auth/access"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ access_code: accessCode }),
  });
  return parseJsonResponse(response);
}

export async function logoutAccess(): Promise<AuthSessionResponse> {
  const response = await fetch(apiUrl("/auth/logout"), {
    method: "POST",
    credentials: "include",
  });
  return parseJsonResponse(response);
}

export async function getCurrentUser(): Promise<AuthMeResponse> {
  const response = await fetch(apiUrl("/auth/me"), {
    credentials: "include",
    headers: authHeaders(),
  });
  return parseJsonResponse(response);
}

export async function loginAccount(payload: {
  username_or_email: string;
  password: string;
}): Promise<AuthTokenResponse> {
  const response = await fetch(apiUrl("/auth/login"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
}

export async function registerAccount(payload: {
  username: string;
  email: string;
  password: string;
}): Promise<AuthTokenResponse> {
  const response = await fetch(apiUrl("/auth/register"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
}

export async function deleteSessionData(sessionId: string): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl(`/sessions/${encodeURIComponent(sessionId)}`), {
    method: "DELETE",
    headers: authHeaders(),
    credentials: "include",
  });
  return parseJsonResponse(response);
}

export async function getPrivacySummary(sessionId: string): Promise<PrivacySummaryResponse> {
  const response = await fetch(apiUrl(`/sessions/${encodeURIComponent(sessionId)}/privacy-summary`), {
    headers: authHeaders(),
    credentials: "include",
  });
  return parseJsonResponse(response);
}

export async function getMemory(sessionId: string): Promise<MemorySnapshot> {
  const response = await fetch(apiUrl(`/sessions/${encodeURIComponent(sessionId)}/memory`), {
    headers: authHeaders(),
    credentials: "include",
  });
  return parseJsonResponse(response);
}

export async function updateMemoryEnabled(sessionId: string, memoryEnabled: boolean): Promise<MemorySnapshot> {
  const response = await fetch(apiUrl(`/sessions/${encodeURIComponent(sessionId)}/memory-settings`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    credentials: "include",
    body: JSON.stringify({ memory_enabled: memoryEnabled }),
  });
  return parseJsonResponse(response);
}

export async function deleteMemory(sessionId: string, memoryId?: string): Promise<Record<string, unknown>> {
  const suffix = memoryId ? `?memory_id=${encodeURIComponent(memoryId)}` : "";
  const response = await fetch(apiUrl(`/sessions/${encodeURIComponent(sessionId)}/memory${suffix}`), {
    method: "DELETE",
    headers: authHeaders(),
    credentials: "include",
  });
  return parseJsonResponse(response);
}

export async function rebuildMemory(sessionId: string): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl(`/sessions/${encodeURIComponent(sessionId)}/memory/rebuild`), {
    method: "POST",
    headers: authHeaders(),
    credentials: "include",
  });
  return parseJsonResponse(response);
}

export async function startIntervention(payload: {
  intervention_id: string;
  session_id: string;
  type: string;
  title: string;
  pre_stress_score?: number;
}): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl(`/interventions/${encodeURIComponent(payload.intervention_id)}/start`), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
}

export async function completeIntervention(
  interventionId: string,
  payload: { post_stress_score?: number },
): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl(`/interventions/${encodeURIComponent(interventionId)}/complete`), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
}

export async function sendInterventionFeedback(
  interventionId: string,
  payload: { helpfulness?: number; feedback_text?: string },
): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl(`/interventions/${encodeURIComponent(interventionId)}/feedback`), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
}

export async function importKnowledge(): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl("/knowledge/staging/rebuild"), {
    method: "POST",
    headers: authHeaders(),
    credentials: "include",
  });
  return parseJsonResponse(response);
}

export async function getEvaluationRegistry(): Promise<EvaluationRegistryResponse> {
  const response = await fetch(apiUrl("/evaluation/registry"), {
    headers: authHeaders(),
    credentials: "include",
  });
  return parseJsonResponse(response);
}

export async function runEvaluation(payload?: Partial<EvaluationRunRequest>): Promise<EvaluationRunSummary> {
  const response = await fetch(apiUrl("/evaluation/run"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    credentials: "include",
    body: JSON.stringify(payload || {}),
  });
  return parseJsonResponse(response);
}

export async function listEvaluationRuns(): Promise<EvaluationRunListResponse> {
  const response = await fetch(apiUrl("/evaluation/runs"), {
    headers: authHeaders(),
    credentials: "include",
  });
  return parseJsonResponse(response);
}

export async function getEvaluationRun(runId: string): Promise<EvaluationRunDetailResponse> {
  const response = await fetch(apiUrl(`/evaluation/runs/${encodeURIComponent(runId)}`), {
    headers: authHeaders(),
    credentials: "include",
  });
  return parseJsonResponse(response);
}

export async function compareEvaluationRuns(payload: {
  baseline_run_id: string;
  candidate_run_id: string;
}): Promise<EvaluationCompareResponse> {
  const response = await fetch(apiUrl("/evaluation/compare"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
}

export async function getKnowledgeStatus(): Promise<KnowledgeStatusResponse> {
  const response = await fetch(apiUrl("/knowledge/status"), {
    credentials: "include",
    headers: authHeaders(),
  });
  return parseJsonResponse(response);
}

export async function listKnowledgeSources(): Promise<KnowledgeListResponse<KnowledgeReviewSource>> {
  const response = await fetch(apiUrl("/knowledge/sources"), {
    credentials: "include",
    headers: authHeaders(),
  });
  return parseJsonResponse(response);
}

export async function decideKnowledgeSource(
  sourceId: string,
  decision: "approve" | "reject" | "flag",
  payload: { comment?: string; reason?: string },
): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl(`/knowledge/sources/${encodeURIComponent(sourceId)}/${decision}`), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
}

export async function listKnowledgeChunks(params: {
  status?: string;
  queue?: "all" | "safety" | "intervention";
  priority?: string;
  source_id?: string;
} = {}): Promise<KnowledgeListResponse<KnowledgeReviewChunk>> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) query.set(key, value);
  });
  const suffix = query.toString() ? `?${query.toString()}` : "";
  const response = await fetch(apiUrl(`/knowledge/chunks${suffix}`), {
    credentials: "include",
    headers: authHeaders(),
  });
  return parseJsonResponse(response);
}

export async function decideKnowledgeChunk(
  chunkId: string,
  decision: "approve" | "reject",
  payload: { comment?: string; reason?: string },
): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl(`/knowledge/chunks/${encodeURIComponent(chunkId)}/${decision}`), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
}

export async function getProductionStatus(): Promise<ProductionStatusResponse> {
  const response = await fetch(apiUrl("/knowledge/production/status"), {
    credentials: "include",
    headers: authHeaders(),
  });
  return parseJsonResponse(response);
}

export async function publishProductionKnowledge(payload: {
  dry_run?: boolean;
  batch_size?: number | null;
  allow_empty?: boolean;
}): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl("/knowledge/production/publish"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
}

export async function rollbackProductionKnowledge(payload: {
  dry_run?: boolean;
  backup_dir?: string | null;
}): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl("/knowledge/production/rollback"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
}

export async function getDebugAgent(): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl("/debug/agent"), {
    credentials: "include",
    headers: authHeaders(),
  });
  return parseJsonResponse(response);
}

export async function getDebugRag(): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl("/debug/rag"), {
    credentials: "include",
    headers: authHeaders(),
  });
  return parseJsonResponse(response);
}

export async function runRetrievalDebug(query: string): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl(`/debug/retrieval?query=${encodeURIComponent(query)}`), {
    credentials: "include",
    headers: authHeaders(),
  });
  return parseJsonResponse(response);
}

export async function listHumanEvaluationCases(runId?: string): Promise<{ run_id: string; items: HumanEvaluationCase[] }> {
  const suffix = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  const response = await fetch(apiUrl(`/evaluation/review/cases${suffix}`), {
    credentials: "include",
    headers: authHeaders(),
  });
  return parseJsonResponse(response);
}

export async function scoreHumanEvaluationCase(payload: {
  run_id?: string;
  case_id: string;
  score?: number | null;
  rubric?: Record<string, unknown>;
  comment?: string;
  llm_judge_reviewed?: boolean;
}): Promise<Record<string, unknown>> {
  const response = await fetch(apiUrl("/evaluation/review/score"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
}

export async function exportHumanEvaluationCsv(): Promise<string> {
  const response = await fetch(apiUrl("/evaluation/review/export"), {
    credentials: "include",
    headers: authHeaders(),
  });
  if (!response.ok) {
    await parseJsonResponse(response);
  }
  return response.text();
}

export async function listAdminUsers(): Promise<{ items: AuthUser[] }> {
  const response = await fetch(apiUrl("/admin/users"), {
    credentials: "include",
    headers: authHeaders(),
  });
  return parseJsonResponse(response);
}

export async function createAdminUser(payload: {
  username: string;
  email: string;
  password: string;
  role: Role;
  is_active?: boolean;
}): Promise<AuthUser> {
  const response = await fetch(apiUrl("/admin/users"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
}

export async function updateAdminUser(userId: string, payload: AdminUserUpdate): Promise<AuthUser> {
  const response = await fetch(apiUrl(`/admin/users/${encodeURIComponent(userId)}`), {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
}

export async function getAdminSystemStatus(): Promise<AdminSystemStatus> {
  const response = await fetch(apiUrl("/admin/system"), {
    credentials: "include",
    headers: authHeaders(),
  });
  return parseJsonResponse(response);
}

export async function getAdminAuditLog(): Promise<{ items: AdminAuditLogItem[] }> {
  const response = await fetch(apiUrl("/admin/audit-log"), {
    credentials: "include",
    headers: authHeaders(),
  });
  return parseJsonResponse(response);
}

export type {
  AdminAuditLogItem,
  AdminSystemStatus,
  AdminUserUpdate,
  AgentTraceItem,
  ApiErrorDetail,
  AuthMeResponse,
  AuthSessionResponse,
  AuthTokenResponse,
  AuthUser,
  ChatRequest,
  ChatResponse,
  CheckIn,
  ConversationDetailResponse,
  ConversationListResponse,
  ConversationMessage,
  ConversationSendResponse,
  ConversationSummary,
  Emotion,
  FileKind,
  Intervention,
  KnowledgeSource,
  MultimodalChatResponse,
  MemorySnapshot,
  PsychologicalState,
  PrivacySummaryResponse,
  RAGRoute,
  ReportItem,
  ReportResponse,
  Risk,
  StrategyPlan,
  EvaluationAblation,
  EvaluationCompareResponse,
  EvaluationFramework,
  EvaluationRegistryResponse,
  EvaluationRunDetailResponse,
  EvaluationRunListResponse,
  EvaluationRunRequest,
  EvaluationRunSummary,
  EvaluationSystem,
  HumanEvaluationCase,
  KnowledgeListResponse,
  KnowledgeReviewChunk,
  KnowledgeReviewSource,
  KnowledgeStatusResponse,
  UploadedFile,
  ProductionStatusResponse,
} from "../types/api";
