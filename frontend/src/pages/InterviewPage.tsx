import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useConnectionState,
  useLocalParticipant,
  useRoomContext,
} from "@livekit/components-react";
import {
  ConnectionState,
  RoomEvent,
  type TranscriptionSegment,
  type Participant,
} from "livekit-client";
import { AudioControls } from "../components/AudioControls";
import { TranscriptPanel } from "../components/TranscriptPanel";
import { TextInput } from "../components/TextInput";
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
      audio={true}
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
  const { localParticipant } = useLocalParticipant();
  const [transcripts, setTranscripts] = useState<TranscriptEntry[]>([]);

  // Listen for transcription events from the LiveKit room.
  // The agent pipeline automatically emits these for both user STT and agent TTS.
  const handleTranscription = useCallback(
    (segments: TranscriptionSegment[], participant?: Participant) => {
      const finalSegments = segments.filter((s) => s.final);
      if (!finalSegments.length) return;

      const text = finalSegments.map((s) => s.text).join(" ").trim();
      if (!text) return;

      const isAgent = participant?.identity !== localParticipant.identity;

      setTranscripts((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          speaker: isAgent ? "agent" : "user",
          text,
        },
      ]);
    },
    [localParticipant.identity]
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
        <button className={styles.leaveBtn} onClick={handleLeave}>
          Leave
        </button>
      </header>

      <main className={styles.main}>
        <TranscriptPanel transcripts={transcripts} />
      </main>

      <footer className={styles.footer}>
        <AudioControls />
        <TextInput disabled={!isConnected} />
      </footer>

      <RoomAudioRenderer />
    </div>
  );
}
