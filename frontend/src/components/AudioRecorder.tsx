import { useAudioRecorder } from "../hooks/useAudioRecorder";

type AudioRecorderProps = {
  disabled: boolean;
  onRecorded: (file: File) => void;
};

export default function AudioRecorder({ disabled, onRecorded }: AudioRecorderProps) {
  const recorder = useAudioRecorder();

  async function handleStop() {
    const file = await recorder.stop();
    if (file) onRecorded(file);
  }

  return (
    <div className="recorder-panel">
      {recorder.recording ? (
        <button disabled={disabled} onClick={handleStop} type="button">
          停止录音 {recorder.seconds}s
        </button>
      ) : (
        <button disabled={disabled} onClick={recorder.start} type="button">
          麦克风录音
        </button>
      )}
      {recorder.error && <span className="inline-error">{recorder.error}</span>}
    </div>
  );
}
