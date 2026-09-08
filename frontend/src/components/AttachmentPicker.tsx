import type { FileKind } from "../types/api";

type AttachmentPickerProps = {
  disabled: boolean;
  onPick: (files: File[], kind: FileKind) => void;
};

export default function AttachmentPicker({ disabled, onPick }: AttachmentPickerProps) {
  function handleChange(kind: FileKind, files: FileList | null) {
    if (!files) return;
    onPick(Array.from(files), kind);
  }

  return (
    <div className="attachment-picker">
      <label>
        图片
        <input
          accept="image/jpeg,image/png,image/webp"
          disabled={disabled}
          multiple
          onChange={(event) => handleChange("image", event.target.files)}
          type="file"
        />
      </label>
      <label>
        音频
        <input
          accept="audio/*,.webm,.opus,.m4a"
          disabled={disabled}
          multiple
          onChange={(event) => handleChange("audio", event.target.files)}
          type="file"
        />
      </label>
      <label>
        视频
        <input
          accept="video/mp4,video/webm,video/quicktime,.mkv"
          disabled={disabled}
          multiple
          onChange={(event) => handleChange("video", event.target.files)}
          type="file"
        />
      </label>
    </div>
  );
}
