import { useLocalParticipant } from "@livekit/components-react";
import styles from "./AudioControls.module.css";

export function AudioControls() {
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();

  const toggleMic = () => {
    localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled);
  };

  return (
    <button
      className={`${styles.micBtn} ${isMicrophoneEnabled ? styles.on : styles.off}`}
      onClick={toggleMic}
      title={isMicrophoneEnabled ? "Mute microphone" : "Unmute microphone"}
    >
      {isMicrophoneEnabled ? "Mic On" : "Mic Off"}
    </button>
  );
}
