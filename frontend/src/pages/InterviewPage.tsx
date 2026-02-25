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
import styles from "./InterviewPage.module.css";

interface LocationState {
  token: string;
  livekitUrl: string;
  roomName: string;
  participantName: string;
}

export interface TranscriptEntry {
  id: string;
  speaker: "agent" | "user";
  text: string;
}

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
  const recordingControlRef = useRef<RecordingControlsHandle | null>(null);

  // Track seen segment IDs to deduplicate transcript entries.
  const seenSegmentIds = useRef(new Set<string>());

  const handleTranscription = useCallback(
    (segments: TranscriptionSegment[], participant?: Participant) => {
      const newEntries: TranscriptEntry[] = [];

      for (const seg of segments) {
        if (!seg.final) continue;
        if (seenSegmentIds.current.has(seg.id)) continue;
        seenSegmentIds.current.add(seg.id);

        const text = seg.text.trim();
        if (!text) continue;

        const isAgent = participant?.isAgent ?? false;
        newEntries.push({
          id: seg.id,
          speaker: isAgent ? "agent" : "user",
          text,
        });
      }

      if (newEntries.length > 0) {
        setTranscripts((prev) => [...prev, ...newEntries]);
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
  const handleEndInterviewClick = useCallback(async () => {
    // Send a message so the agent speaks a warning via TTS
    try {
      await room.localParticipant.sendText(
        "I'd like to end the interview",
        { topic: "lk.chat" }
      );
    } catch {
      // Room might not be connected; still show the modal
    }
    setShowEndModal(true);
  }, [room]);

  const handlePause = useCallback(async () => {
    setShowEndModal(false);
    try {
      await room.localParticipant.sendText("pause", { topic: "lk.chat" });
    } catch {
      // ignore
    }
  }, [room]);

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
      </footer>

      <RoomAudioRenderer />

      <EndInterviewModal
        open={showEndModal}
        onPause={handlePause}
        onConfirmEnd={handleConfirmEnd}
        onCancel={() => setShowEndModal(false)}
      />
    </div>
  );
}
