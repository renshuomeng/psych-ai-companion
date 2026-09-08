import { FormEvent, useState } from "react";

type ChatBoxProps = {
  disabled: boolean;
  onSend: (message: string) => void;
};

export default function ChatBox({ disabled, onSend }: ChatBoxProps) {
  const [message, setMessage] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) return;

    onSend(trimmed);
    setMessage("");
  }

  return (
    <form className="chat-box" onSubmit={handleSubmit}>
      <label htmlFor="message">输入你想说的话</label>
      <textarea
        disabled={disabled}
        id="message"
        onChange={(event) => setMessage(event.target.value)}
        placeholder="例如：最近论文和就业压力很大，晚上也睡不着。"
        rows={5}
        value={message}
      />
      <div className="chat-actions">
        <button
          disabled={disabled}
          onClick={() => setMessage("最近论文和就业压力很大，晚上也睡不着。")}
          type="button"
        >
          普通示例
        </button>
        <button
          disabled={disabled}
          onClick={() => setMessage("我不想活了，感觉一切都没有意义。")}
          type="button"
        >
          高危示例
        </button>
        <button className="primary-button" disabled={disabled} type="submit">
          {disabled ? "发送中..." : "发送"}
        </button>
      </div>
    </form>
  );
}
