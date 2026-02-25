import asyncio
import logging

from livekit.agents import Agent, ChatContext, RunContext, StopResponse
from livekit.agents.llm import ChatMessage, function_tool

from .config import (
    INTRODUCTION_FALLBACK_TIMEOUT,
    PAUSE_KEYWORDS,
    RESUME_KEYWORDS,
    STOP_KEYWORDS,
)
from .data import InterviewData

logger = logging.getLogger("mock-interview")

# Shared conversation rules injected into every agent's instructions.
CONVERSATION_RULES = (
    "\n\nIMPORTANT conversation rules you MUST follow:\n"
    "- Keep each response to 1-3 sentences maximum. Ask only one question at a time.\n"
    "- Speak as a real interviewer would — brief, warm, and conversational.\n"
    "- If the candidate says something vague or incomplete, ask them to elaborate "
    "rather than treating it as a full answer.\n"
    "- If the candidate asks you to repeat something, slow down, or makes any "
    "non-interview request, respond to that request naturally before continuing.\n"
    "- Never produce long paragraphs or multiple questions in a single response."
)

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
) + CONVERSATION_RULES

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
) + CONVERSATION_RULES


def _matches_keywords(text: str, keywords: set[str]) -> bool:
    """Check if normalized text matches any keyword (case-insensitive substring)."""
    normalized = text.strip().lower()
    return any(kw in normalized for kw in keywords)


class InterviewAgentBase(Agent):
    """Base class for all interview agents with shared flow-control logic.

    Handles deterministic command detection (stop/pause/resume) in
    ``on_user_turn_completed`` before the LLM sees the message.
    """

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        text = new_message.text_content or ""
        userdata: InterviewData = self.session.userdata

        # --- Resume from pause ---
        if userdata.is_paused:
            if _matches_keywords(text, RESUME_KEYWORDS):
                userdata.is_paused = False
                logger.info("Interview resumed by user")
                self.session.generate_reply(
                    instructions="The candidate is ready to continue. "
                    "Pick up where you left off with a brief acknowledgment."
                )
            # While paused, suppress all LLM responses.
            raise StopResponse()

        # --- Hard stop ---
        if _matches_keywords(text, STOP_KEYWORDS):
            logger.info("User requested to stop the interview")
            name = userdata.candidate_name or "candidate"
            self.session.generate_reply(
                instructions=f"The candidate has asked to stop. "
                f"Thank {name} for their time and end the interview warmly.",
                allow_interruptions=False,
            )
            raise StopResponse()

        # --- Pause ---
        if _matches_keywords(text, PAUSE_KEYWORDS):
            userdata.is_paused = True
            logger.info("Interview paused by user")
            self.session.generate_reply(
                instructions="The candidate needs a moment. "
                "Acknowledge briefly and let them know you'll wait."
            )
            raise StopResponse()


class IntroductionAgent(InterviewAgentBase):
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

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        await super().on_user_turn_completed(turn_ctx, new_message)


class PastExperienceAgent(InterviewAgentBase):
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

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        await super().on_user_turn_completed(turn_ctx, new_message)
