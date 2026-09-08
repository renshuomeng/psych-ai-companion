type TranscriptCardProps = {
  text: string;
  onChange?: (value: string) => void;
};

export default function TranscriptCard({ text, onChange }: TranscriptCardProps) {
  return (
    <section className="result-card">
      <h3>语音转写</h3>
      {onChange ? (
        <textarea
          onChange={(event) => onChange(event.target.value)}
          placeholder="语音转写结果会显示在这里，发送前可以手动修正。"
          rows={5}
          value={text}
        />
      ) : (
        <p>{text || "尚无语音转写结果。"}</p>
      )}
    </section>
  );
}
