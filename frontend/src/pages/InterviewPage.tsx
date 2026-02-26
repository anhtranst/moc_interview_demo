import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useConnectionState,
  useRoomContext,
} from "@livekit/components-react";
import {
  ConnectionState,
  RoomEvent,
  type TranscriptionSegment,
  type Participant,
} from "livekit-client";
import {
  RecordingControls,
  type RecordingControlsHandle,
} from "../components/RecordingControls";
import { TranscriptPanel } from "../components/TranscriptPanel";
import { TextInput } from "../components/TextInput";
import { EndInterviewModal } from "../components/EndInterviewModal";
import { ModeToggle, type InterviewMode } from "../components/ModeToggle";
import { VoiceControls } from "../components/VoiceControls";
import styles from "./InterviewPage.module.css";

interface LocationState {
  token: string;
  livekitUrl: string;
  roomName: string;
  participantName: string;
  interviewCode: string;
}

export interface TranscriptEntry {
  id: string;
  speaker: "agent" | "user";
  text: string;
}

// Skip LLM function-call text that leaks into the transcription stream.
const FUNCTION_CALL_RE = /^\s*functions\.\w+\s*\(.*\)\s*$/;

export function InterviewPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as LocationState | null;

  if (!state) {
    navigate("/");
    return null;
  }

  return (
    <LiveKitRoom
      serverUrl={state.livekitUrl}
      token={state.token}
      connect={true}
      audio={false}
      className={styles.room}
    >
      <InterviewRoom />
    </LiveKitRoom>
  );
}

function InterviewRoom() {
  const navigate = useNavigate();
  const room = useRoomContext();
  const connectionState = useConnectionState();
  const [transcripts, setTranscripts] = useState<TranscriptEntry[]>([]);
  const [draftText, setDraftText] = useState("");
  const [showEndModal, setShowEndModal] = useState(false);
  const [mode, setMode] = useState<InterviewMode>("review");
  const recordingControlRef = useRef<RecordingControlsHandle | null>(null);

  // Track seen segment IDs to deduplicate transcript entries.
  const seenSegmentIds = useRef(new Set<string>());

  const handleTranscription = useCallback(
    (segments: TranscriptionSegment[], participant?: Participant) => {
      for (const seg of segments) {
        // Skip segments that have already been finalized.
        if (seenSegmentIds.current.has(seg.id)) continue;

        const text = seg.text.trim();
        if (!text) continue;

        // Filter out raw function-call representations (e.g. "functions.end_interview()")
        if (FUNCTION_CALL_RE.test(text)) {
          if (seg.final) seenSegmentIds.current.add(seg.id);
          continue;
        }

        if (seg.final) {
          seenSegmentIds.current.add(seg.id);
        }

        const isAgent = participant?.isAgent ?? false;
        const entry: TranscriptEntry = {
          id: seg.id,
          speaker: isAgent ? "agent" : "user",
          text,
        };

        // Upsert: update existing entry in-place, or append new.
        setTranscripts((prev) => {
          const idx = prev.findIndex((t) => t.id === seg.id);
          if (idx >= 0) {
            const updated = [...prev];
            updated[idx] = entry;
            return updated;
          }
          return [...prev, entry];
        });
      }
    },
    []
  );

  useEffect(() => {
    room.on(RoomEvent.TranscriptionReceived, handleTranscription);
    return () => {
      room.off(RoomEvent.TranscriptionReceived, handleTranscription);
    };
  }, [room, handleTranscription]);

  const handleLeave = () => {
    navigate("/");
  };

  // Called after TextInput successfully sends a message.
  const handleSent = useCallback((text: string) => {
    setTranscripts((prev) => [
      ...prev,
      { id: crypto.randomUUID(), speaker: "user", text },
    ]);
    setDraftText("");
    recordingControlRef.current?.reset();
  }, []);

  // When user manually types/edits in the textbox, auto-pause recording.
  const handleDraftChange = useCallback((text: string) => {
    setDraftText(text);
    recordingControlRef.current?.pause();
  }, []);

  // --- End Interview confirmation flow ---
  const handleEndInterviewClick = useCallback(() => {
    setShowEndModal(true);
  }, []);

  const handleConfirmEnd = useCallback(async () => {
    setShowEndModal(false);
    try {
      await room.localParticipant.sendText("end interview", {
        topic: "lk.chat",
      });
    } catch {
      // ignore
    }
  }, [room]);

  const isConnected = connectionState === ConnectionState.Connected;

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Mock Interview</h1>
          <span className={styles.status}>
            {isConnected ? "Connected" : connectionState}
          </span>
        </div>
        <ModeToggle
          mode={mode}
          onModeChange={setMode}
          disabled={!isConnected}
        />
        <div className={styles.headerActions}>
          <button
            className={styles.endInterviewBtn}
            onClick={handleEndInterviewClick}
            disabled={!isConnected}
          >
            End Interview
          </button>
          <button className={styles.leaveBtn} onClick={handleLeave}>
            Leave
          </button>
        </div>
      </header>

      <main className={styles.main}>
        <TranscriptPanel transcripts={transcripts} />
      </main>

      <footer className={styles.footer}>
        {mode === "review" ? (
          <>
            <RecordingControls
              onTranscript={setDraftText}
              draftText={draftText}
              controlRef={recordingControlRef}
              disabled={!isConnected}
            />
            <TextInput
              disabled={!isConnected}
              draftText={draftText}
              onDraftChange={handleDraftChange}
              onSent={handleSent}
            />
          </>
        ) : (
          <VoiceControls disabled={!isConnected} />
        )}
      </footer>

      <RoomAudioRenderer />

      <EndInterviewModal
        open={showEndModal}
        onConfirmEnd={handleConfirmEnd}
        onCancel={() => setShowEndModal(false)}
      />
    </div>
  );
}
