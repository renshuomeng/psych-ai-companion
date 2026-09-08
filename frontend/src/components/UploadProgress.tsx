type UploadProgressProps = {
  progress: number;
};

export default function UploadProgress({ progress }: UploadProgressProps) {
  return (
    <div className="upload-progress" aria-label="上传进度">
      <span style={{ width: `${progress}%` }} />
      <strong>{progress}%</strong>
    </div>
  );
}
