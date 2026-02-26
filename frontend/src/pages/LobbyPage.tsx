import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { fetchToken } from "../lib/api";
import styles from "./LobbyPage.module.css";

export function LobbyPage() {
  const [interviewCode, setInterviewCode] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!interviewCode.trim() || !name.trim()) return;

    setLoading(true);
    setError("");

    try {
      const resp = await fetchToken(name.trim(), interviewCode.trim());
      navigate("/interview", {
        state: {
          token: resp.token,
          livekitUrl: resp.livekit_url,
          roomName: resp.room_name,
          participantName: name.trim(),
          interviewCode: resp.interview_code,
        },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <h1 className={styles.title}>Mock Interview</h1>
        <p className={styles.subtitle}>
          Practice your interview skills with an AI interviewer
        </p>

        <form onSubmit={handleSubmit} className={styles.form}>
          <label className={styles.label} htmlFor="interviewCode">
            Interview code
          </label>
          <input
            id="interviewCode"
            type="text"
            placeholder="Enter your interview code"
            value={interviewCode}
            onChange={(e) => setInterviewCode(e.target.value)}
            autoFocus
          />

          <label className={styles.label} htmlFor="name">
            Your name
          </label>
          <input
            id="name"
            type="text"
            placeholder="Enter your name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />

          <button
            type="submit"
            className={styles.startBtn}
            disabled={!interviewCode.trim() || !name.trim() || loading}
          >
            {loading ? "Connecting..." : "Start Interview"}
          </button>

          {error && <p className={styles.error}>{error}</p>}
        </form>
      </div>
    </div>
  );
}
