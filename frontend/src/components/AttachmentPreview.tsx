import { previewUrl } from "../api/files";
import type { FileKind, UploadedFile } from "../types/api";
import ProcessingStatus from "./ProcessingStatus";
import UploadProgress from "./UploadProgress";

export type LocalAttachment = {
  id: string;
  kind: FileKind;
  file: File;
  localUrl: string;
  upload?: UploadedFile;
  status: "local" | "uploading" | "uploaded" | "failed";
  progress: number;
  error?: string;
};

type AttachmentPreviewProps = {
  attachment: LocalAttachment;
  sessionId: string;
  onRemove: (id: string) => void;
};

export default function AttachmentPreview({
  attachment,
  sessionId,
  onRemove,
}: AttachmentPreviewProps) {
  const src = attachment.upload
    ? previewUrl(attachment.upload.file_id, sessionId)
    : attachment.localUrl;

  return (
    <article className="attachment-card">
      <div className="attachment-media">
        {attachment.kind === "image" && <img alt={attachment.file.name} src={src} />}
        {attachment.kind === "audio" && <audio controls src={src} />}
        {attachment.kind === "video" && <video controls src={src} />}
      </div>
      <div className="attachment-info">
        <strong>{attachment.file.name}</strong>
        <span>{Math.round(attachment.file.size / 1024)} KB</span>
        <ProcessingStatus status={attachment.status} />
        {attachment.status === "uploading" && (
          <UploadProgress progress={attachment.progress} />
        )}
        {attachment.error && <p className="inline-error">{attachment.error}</p>}
      </div>
      <button onClick={() => onRemove(attachment.id)} type="button">
        删除
      </button>
    </article>
  );
}
