import styles from "./ModeToggle.module.css";

export type InterviewMode = "review" | "live";

interface Props {
  mode: InterviewMode;
  onModeChange: (mode: InterviewMode) => void;
  disabled?: boolean;
}

export function ModeToggle({ mode, onModeChange, disabled }: Props) {
  return (
    <div className={styles.container}>
      <span className={styles.label}>Mode:</span>
      <div className={styles.toggle}>
        <button
          className={`${styles.option} ${mode === "review" ? styles.active : ""}`}
          onClick={() => onModeChange("review")}
          disabled={disabled}
        >
          Review
        </button>
        <button
          className={`${styles.option} ${mode === "live" ? styles.active : ""}`}
          onClick={() => onModeChange("live")}
          disabled={disabled}
        >
          Live
        </button>
      </div>
    </div>
  );
}
