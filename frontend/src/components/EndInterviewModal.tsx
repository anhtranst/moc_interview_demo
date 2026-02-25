import styles from "./EndInterviewModal.module.css";

interface Props {
  open: boolean;
  onConfirmEnd: () => void;
  onCancel: () => void;
}

export function EndInterviewModal({
  open,
  onConfirmEnd,
  onCancel,
}: Props) {
  if (!open) return null;

  return (
    <div className={styles.overlay} onClick={onCancel}>
      <div className={styles.card} onClick={(e) => e.stopPropagation()}>
        <h2 className={styles.title}>End Interview?</h2>
        <p className={styles.message}>
          Are you sure you want to end the interview? This will wrap up the
          session and cannot be undone.
        </p>
        <div className={styles.actions}>
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
