import { DragEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  createConversation,
  deleteConversation,
  getConversation,
  getPrivacySummary,
  listConversations,
  renameConversation,
  type CheckIn,
  type ConversationMessage,
  type ConversationSummary,
  type Emotion,
  type Intervention,
  type KnowledgeSource,
  type MultimodalChatResponse,
  type PsychologicalState,
  type PrivacySummaryResponse,
  type RAGRoute,
  type Risk,
  type StrategyPlan,
} from "../api/client";
import { deleteFile, previewUrl, uploadFile } from "../api/files";
import { createJob, getJob, type JobResponse } from "../api/jobs";
import { useAuth } from "../auth/AuthContext";
import { Permission } from "../auth/rbac";
import AgentV2Card from "../components/AgentV2Card";
import AgentTrace from "../components/AgentTrace";
import AttachmentPicker from "../components/AttachmentPicker";
import AttachmentPreview, { type LocalAttachment } from "../components/AttachmentPreview";
import AudioRecorder from "../components/AudioRecorder";
import CameraRecorder from "../components/CameraRecorder";
import EmotionCard from "../components/EmotionCard";
import EvidencePanel from "../components/EvidencePanel";
import InterventionCard from "../components/InterventionCard";
import KnowledgeSourcesCard from "../components/KnowledgeSourcesCard";
import MediaAnalysisCard from "../components/MediaAnalysisCard";
import MemoryPanel from "../components/MemoryPanel";
import RiskCard from "../components/RiskCard";
import SystemMetricsCard from "../components/SystemMetricsCard";
import TranscriptCard from "../components/TranscriptCard";
import type { AgentTraceItem, EvidenceItem, FileKind } from "../types/api";

type MultimodalChatProps = {
  checkin: CheckIn;
};

type AnalysisSnapshot = {
  reply: string;
  emotion: Emotion | null;
  risk: Risk | null;
  interventions: Intervention[];
  agentTrace: AgentTraceItem[];
  knowledgeSources: KnowledgeSource[];
  evidence: EvidenceItem[];
  psychologicalState?: PsychologicalState | null;
  strategyPlan?: StrategyPlan | null;
  ragRoute?: RAGRoute | null;
  retrieval?: MultimodalChatResponse["retrieval"];
  requestMetrics?: MultimodalChatResponse["request_metrics"];
  mediaAnalysis: MultimodalChatResponse["media_analysis"] | null;
  transcript: string;
};

function inferKind(file: File): FileKind | null {
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("audio/")) return "audio";
  if (file.type.startsWith("video/")) return "video";
  if (file.name.endsWith(".m4a") || file.name.endsWith(".opus")) return "audio";
  if (file.name.endsWith(".mkv")) return "video";
  return null;
}

function readPathConversationId(): string | null {
  const match = window.location.pathname.match(/^\/chat\/([^/]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function updateChatUrl(conversationId: string) {
  const nextPath = `/chat/${encodeURIComponent(conversationId)}`;
  if (window.location.pathname !== nextPath) {
    window.history.replaceState(null, "", nextPath);
  }
}

function formatDateGroup(value?: string | null) {
  if (!value) return "更早";
  const date = new Date(value);
  const now = new Date();
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startDate = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const diffDays = Math.floor((startToday - startDate) / 86_400_000);
  if (diffDays <= 0) return "今天";
  if (diffDays === 1) return "昨天";
  if (diffDays <= 7) return "最近7天";
  if (diffDays <= 30) return "最近30天";
  return "更早";
}

function messageTime(value: string) {
  return new Date(value).toLocaleString(undefined, {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function readableError(err: unknown) {
  if (err instanceof ApiError) {
    return `${err.detail.message}（${err.detail.code} / ${err.detail.stage}）`;
  }
  return err instanceof Error ? err.message : "请求失败，请检查后端服务。";
}

function metadataArray<T>(metadata: Record<string, unknown>, key: string): T[] {
  const value = metadata[key];
  return Array.isArray(value) ? (value as T[]) : [];
}

function metadataObject<T>(metadata: Record<string, unknown>, key: string): T | null {
  const value = metadata[key];
  return value && typeof value === "object" && !Array.isArray(value) ? (value as T) : null;
}

function buildAnalysis(messages: ConversationMessage[]): AnalysisSnapshot | null {
  const latestAssistant = [...messages].reverse().find((item) => item.role === "assistant");
  if (!latestAssistant) return null;
  const latestUser = [...messages].reverse().find((item) => item.role === "user");
  const assistantMetadata = latestAssistant.metadata ?? {};
  const userMetadata = latestUser?.metadata ?? {};
  const transcript = metadataObject<{ text?: string }>(userMetadata, "transcript");
  return {
    reply: latestAssistant.content,
    emotion: metadataObject<Emotion>(assistantMetadata, "emotion"),
    risk: metadataObject<Risk>(assistantMetadata, "risk"),
    interventions: metadataArray<Intervention>(assistantMetadata, "interventions"),
    agentTrace: metadataArray<AgentTraceItem>(assistantMetadata, "agent_trace"),
    knowledgeSources: metadataArray<KnowledgeSource>(assistantMetadata, "knowledge_sources"),
    evidence: metadataArray<EvidenceItem>(assistantMetadata, "evidence"),
    psychologicalState: metadataObject<PsychologicalState>(assistantMetadata, "psychological_state"),
    strategyPlan: metadataObject<StrategyPlan>(assistantMetadata, "strategy_plan"),
    ragRoute: metadataObject<RAGRoute>(assistantMetadata, "rag_route"),
    retrieval: metadataObject<MultimodalChatResponse["retrieval"]>(assistantMetadata, "retrieval") ?? undefined,
    requestMetrics:
      metadataObject<MultimodalChatResponse["request_metrics"]>(assistantMetadata, "request_metrics") ?? undefined,
    mediaAnalysis: metadataObject<MultimodalChatResponse["media_analysis"]>(userMetadata, "media_analysis"),
    transcript: transcript?.text ?? "",
  };
}

function terminalJob(job: JobResponse) {
  return ["completed", "failed", "cancelled"].includes(job.status);
}

function jobFailureMessage(job: JobResponse) {
  const error = job.error;
  const message = typeof error?.message === "string" ? error.message : "后台多模态任务处理失败。";
  const code = typeof error?.code === "string" ? error.code : job.status;
  const stage = typeof error?.stage === "string" ? error.stage : job.stage;
  return `${message}（${code} / ${stage}）`;
}

function jobStatusText(job: JobResponse | null) {
  if (!job) return "正在提交任务...";
  const labels: Record<string, string> = {
    queued: "任务已进入队列",
    validating: "正在校验任务",
    processing: "正在分析多模态线索",
    completed: "任务已完成",
    failed: "任务处理失败",
    cancelled: "任务已取消",
  };
  return `${labels[job.status] ?? "正在处理任务"} · ${job.stage} · ${job.progress}%`;
}

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function waitForJobCompletion(
  jobId: string,
  onUpdate: (job: JobResponse) => void,
) {
  let current = await getJob(jobId);
  onUpdate(current);
  while (!terminalJob(current)) {
    await wait(1500);
    current = await getJob(jobId);
    onUpdate(current);
  }
  return current;
}

function groupConversations(items: ConversationSummary[]) {
  return items.reduce<Record<string, ConversationSummary[]>>((groups, item) => {
    const key = formatDateGroup(item.last_message_at ?? item.updated_at);
    groups[key] = [...(groups[key] ?? []), item];
    return groups;
  }, {});
}

function MessageAttachment({
  attachment,
  conversationId,
}: {
  attachment: ConversationMessage["attachments"][number];
  conversationId: string;
}) {
  const [failed, setFailed] = useState(false);
  if (failed || attachment.status === "failed") {
    return <span className="expired-attachment">附件已过期或无法预览</span>;
  }
  const src = previewUrl(attachment.file_id, conversationId);
  return (
    <div className="message-attachment">
      {attachment.kind === "image" && <img alt="图片附件" onError={() => setFailed(true)} src={src} />}
      {attachment.kind === "audio" && <audio controls onError={() => setFailed(true)} src={src} />}
      {attachment.kind === "video" && <video controls onError={() => setFailed(true)} src={src} />}
    </div>
  );
}

export default function MultimodalChat({ checkin }: MultimodalChatProps) {
  const { hasPermission } = useAuth();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string>("");
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [message, setMessage] = useState("");
  const [attachments, setAttachments] = useState<LocalAttachment[]>([]);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [sending, setSending] = useState(false);
  const [activeJob, setActiveJob] = useState<JobResponse | null>(null);
  const [error, setError] = useState("");
  const [transcriptDraft, setTranscriptDraft] = useState("");
  const [privacySummary, setPrivacySummary] = useState<PrivacySummaryResponse | null>(null);
  const [search, setSearch] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messageListRef = useRef<HTMLDivElement | null>(null);
  const loadSeq = useRef(0);
  const currentConversationIdRef = useRef("");

  const grouped = useMemo(() => groupConversations(conversations), [conversations]);
  const currentConversation = conversations.find((item) => item.id === currentConversationId) ?? null;
  const latestAnalysis = useMemo(() => buildAnalysis(messages), [messages]);
  const canViewAgentDebug = hasPermission(Permission.AGENT_TRACE_VIEW);
  const canViewRagDebug = hasPermission(Permission.RAG_DEBUG_VIEW);
  const showInternalAnalysis = canViewAgentDebug || canViewRagDebug;

  useEffect(() => {
    currentConversationIdRef.current = currentConversationId;
  }, [currentConversationId]);

  async function refreshConversations(nextSearch = search) {
    const result = await listConversations(nextSearch);
    setConversations(result.items);
    return result.items;
  }

  function clearComposer() {
    attachments.forEach((item) => {
      if (item.localUrl) URL.revokeObjectURL(item.localUrl);
    });
    setAttachments([]);
    setMessage("");
    setTranscriptDraft("");
    setError("");
  }

  async function loadConversation(conversationId: string, pushUrl = true) {
    const seq = ++loadSeq.current;
    setLoadingConversation(true);
    setError("");
    try {
      const detail = await getConversation(conversationId);
      if (seq !== loadSeq.current) return;
      setCurrentConversationId(detail.conversation.id);
      setMessages(detail.messages);
      localStorage.setItem("psych-ai-last-conversation-id", detail.conversation.id);
      if (pushUrl) updateChatUrl(detail.conversation.id);
      clearComposer();
      setSidebarOpen(false);
    } catch (err) {
      if (seq === loadSeq.current) setError(readableError(err));
    } finally {
      if (seq === loadSeq.current) setLoadingConversation(false);
    }
  }

  async function createAndOpenConversation() {
    const created = await createConversation();
    await refreshConversations();
    await loadConversation(created.id);
  }

  useEffect(() => {
    let cancelled = false;
    async function initialize() {
      setLoadingConversation(true);
      try {
        const items = await refreshConversations("");
        if (cancelled) return;
        const requestedId = readPathConversationId();
        const savedId = localStorage.getItem("psych-ai-last-conversation-id");
        const firstId = requestedId || savedId || items[0]?.id;
        if (firstId) {
          await loadConversation(firstId, true);
        } else {
          const created = await createConversation();
          await refreshConversations("");
          await loadConversation(created.id, true);
        }
      } catch (err) {
        if (!cancelled) setError(readableError(err));
      } finally {
        if (!cancelled) setLoadingConversation(false);
      }
    }
    void initialize();
    return () => {
      cancelled = true;
      loadSeq.current += 1;
    };
  }, []);

  useEffect(() => {
    if (!currentConversationId) return;
    void getPrivacySummary(currentConversationId)
      .then(setPrivacySummary)
      .catch(() => setPrivacySummary(null));
  }, [currentConversationId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshConversations(search).catch(() => undefined);
    }, 220);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    const node = messageListRef.current;
    if (!node) return;
    const nearBottom = node.scrollHeight - node.scrollTop - node.clientHeight < 140;
    if (nearBottom) {
      node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
    }
  }, [messages, sending]);

  function addLocalFiles(files: File[], kind: FileKind) {
    if (!currentConversationId) return;
    const next = files.map((file) => ({
      id: crypto.randomUUID(),
      kind,
      file,
      localUrl: URL.createObjectURL(file),
      status: "local" as const,
      progress: 0,
    }));
    setAttachments((items) => [...items, ...next]);
    next.forEach((item) => void uploadAttachment(item));
  }

  async function uploadAttachment(item: LocalAttachment) {
    if (!currentConversationId) return;
    setAttachments((items) =>
      items.map((candidate) =>
        candidate.id === item.id ? { ...candidate, status: "uploading", progress: 1 } : candidate,
      ),
    );
    try {
      const uploaded = await uploadFile(item.file, currentConversationId, item.kind, (progress) => {
        setAttachments((items) =>
          items.map((candidate) =>
            candidate.id === item.id ? { ...candidate, progress } : candidate,
          ),
        );
      });
      setAttachments((items) =>
        items.map((candidate) =>
          candidate.id === item.id
            ? { ...candidate, upload: uploaded, status: "uploaded", progress: 100 }
            : candidate,
        ),
      );
    } catch (err) {
      setAttachments((items) =>
        items.map((candidate) =>
          candidate.id === item.id
            ? { ...candidate, status: "failed", error: readableError(err) }
            : candidate,
        ),
      );
    }
  }

  async function removeAttachment(id: string) {
    const item = attachments.find((candidate) => candidate.id === id);
    if (item?.upload && currentConversationId) {
      await deleteFile(item.upload.file_id, currentConversationId).catch(() => undefined);
    }
    if (item?.localUrl) URL.revokeObjectURL(item.localUrl);
    setAttachments((items) => items.filter((candidate) => candidate.id !== id));
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    const groupedFiles = new Map<FileKind, File[]>();
    Array.from(event.dataTransfer.files).forEach((file) => {
      const kind = inferKind(file);
      if (!kind) return;
      groupedFiles.set(kind, [...(groupedFiles.get(kind) ?? []), file]);
    });
    groupedFiles.forEach((files, kind) => addLocalFiles(files, kind));
  }

  async function send() {
    if (!currentConversationId || sending) return;
    const conversationId = currentConversationId;
    const uploaded = attachments.filter((item) => item.upload);
    const content = [message.trim(), transcriptDraft.trim()].filter(Boolean).join("\n");
    if (!content && uploaded.length === 0) {
      setError("请至少输入文字、上传文件或录制一段音频。");
      return;
    }
    if (attachments.some((item) => item.status === "uploading")) {
      setError("仍有文件正在上传，请稍后发送。");
      return;
    }
    setSending(true);
    setActiveJob(null);
    setError("");
    const optimisticId = `optimistic-${crypto.randomUUID()}`;
    const optimisticMessage: ConversationMessage = {
      id: optimisticId,
      message_id: optimisticId,
      conversation_id: currentConversationId,
      role: "user",
      content,
      created_at: new Date().toISOString(),
      sequence: messages.length + 1,
      message_type: uploaded.length ? "multimodal" : "text",
      attachments: uploaded.map((item) => ({
        file_id: item.upload!.file_id,
        kind: item.kind,
        status: item.status,
      })),
      metadata: { sending: true },
    };
    setMessages((items) => [...items, optimisticMessage]);
    try {
      const created = await createJob({
        session_id: conversationId,
        message: content,
        file_ids: uploaded.map((item) => item.upload!.file_id),
        checkin,
      });
      setActiveJob(created);
      const completed = await waitForJobCompletion(created.job_id, setActiveJob);
      if (completed.status !== "completed" || !completed.result) {
        throw new Error(jobFailureMessage(completed));
      }
      const result = completed.result;
      if (currentConversationIdRef.current !== conversationId) {
        await refreshConversations();
        return;
      }
      if (result.conversation.id !== conversationId) return;
      setMessages((items) => [
        ...items.filter((item) => item.id !== optimisticId),
        result.user_message,
        result.assistant_message,
      ]);
      setTranscriptDraft("");
      setMessage("");
      attachments.forEach((item) => {
        if (item.localUrl) URL.revokeObjectURL(item.localUrl);
      });
      setAttachments([]);
      await refreshConversations();
    } catch (err) {
      setMessages((items) =>
        items.map((item) =>
          item.id === optimisticId ? { ...item, metadata: { ...item.metadata, failed: true } } : item,
        ),
      );
      setError(readableError(err));
    } finally {
      setSending(false);
      setActiveJob(null);
    }
  }

  async function renameCurrentConversation(id: string, currentTitle: string) {
    const title = window.prompt("重命名对话", currentTitle);
    if (!title?.trim()) return;
    try {
      await renameConversation(id, title.trim());
      await refreshConversations();
    } catch (err) {
      setError(readableError(err));
    }
  }

  async function deleteCurrentConversation(id: string) {
    const confirmed = window.confirm("确定删除此对话吗？删除后无法恢复。");
    if (!confirmed) return;
    setSending(true);
    setError("");
    try {
      await deleteConversation(id);
      const remaining = await refreshConversations();
      if (remaining.length) {
        await loadConversation(remaining[0].id);
      } else {
        await createAndOpenConversation();
      }
    } catch (err) {
      setError(readableError(err));
    } finally {
      setSending(false);
    }
  }

  const sidebar = (
    <aside className="conversation-sidebar">
      <div className="conversation-sidebar-header">
        <button className="primary-button" disabled={sending} onClick={createAndOpenConversation} type="button">
          + 新建对话
        </button>
        <input
          aria-label="搜索历史对话"
          onChange={(event) => setSearch(event.target.value)}
          placeholder="搜索标题"
          value={search}
        />
      </div>
      <div className="conversation-list">
        {["今天", "昨天", "最近7天", "最近30天", "更早"].map((group) =>
          grouped[group]?.length ? (
            <section className="conversation-group" key={group}>
              <h3>{group}</h3>
              {grouped[group].map((item) => (
                <article
                  className={
                    item.id === currentConversationId
                      ? "conversation-item active"
                      : "conversation-item"
                  }
                  key={item.id}
                >
                  <button onClick={() => loadConversation(item.id)} type="button">
                    <strong>{item.title}</strong>
                    <span>{item.last_message_preview || "有什么想聊的吗？"}</span>
                    <small>{item.message_count} 条消息</small>
                  </button>
                  <div className="conversation-item-actions">
                    <button onClick={() => renameCurrentConversation(item.id, item.title)} title="重命名" type="button">
                      改
                    </button>
                    <button onClick={() => deleteCurrentConversation(item.id)} title="删除" type="button">
                      删
                    </button>
                  </div>
                </article>
              ))}
            </section>
          ) : null,
        )}
      </div>
    </aside>
  );

  return (
    <section className="conversation-shell">
      <button className="mobile-sidebar-toggle" onClick={() => setSidebarOpen(true)} type="button">
        ☰ 对话
      </button>
      <div className={sidebarOpen ? "conversation-drawer open" : "conversation-drawer"}>
        <button className="drawer-close" onClick={() => setSidebarOpen(false)} type="button">
          关闭
        </button>
        {sidebar}
      </div>
      {sidebar}

      <main className="chat-workspace">
        <header className="chat-header">
          <div>
            <span className="eyebrow">CARE Companion</span>
            <h1>{currentConversation?.title ?? "新对话"}</h1>
            <p>
              Session: {currentConversationId ? `${currentConversationId.slice(0, 8)}...` : "loading"} ·
              保留 {privacySummary?.retention_hours ?? 24} 小时上传文件
            </p>
          </div>
          {currentConversation && (
            <div className="chat-header-actions">
              <button onClick={() => renameCurrentConversation(currentConversation.id, currentConversation.title)} type="button">
                重命名
              </button>
              <button onClick={() => deleteCurrentConversation(currentConversation.id)} type="button">
                删除
              </button>
            </div>
          )}
        </header>

        {error && <div className="error-banner">{error}</div>}

        <div className="message-list" ref={messageListRef}>
          {loadingConversation ? (
            <section className="empty-conversation-state">正在加载对话...</section>
          ) : messages.length === 0 ? (
            <section className="empty-conversation-state">
              <h2>有什么想聊的吗？</h2>
              <p>可以从一段文字开始，也可以加入图片、音频或视频线索。</p>
            </section>
          ) : (
            messages.map((item) => (
              <article className={`chat-message ${item.role}`} key={item.id}>
                <div>
                  <span>{item.role === "user" ? "你" : "AI"}</span>
                  <small>{messageTime(item.created_at)}</small>
                </div>
                <p>{item.content || (item.attachments.length ? "已发送附件" : "")}</p>
                {item.attachments.length > 0 && (
                  <div className="message-attachments">
                    {item.attachments.map((attachment) => (
                      <MessageAttachment
                        attachment={attachment}
                        conversationId={item.conversation_id}
                        key={attachment.file_id}
                      />
                    ))}
                  </div>
                )}
                {Boolean(item.metadata?.failed) && <small className="inline-error">发送失败，可以重新发送。</small>}
              </article>
            ))
          )}
          {sending && (
            <section className="typing-indicator">
              <span>{jobStatusText(activeJob)}</span>
              {activeJob && (
                <div className="progress-track">
                  <span className="progress-bar" style={{ width: `${activeJob.progress}%` }} />
                </div>
              )}
            </section>
          )}
        </div>

        <section className="chat-composer" onDragOver={(event) => event.preventDefault()} onDrop={onDrop}>
          <textarea
            disabled={sending || loadingConversation}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="输入文字，也可以拖拽图片、音频或视频到这里。"
            rows={4}
            value={message}
          />
          <AttachmentPicker disabled={sending || loadingConversation} onPick={addLocalFiles} />
          <div className="recorder-row">
            <AudioRecorder disabled={sending || loadingConversation} onRecorded={(file) => addLocalFiles([file], "audio")} />
            <CameraRecorder disabled={sending || loadingConversation} onRecorded={(file) => addLocalFiles([file], "video")} />
          </div>
          <div className="attachment-list">
            {attachments.map((attachment) => (
              <AttachmentPreview
                attachment={attachment}
                key={attachment.id}
                onRemove={removeAttachment}
                sessionId={currentConversationId}
              />
            ))}
          </div>
          <TranscriptCard text={transcriptDraft} onChange={setTranscriptDraft} />
          <div className="chat-actions">
            <button
              disabled={sending}
              onClick={() => setMessage("最近论文和就业压力很大，晚上也睡不着。")}
              type="button"
            >
              普通示例
            </button>
            <button
              disabled={sending}
              onClick={() => setMessage("我有自杀的想法，怕自己会伤害自己。")}
              type="button"
            >
              高危调试
            </button>
            <button className="primary-button" disabled={sending || loadingConversation} onClick={send} type="button">
              {sending ? (activeJob ? "处理中..." : "发送中...") : "发送"}
            </button>
          </div>
        </section>

        <details className="analysis-details" open={false}>
          <summary>查看分析过程</summary>
          <div className="analysis-panel conversation-analysis-panel">
            <MediaAnalysisCard analysis={latestAnalysis?.mediaAnalysis ?? null} />
            <TranscriptCard text={latestAnalysis?.transcript ?? ""} />
            <EmotionCard emotion={latestAnalysis?.emotion ?? null} />
            <RiskCard risk={latestAnalysis?.risk ?? null} />
            {canViewAgentDebug && (
              <AgentV2Card
                psychologicalState={latestAnalysis?.psychologicalState ?? null}
                ragRoute={latestAnalysis?.ragRoute ?? null}
                strategyPlan={latestAnalysis?.strategyPlan ?? null}
              />
            )}
            {canViewRagDebug && <EvidencePanel evidence={latestAnalysis?.evidence ?? []} emotion={latestAnalysis?.emotion ?? null} />}
            {canViewRagDebug && (
              <KnowledgeSourcesCard
                retrievalStatus={latestAnalysis?.retrieval?.retrieval_status}
                sources={latestAnalysis?.knowledgeSources ?? []}
              />
            )}
            <InterventionCard
              interventions={latestAnalysis?.interventions ?? []}
              sessionId={currentConversationId}
            />
            {currentConversationId && <MemoryPanel sessionId={currentConversationId} />}
            {showInternalAnalysis && <SystemMetricsCard metrics={latestAnalysis?.requestMetrics} />}
            {canViewAgentDebug && <AgentTrace trace={latestAnalysis?.agentTrace ?? []} />}
          </div>
        </details>
      </main>
    </section>
  );
}
