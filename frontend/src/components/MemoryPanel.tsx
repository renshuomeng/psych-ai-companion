import { useEffect, useState } from "react";

import {
  deleteMemory,
  getMemory,
  rebuildMemory,
  updateMemoryEnabled,
  type MemorySnapshot,
} from "../api/client";

type Props = {
  sessionId: string;
};

export default function MemoryPanel({ sessionId }: Props) {
  const [memory, setMemory] = useState<MemorySnapshot | null>(null);
  const [status, setStatus] = useState("");

  async function refresh() {
    setMemory(await getMemory(sessionId));
  }

  useEffect(() => {
    void refresh().catch(() => setMemory(null));
  }, [sessionId]);

  async function toggleMemory(enabled: boolean) {
    setMemory(await updateMemoryEnabled(sessionId, enabled));
  }

  async function clearMemory() {
    await deleteMemory(sessionId);
    await refresh();
    setStatus("已删除当前会话记忆。");
  }

  async function rebuild() {
    await rebuildMemory(sessionId);
    await refresh();
    setStatus("已重新生成摘要。");
  }

  return (
    <section className="result-card">
      <h3>记忆与隐私</h3>
      {!memory ? (
        <p className="muted">暂未读取到记忆。</p>
      ) : (
        <>
          <div className="toggle-row">
            <span>{memory.memory_enabled ? "记忆已开启" : "记忆已关闭"}</span>
            <button onClick={() => void toggleMemory(!memory.memory_enabled)} type="button">
              {memory.memory_enabled ? "关闭" : "开启"}
            </button>
          </div>
          <div className="memory-grid">
            {memory.memory_items.length === 0 ? (
              <p className="muted">暂无结构化偏好。</p>
            ) : (
              memory.memory_items.map((item) => (
                <article key={item.memory_id}>
                  <strong>{item.key}</strong>
                  <p>{JSON.stringify(item.value)}</p>
                  <small>置信度 {Math.round(item.confidence * 100)}%</small>
                  <button onClick={() => void deleteMemory(sessionId, item.memory_id).then(refresh)} type="button">
                    删除
                  </button>
                </article>
              ))
            )}
          </div>
          <details>
            <summary>滚动摘要</summary>
            <pre>{JSON.stringify(memory.conversation_summary, null, 2)}</pre>
          </details>
          <div className="compact-actions">
            <button onClick={() => void rebuild()} type="button">重建摘要</button>
            <button onClick={() => void clearMemory()} type="button">删除全部记忆</button>
          </div>
          {status && <p className="muted">{status}</p>}
        </>
      )}
    </section>
  );
}
