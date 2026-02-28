import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from livekit.agents import (
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    cli,
    metrics,
)
from livekit.agents.voice import ConversationItemAddedEvent, MetricsCollectedEvent
from livekit.plugins import google, openai

from .agents import IntroductionAgent
from .config import MAX_COMPLETION_TOKENS, MAX_ENDPOINTING_DELAY, MIN_ENDPOINTING_DELAY
from .cv_loader import extract_cv_metadata, load_cv_text
from .data import InterviewData

load_dotenv()
logger = logging.getLogger("mock-interview")

server = AgentServer()

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def prewarm(proc: JobProcess) -> None:
    pass


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    # Extract interview code from room name.
    # Format: "interview--{code}--{uuid}" (double-dash separators).
    room_name = ctx.room.name or ""
    interview_code = None
    if room_name.startswith("interview--"):
        parts = room_name.split("--")
        if len(parts) >= 2:
            interview_code = parts[1]

    # Load CV and extract metadata (name + STT keywords) before session starts.
    llm = openai.LLM(model="gpt-4.1-mini", max_completion_tokens=MAX_COMPLETION_TOKENS)
    cv_text: str | None = None
    candidate_name: str | None = None
    stt_keywords: list[tuple[str, float]] = []

    if interview_code:
        cv_text = load_cv_text(interview_code)
        if cv_text:
            # Use a separate LLM instance with higher token limit for structured
            # JSON extraction (the conversation LLM is capped at 150 tokens).
            extraction_llm = openai.LLM(model="gpt-4.1-mini", max_completion_tokens=1024)
            metadata = await extract_cv_metadata(cv_text, extraction_llm)
            candidate_name = metadata.candidate_name
            stt_keywords = metadata.keywords

    userdata = InterviewData(
        interview_code=interview_code,
        started_at=time.time(),
        candidate_name=candidate_name,
        cv_text=cv_text,
        stt_keywords=stt_keywords,
    )

    session = AgentSession[InterviewData](
        llm=llm,
        stt=google.STT(
            languages="en-US",
            detect_language=True,
            interim_results=True,
            model="latest_long",
            enable_voice_activity_events=True,
            keywords=stt_keywords or [],
        ),
        tts=google.TTS(model_name="chirp_3"),
        userdata=userdata,
        turn_detection="stt",
        min_endpointing_delay=MIN_ENDPOINTING_DELAY,
        max_endpointing_delay=MAX_ENDPOINTING_DELAY,
        discard_audio_if_uninterruptible=False,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent) -> None:
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    @session.on("conversation_item_added")
    def _on_message(ev: ConversationItemAddedEvent) -> None:
        msg = ev.item
        if hasattr(msg, "role") and hasattr(msg, "text_content"):
            text = msg.text_content or ""
            if text:
                label = "INTERVIEWER" if msg.role == "assistant" else msg.role.upper()
                logger.info("[%s] %s", label, text)

    async def on_shutdown() -> None:
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")
        _save_transcript(session)

    ctx.add_shutdown_callback(on_shutdown)

    await session.start(
        agent=IntroductionAgent(cv_text=cv_text, candidate_name=candidate_name),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            text_enabled=True,
            audio_enabled=True,
        ),
    )


def _save_transcript(session: AgentSession[InterviewData]) -> None:
    """Persist the conversation transcript to disk as JSON."""
    ud = session.userdata
    if not ud or not ud.interview_code:
        logger.warning("No interview code — skipping transcript save")
        return

    transcript_dir = _DATA_DIR / ud.interview_code / "transcripts"
    if not transcript_dir.is_dir():
        logger.warning("Transcript directory does not exist: %s", transcript_dir)
        return

    now = time.time()
    messages = []
    for msg in session.history.messages():
        text = msg.text_content
        if not text:
            continue
        messages.append({
            "role": msg.role,
            "text": text,
            "timestamp": msg.created_at,
        })

    started_iso = (
        datetime.fromtimestamp(ud.started_at, tz=timezone.utc).isoformat()
        if ud.started_at
        else None
    )
    ended_iso = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()

    transcript = {
        "interview_code": ud.interview_code,
        "candidate_name": ud.candidate_name,
        "started_at": started_iso,
        "ended_at": ended_iso,
        "messages": messages,
    }

    ts_str = datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    filepath = transcript_dir / f"{ts_str}.json"

    try:
        filepath.write_text(json.dumps(transcript, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Transcript saved to %s", filepath)
    except OSError:
        logger.exception("Failed to save transcript to %s", filepath)


def _run_serve() -> None:
    """Start the FastAPI token server with uvicorn."""
    import uvicorn

    print("Starting token server on http://localhost:8000")
    print("  POST /api/token — generate LiveKit room token")
    print("  Frontend served from frontend/dist/ (if built)")
    uvicorn.run("src.server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        _run_serve()
    else:
        cli.run_app(server)
