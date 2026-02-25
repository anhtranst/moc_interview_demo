import { useState, type FormEvent } from "react";
import { useRoomContext } from "@livekit/components-react";
import styles from "./TextInput.module.css";

interface Props {
  disabled: boolean;
}

export function TextInput({ disabled }: Props) {
  const [text, setText] = useState("");
  const room = useRoomContext();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled) return;

    // Send text as a data message so the agent receives it as user input.
    const encoder = new TextEncoder();
    const data = encoder.encode(
      JSON.stringify({ type: "user_text", text: trimmed })
    );
    await room.localParticipant.publishData(data, { reliable: true });
    setText("");
  }

  return (
    <form onSubmit={handleSubmit} className={styles.form}>
      <input
        className={styles.input}
        type="text"
        placeholder="Type a message (text fallback)..."
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled}
      />
      <button
        type="submit"
        className={styles.sendBtn}
        disabled={disabled || !text.trim()}
      >
        Send
      </button>
    </form>
  );
}
