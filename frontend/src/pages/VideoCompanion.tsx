export default function VideoCompanion() {
  return (
    <section className="page-stack">
      <div className="section-heading">
        <span className="eyebrow">Video Companion</span>
        <h1>视频陪伴占位</h1>
        <p>摄像头表情识别将在下一阶段实现，计划使用 face-api.js 或等价方案。</p>
      </div>

      <section className="placeholder-panel">
        <div className="camera-frame">
          <span>Camera Placeholder</span>
        </div>
        <p>
          第一阶段不会打开真实摄像头。后续可将识别到的表情 label 与 confidence 传入
          Chat 接口的 <code>face_emotion</code> 字段。
        </p>
      </section>
    </section>
  );
}
