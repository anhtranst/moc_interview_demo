import asyncio
import logging

from livekit.agents import Agent, ChatContext, RunContext, StopResponse
from livekit.agents.llm import ChatMessage, function_tool

from .config import INTRODUCTION_FALLBACK_TIMEOUT
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
    "Gather the candidate's background ONE detail at a time, in this order:\n"
    "1. First, greet the candidate warmly and ask for their name.\n"
    "2. Once you know their name, ask about their current role or situation.\n"
    "3. Once you know their role, ask about their background or education.\n"
    "Ask only ONE question per turn. Do NOT combine multiple questions. "
    "If the candidate gives a vague or incomplete answer, "
    "ask a brief follow-up to clarify before moving to the next topic.\n"
    "Once you have gathered all three details (name, current role, and background), "
    "call the proceed_to_experience tool to move to the next stage. "
    "Do NOT call the tool prematurely -- wait until you have all three details."
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


# Exact text sent by the frontend End Interview button after user confirms.
_END_INTERVIEW_TEXT = "end interview"


class InterviewAgentBase(Agent):
    """Base class for all interview agents with shared conversation rules.

    Handles the deterministic "end interview" command sent by the frontend
    End Interview button in ``on_user_turn_completed``.
    """

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        text = (new_message.text_content or "").strip().lower()

        if text == _END_INTERVIEW_TEXT:
            logger.info("User ended the interview via button")
            userdata: InterviewData = self.session.userdata
            name = userdata.candidate_name or "candidate"
            self.session.generate_reply(
                instructions=f"The candidate has decided to end the interview. "
                f"Thank {name} for their time and end the interview warmly.",
                allow_interruptions=False,
            )
            self.session.shutdown(drain=True)
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
        within the timeout, generate a bridging message and transition
        to PastExperienceAgent."""
        try:
            await asyncio.sleep(INTRODUCTION_FALLBACK_TIMEOUT)
        except asyncio.CancelledError:
            return

        logger.info("Introduction fallback timer fired -- bridging to next stage")
        userdata: InterviewData = self.session.userdata
        userdata.transition_source = "fallback"

        # Generate a bridging message and wait for it to fully play out
        # before switching agents, so the transition feels natural.
        name = userdata.candidate_name or "there"
        try:
            await self.session.generate_reply(
                instructions=(
                    f"Thank {name} for what they have shared so far and let them know "
                    "you'd like to move on to discuss their work experience in more detail. "
                    "Keep it to one brief sentence."
                ),
                allow_interruptions=False,
            )
        except asyncio.CancelledError:
            return  # Tool-based transition took over; abort fallback

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
                    f"The candidate {name} has already been told you're moving on to "
                    "discuss their work experience. Ask a specific question about their "
                    "past work experience or most recent role. Do NOT repeat that you're "
                    "transitioning -- just ask the question directly."
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
        self.session.generate_reply(
            instructions=f"Thank {name} for their time and end the interview warmly.",
            allow_interruptions=False,
        )
        self.session.shutdown(drain=True)
        raise StopResponse()

