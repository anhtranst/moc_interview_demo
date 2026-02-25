import logging
import sys

from dotenv import load_dotenv

from livekit.agents import AgentServer, AgentSession, JobContext, JobProcess, cli, metrics
from livekit.agents.voice import MetricsCollectedEvent
from livekit.plugins import google, openai, silero

from .agents import IntroductionAgent
from .config import MAX_COMPLETION_TOKENS
from .data import InterviewData

load_dotenv()
logger = logging.getLogger("mock-interview")

server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    session = AgentSession[InterviewData](
        vad=ctx.proc.userdata["vad"],
        stt=google.STT(),
        llm=openai.LLM(model="gpt-4.1-mini", max_completion_tokens=MAX_COMPLETION_TOKENS),
        tts=google.TTS(model_name="chirp_3"),
        userdata=InterviewData(),
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent) -> None:
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage() -> None:
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=IntroductionAgent(),
        room=ctx.room,
    )


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
