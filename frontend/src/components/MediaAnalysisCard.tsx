import type { MultimodalChatResponse } from "../types/api";

type MediaAnalysisCardProps = {
  analysis: MultimodalChatResponse["media_analysis"] | null;
};

export default function MediaAnalysisCard({ analysis }: MediaAnalysisCardProps) {
  return (
    <section className="result-card">
      <h3>媒体分析</h3>
      {!analysis ? (
        <p className="muted">图片 OCR、视觉线索和视频摘要会显示在这里。</p>
      ) : (
        <div className="analysis-stack">
          <p>
            <strong>OCR：</strong>
            {analysis.ocr_text.length ? analysis.ocr_text.join(" / ") : "暂无"}
          </p>
          <p>
            <strong>可观察线索：</strong>
            {analysis.observable_cues.length ? analysis.observable_cues.join(" / ") : "暂无"}
          </p>
          <p>
            <strong>视觉表情候选：</strong>
            {analysis.visual_affect_candidates?.length
              ? analysis.visual_affect_candidates
                  .map((item) => `${item.label} ${Math.round(item.confidence * 100)}%`)
                  .join(" / ")
              : "暂无"}
          </p>
          <p>
            <strong>不确定性：</strong>
            {analysis.uncertainty.length ? analysis.uncertainty.join(" / ") : "暂无"}
          </p>
        </div>
      )}
    </section>
  );
}
