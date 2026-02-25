import { useEffect, useRef } from "react";
import type { TranscriptEntry } from "../pages/InterviewPage";
import styles from "./TranscriptPanel.module.css";

interface Props {
  transcripts: TranscriptEntry[];
}

export function TranscriptPanel({ transcripts }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcripts]);

  if (transcripts.length === 0) {
    return (
      <div className={styles.empty}>
        <p>Waiting for the interview to begin...</p>
        <p className={styles.hint}>The interviewer will greet you shortly.</p>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      {transcripts.map((entry) => (
        <div
          key={entry.id}
          className={`${styles.message} ${
            entry.speaker === "agent" ? styles.agent : styles.user
          }`}
        >
          <span className={styles.label}>
            {entry.speaker === "agent" ? "Interviewer" : "You"}
          </span>
          <p className={styles.text}>{entry.text}</p>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
