import { type FormEvent } from "react";
import { useRoomContext } from "@livekit/components-react";
import styles from "./TextInput.module.css";

interface Props {
  disabled: boolean;
  draftText: string;
  onDraftChange: (text: string) => void;
  onSent: (text: string) => void;
}

export function TextInput({ disabled, draftText, onDraftChange, onSent }: Props) {
  const room = useRoomContext();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = draftText.trim();
    if (!trimmed || disabled) return;

    // Send text via LiveKit text stream so the agent receives it as user input.
    await room.localParticipant.sendText(trimmed, { topic: "lk.chat" });
    onSent(trimmed);
  }

  return (
    <form onSubmit={handleSubmit} className={styles.form}>
      <input
        className={styles.input}
        type="text"
        placeholder="Type a message or use the mic to record..."
        value={draftText}
        onChange={(e) => onDraftChange(e.target.value)}
        disabled={disabled}
      />
      <button
        type="submit"
        className={styles.sendBtn}
        disabled={disabled || !draftText.trim()}
      >
        Send
      </button>
    </form>
  );
}
