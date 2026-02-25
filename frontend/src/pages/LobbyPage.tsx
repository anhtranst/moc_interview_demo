import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { fetchToken } from "../lib/api";
import styles from "./LobbyPage.module.css";

export function LobbyPage() {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;

    setLoading(true);
    setError("");

    try {
      const { token, livekit_url, room_name } = await fetchToken(name.trim());
      navigate("/interview", {
        state: { token, livekitUrl: livekit_url, roomName: room_name, participantName: name.trim() },
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
          <label className={styles.label} htmlFor="name">
            Your name
          </label>
          <input
            id="name"
            type="text"
            placeholder="Enter your name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
          />

          <button
            type="submit"
            className={styles.startBtn}
            disabled={!name.trim() || loading}
          >
            {loading ? "Connecting..." : "Start Interview"}
          </button>

          {error && <p className={styles.error}>{error}</p>}
        </form>
      </div>
    </div>
  );
}
