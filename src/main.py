import logging

from dotenv import load_dotenv

from livekit.agents import AgentServer, AgentSession, JobContext, JobProcess, cli, metrics
from livekit.agents.voice import MetricsCollectedEvent
from livekit.plugins import google, openai, silero

from .agents import IntroductionAgent
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
        llm=openai.LLM(model="gpt-4.1-mini"),
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


if __name__ == "__main__":
    cli.run_app(server)
