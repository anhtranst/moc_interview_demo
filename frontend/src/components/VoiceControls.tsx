import { useCallback, useEffect, useState } from "react";
import { useRoomContext } from "@livekit/components-react";
import styles from "./VoiceControls.module.css";

interface Props {
  disabled?: boolean;
}

export function VoiceControls({ disabled }: Props) {
  const room = useRoomContext();
  const [micEnabled, setMicEnabled] = useState(false);
  const [pending, setPending] = useState(false);

  // Enable mic on mount, disable on unmount
  useEffect(() => {
    if (disabled) return;

    let cancelled = false;
    setPending(true);

    room.localParticipant
      .setMicrophoneEnabled(true)
      .then(() => {
        if (!cancelled) {
          setMicEnabled(true);
          setPending(false);
        }
      })
      .catch(() => {
        if (!cancelled) setPending(false);
      });

    return () => {
      cancelled = true;
      room.localParticipant.setMicrophoneEnabled(false).catch(() => {});
      setMicEnabled(false);
    };
  }, [room, disabled]);

  const toggleMic = useCallback(async () => {
    if (pending) return;
    setPending(true);
    try {
      const next = !micEnabled;
      await room.localParticipant.setMicrophoneEnabled(next);
      setMicEnabled(next);
    } finally {
      setPending(false);
    }
  }, [room, micEnabled, pending]);

  return (
    <div className={styles.container}>
      <div className={styles.indicator}>
        {micEnabled ? (
          <>
            <span className={styles.dot} />
            <span className={styles.statusText}>Listening...</span>
          </>
        ) : (
          <span className={styles.statusText}>Microphone muted</span>
        )}
      </div>
      <button
        className={`${styles.micBtn} ${micEnabled ? styles.micOn : styles.micOff}`}
        onClick={toggleMic}
        disabled={disabled || pending}
      >
        {pending ? "..." : micEnabled ? "Mute" : "Unmute"}
      </button>
      <span className={styles.hint}>
        Speak naturally — the agent will respond when you pause.
      </span>
    </div>
  );
}
