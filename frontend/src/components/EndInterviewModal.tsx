import styles from "./EndInterviewModal.module.css";

interface Props {
  open: boolean;
  onPause: () => void;
  onConfirmEnd: () => void;
  onCancel: () => void;
}

export function EndInterviewModal({
  open,
  onPause,
  onConfirmEnd,
  onCancel,
}: Props) {
  if (!open) return null;

  return (
    <div className={styles.overlay} onClick={onCancel}>
      <div className={styles.card} onClick={(e) => e.stopPropagation()}>
        <h2 className={styles.title}>End Interview?</h2>
        <p className={styles.message}>
          If you just need a short break, you can pause the interview and come
          back later. Are you sure you want to end the interview now?
        </p>
        <div className={styles.actions}>
          <button className={styles.pauseBtn} onClick={onPause}>
            Just Pause
          </button>
          <button className={styles.endBtn} onClick={onConfirmEnd}>
            Yes, End Interview
          </button>
          <button className={styles.cancelBtn} onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
