import { useRef, useState } from "react";

export function useVideoRecorder() {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState("");

  async function start(preview: HTMLVideoElement | null) {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
      if (preview) {
        preview.srcObject = stream;
        await preview.play();
      }
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setRecording(true);
    } catch {
      setError("摄像头或麦克风权限被拒绝，无法录制视频。");
    }
  }

  function stop(): Promise<File | null> {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder) {
        resolve(null);
        return;
      }
      recorder.onstop = () => {
        recorder.stream.getTracks().forEach((track) => track.stop());
        setRecording(false);
        const blob = new Blob(chunksRef.current, { type: "video/webm" });
        resolve(new File([blob], `camera-${Date.now()}.webm`, { type: "video/webm" }));
      };
      recorder.stop();
    });
  }

  return { recording, error, start, stop };
}
