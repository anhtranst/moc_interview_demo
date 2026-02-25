import { useCallback, useEffect, useRef, useState } from "react";
import styles from "./RecordingControls.module.css";

type RecordingState = "idle" | "recording" | "paused";

export interface RecordingControlsHandle {
  reset: () => void;
  pause: () => void;
}

interface Props {
  onTranscript: (text: string) => void;
  draftText: string;
  controlRef: React.MutableRefObject<RecordingControlsHandle | null>;
  disabled?: boolean;
}

// Extend Window for vendor-prefixed SpeechRecognition
interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionInstance;

interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: Event & { error: string }) => void) | null;
  onend: (() => void) | null;
}

function getSpeechRecognitionCtor(): SpeechRecognitionCtor | null {
  const w = window as unknown as Record<string, unknown>;
  return (w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null) as SpeechRecognitionCtor | null;
}

export function RecordingControls({ onTranscript, draftText, controlRef, disabled }: Props) {
  const [state, setState] = useState<RecordingState>("idle");
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const accumulatedRef = useRef("");
  const stateRef = useRef(state);
  stateRef.current = state;

  const supported = !!getSpeechRecognitionCtor();

  const stopRecognition = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.onend = null;
      recognitionRef.current.abort();
      recognitionRef.current = null;
    }
  }, []);

  const startRecognition = useCallback(() => {
    stopRecognition();

    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) return;

    const recognition = new Ctor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalText = accumulatedRef.current;
      let interimText = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          const sentence = result[0].transcript.trim();
          if (sentence) {
            finalText = finalText ? finalText + " " + sentence : sentence;
          }
        } else {
          interimText += result[0].transcript;
        }
      }

      accumulatedRef.current = finalText;
      const display = interimText
        ? finalText + (finalText ? " " : "") + interimText
        : finalText;
      onTranscript(display);
    };

    recognition.onerror = (event) => {
      // "aborted" fires when we call .abort() intentionally
      if (event.error !== "aborted") {
        console.warn("SpeechRecognition error:", event.error);
      }
    };

    recognition.onend = () => {
      // Auto-restart if we're still in "recording" state (browser may stop on silence)
      if (stateRef.current === "recording") {
        try {
          recognition.start();
        } catch {
          // Ignore if already started
        }
      }
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, [stopRecognition, onTranscript]);

  // Clean up on unmount
  useEffect(() => {
    return () => stopRecognition();
  }, [stopRecognition]);

  const handleStart = () => {
    accumulatedRef.current = "";
    setState("recording");
    startRecognition();
  };

  const handlePause = () => {
    setState("paused");
    stopRecognition();
  };

  const handleResume = () => {
    // Sync accumulated text with whatever the user edited in the textbox
    accumulatedRef.current = draftText;
    setState("recording");
    startRecognition();
  };

  /** Called by parent after text is sent to reset the controls. */
  const reset = useCallback(() => {
    stopRecognition();
    accumulatedRef.current = "";
    setState("idle");
  }, [stopRecognition]);

  // Expose controls to parent via ref
  useEffect(() => {
    controlRef.current = { reset, pause: handlePause };
    return () => {
      controlRef.current = null;
    };
  }, [reset, controlRef]);

  if (!supported) {
    return (
      <span className={styles.unsupported}>
        Speech recognition not supported in this browser
      </span>
    );
  }

  if (state === "idle") {
    return (
      <button
        className={`${styles.btn} ${styles.start}`}
        onClick={handleStart}
        disabled={disabled}
      >
        Start Recording
      </button>
    );
  }

  if (state === "recording") {
    return (
      <button
        className={`${styles.btn} ${styles.pause}`}
        onClick={handlePause}
      >
        Pause
      </button>
    );
  }

  // paused
  return (
    <button
      className={`${styles.btn} ${styles.resume}`}
      onClick={handleResume}
    >
      Resume
    </button>
  );
}
