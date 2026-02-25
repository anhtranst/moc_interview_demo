import asyncio
import logging

from livekit.agents import Agent, ChatContext, RunContext
from livekit.agents.llm import function_tool

from .config import INTRODUCTION_FALLBACK_TIMEOUT
from .data import InterviewData

logger = logging.getLogger("mock-interview")

INTRODUCTION_INSTRUCTIONS = (
    "You are a professional interviewer conducting a mock interview. "
    "Your current task is the self-introduction stage. "
    "Greet the candidate warmly and ask them to introduce themselves. "
    "Listen carefully to their introduction. Ask brief clarifying questions "
    "if their introduction is very short. "
    "Once the candidate has provided a reasonable self-introduction "
    "(their name, background, and current role or situation), "
    "call the proceed_to_experience tool to move to the next stage. "
    "Do NOT call the tool prematurely -- wait until the candidate has "
    "finished their introduction."
)

EXPERIENCE_INSTRUCTIONS = (
    "You are a professional interviewer conducting a mock interview. "
    "You are now in the past-experience stage. "
    "The candidate has already introduced themselves. "
    "Ask the candidate about their past work experience, projects, "
    "and achievements. Ask follow-up questions to dig deeper into "
    "specific experiences they mention. "
    "Be conversational and encouraging. "
    "When the candidate has discussed their experience sufficiently "
    "(at least 2-3 exchanges), call the end_interview tool to wrap up."
)


class IntroductionAgent(Agent):
    def __init__(self, *, chat_ctx: ChatContext | None = None) -> None:
        super().__init__(
            instructions=INTRODUCTION_INSTRUCTIONS,
            chat_ctx=chat_ctx,
        )
        self._fallback_task: asyncio.Task[None] | None = None

    async def on_enter(self) -> None:
        self.session.generate_reply()
        self._fallback_task = asyncio.create_task(self._fallback_transition())

    async def on_exit(self) -> None:
        if self._fallback_task is not None and not self._fallback_task.done():
            self._fallback_task.cancel()
            self._fallback_task = None

    async def _fallback_transition(self) -> None:
        """Time-based fallback: if proceed_to_experience is not called
        within the timeout, force-transition to PastExperienceAgent."""
        try:
            await asyncio.sleep(INTRODUCTION_FALLBACK_TIMEOUT)
        except asyncio.CancelledError:
            return

        logger.info("Introduction fallback timer fired -- forcing transition")
        userdata: InterviewData = self.session.userdata
        userdata.transition_source = "fallback"

        next_agent = PastExperienceAgent(chat_ctx=self.chat_ctx)
        self.session.update_agent(next_agent)

    @function_tool
    async def proceed_to_experience(
        self,
        context: RunContext[InterviewData],
        candidate_name: str,
        introduction_summary: str,
    ) -> "PastExperienceAgent":
        """Called when the candidate has finished their self-introduction.

        Args:
            candidate_name: The name of the candidate
            introduction_summary: A brief summary of the candidate's introduction
        """
        context.userdata.candidate_name = candidate_name
        context.userdata.introduction_summary = introduction_summary
        context.userdata.transition_source = "tool"

        logger.info("Transitioning to past-experience stage for %s", candidate_name)

        # Cancel the fallback timer since the tool-based transition is happening
        if self._fallback_task is not None and not self._fallback_task.done():
            self._fallback_task.cancel()
            self._fallback_task = None

        return PastExperienceAgent(chat_ctx=self.chat_ctx)


class PastExperienceAgent(Agent):
    def __init__(self, *, chat_ctx: ChatContext | None = None) -> None:
        super().__init__(
            instructions=EXPERIENCE_INSTRUCTIONS,
            chat_ctx=chat_ctx,
        )

    async def on_enter(self) -> None:
        userdata: InterviewData = self.session.userdata
        name = userdata.candidate_name or "candidate"

        if userdata.transition_source == "fallback":
            self.session.generate_reply(
                instructions=(
                    f"The candidate {name} has been speaking for a while. "
                    "Smoothly transition to asking about their past experience. "
                    "Briefly acknowledge what they have shared so far, then "
                    "ask about their past work experience."
                )
            )
        else:
            self.session.generate_reply(
                instructions=(
                    f"Thank {name} for their introduction and smoothly "
                    "transition to asking about their past work experience. "
                    "Be specific about what interested you from their introduction."
                )
            )

    @function_tool
    async def end_interview(self, context: RunContext[InterviewData]) -> None:
        """Called when the past-experience discussion is complete
        and the interview should wrap up."""
        name = context.userdata.candidate_name or "candidate"
        self.session.interrupt()
        await self.session.generate_reply(
            instructions=f"Thank {name} for their time and end the interview warmly.",
            allow_interruptions=False,
        )
