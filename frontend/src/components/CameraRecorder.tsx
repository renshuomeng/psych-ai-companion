import { useRef, useState } from "react";

import { useVideoRecorder } from "../hooks/useVideoRecorder";

type CameraRecorderProps = {
  disabled: boolean;
  onRecorded: (file: File) => void;
};

export default function CameraRecorder({ disabled, onRecorded }: CameraRecorderProps) {
  const previewRef = useRef<HTMLVideoElement | null>(null);
  const recorder = useVideoRecorder();
  const [showPreview, setShowPreview] = useState(false);

  async function start() {
    setShowPreview(true);
    await recorder.start(previewRef.current);
  }

  async function stop() {
    const file = await recorder.stop();
    if (file) onRecorded(file);
    setShowPreview(false);
  }

  return (
    <div className="recorder-panel">
      {showPreview && <video muted playsInline ref={previewRef} />}
      {recorder.recording ? (
        <button disabled={disabled} onClick={stop} type="button">
          停止摄像头录制
        </button>
      ) : (
        <button disabled={disabled} onClick={start} type="button">
          摄像头录制
        </button>
      )}
      {recorder.error && <span className="inline-error">{recorder.error}</span>}
    </div>
  );
}
