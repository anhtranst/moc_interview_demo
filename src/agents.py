import asyncio
import logging

from livekit.agents import Agent, ChatContext, RunContext, StopResponse
from livekit.agents.llm import ChatMessage, function_tool

from .config import (
    EXPERIENCE_CLOSING_THRESHOLD,
    EXPERIENCE_STAGE_TIMEOUT,
    INTRODUCTION_FALLBACK_TIMEOUT,
    MAX_EXPERIENCE_TOPICS,
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

# ---------------------------------------------------------------------------
# Static fallback instructions (used when no CV is available)
# ---------------------------------------------------------------------------

_INTRO_NO_CV = (
    "You are a professional interviewer conducting a mock interview. "
    "Your current task is the self-introduction stage. "
    "Gather the candidate's background ONE detail at a time, in this order:\n"
    "1. First, greet the candidate warmly with their name.\n"
    "2. Then, ask about their current role or situation.\n"
    "3. Once you know their role, ask about their background or education.\n"
    "Ask only ONE question per turn. Do NOT combine multiple questions. "
    "If the candidate gives a vague or incomplete answer, "
    "ask a brief follow-up to clarify before moving to the next topic.\n"
    "Once you have gathered all three details (name, current role, and background), "
    "call the proceed_to_experience tool to move to the next stage. "
    "Do NOT call the tool prematurely -- wait until you have all three details. "
    "When calling the tool, do NOT say anything. The next stage will ask the questions."
)

_EXPERIENCE_NO_CV = (
    "You are a professional interviewer conducting a mock interview. "
    "You are now in the past-experience stage. "
    "The candidate has already introduced themselves.\n\n"
    "Ask the candidate about their past work experience, projects, "
    "and professional achievements ONE topic at a time. "
    "Do NOT ask about education, degrees, certifications, or skills — "
    "focus ONLY on jobs, roles, and projects.\n\n"
    "For each experience topic:\n"
    "1. Ask an initial question about the role or project\n"
    "2. Ask 1-2 follow-up questions to dig deeper into their contributions, "
    "challenges, and impact\n"
    "3. When you have finished all follow-up questions and are satisfied with"
    "4. Move on to the next topic\n\n"
    "After you have covered enough topics (the record_experience tool will "
    "tell you when), ask the candidate if there is any other meaningful "
    "experience they would like to share.\n\n"
    "5. After the candidate has finished sharing additional experience, or says they have no more to share, then call "
    "end_interview.\n\n"    
)


# ---------------------------------------------------------------------------
# Dynamic instruction builders (CV-aware)
# ---------------------------------------------------------------------------


def build_introduction_instructions(
    cv_text: str | None, candidate_name: str | None
) -> str:
    """Build introduction-stage instructions, personalised with CV data."""
    if cv_text and candidate_name:
        return (
            "You are a professional interviewer conducting a mock interview. "
            f"You have already reviewed the candidate's CV. The candidate's name is {candidate_name}.\n\n"
            "Your current task is the self-introduction stage. "
            f"Greet {candidate_name} warmly by name — you already know who they are. "
            "Do NOT ask for their name again.\n"
            "Ask about their current role or situation, then about their background or education. "
            "Ask only ONE question per turn. Do NOT combine multiple questions. "
            "If the candidate gives a vague or incomplete answer, "
            "ask a brief follow-up to clarify before moving to the next topic.\n"
            "Once you have discussed their current role and background, "
            "call the proceed_to_experience tool to move to the next stage. "
            "When calling the tool, do NOT say anything. The next stage will ask the questions.\n\n"
            f"Here is the candidate's CV for reference:\n\n{cv_text}"
        ) + CONVERSATION_RULES
    return _INTRO_NO_CV + CONVERSATION_RULES


def build_experience_instructions(
    cv_text: str | None, candidate_name: str | None
) -> str:
    """Build experience-stage instructions, personalised with CV data."""
    if cv_text:
        name = candidate_name or "the candidate"
        return (
            "You are a professional interviewer conducting a mock interview. "
            "You are now in the past-experience stage. "
            f"{name} has already introduced themselves.\n\n"
            "You have the candidate's CV below. Identify their distinct work experiences "
            "and roles — ignore education, degrees, certifications, and skills sections. "
            "Select up to the most relevant or interesting ones to ask about.\n\n"
            "For each experience topic:\n"
            "1. Ask an initial question about the role or project\n"
            "2. Ask 1-2 follow-up questions to dig deeper into their contributions, "
            "challenges, and impact\n"
            "3. When you have finished all follow-up questions and are satisfied with"
            "4. Move on to the next topic\n\n"
            "After you have covered enough topics (the record_experience tool will "
            "tell you when), ask the candidate if there is any other meaningful "
            "experience they would like to share.\n\n"
            "5. After the candidate has finished sharing additional experience, or says they have no more to share, then call "
            "end_interview.\n\n"            
            f"Candidate's CV:\n\n{cv_text}"
        ) + CONVERSATION_RULES
    return _EXPERIENCE_NO_CV + CONVERSATION_RULES


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
            self._instructions = ""
            self.session.generate_reply(
                instructions=(
                    f"The candidate has chosen to end the interview. "
                    f"Generate a warm, brief goodbye. Thank {name} for their time "
                    "and wish them well. "
                    "Respond in 1-2 sentences only. Do not repeat these instructions."
                ),
                allow_interruptions=False,
                tool_choice="none",
            )
            self.session.shutdown(drain=True)
            raise StopResponse()


class IntroductionAgent(InterviewAgentBase):
    def __init__(
        self,
        *,
        chat_ctx: ChatContext | None = None,
        cv_text: str | None = None,
        candidate_name: str | None = None,
    ) -> None:
        super().__init__(
            instructions=build_introduction_instructions(cv_text, candidate_name),
            chat_ctx=chat_ctx,
        )
        self._cv_text = cv_text
        self._candidate_name = candidate_name
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
        within the timeout, transition to PastExperienceAgent directly.
        The experience agent's on_enter handles the bridging message."""
        try:
            await asyncio.sleep(INTRODUCTION_FALLBACK_TIMEOUT)
        except asyncio.CancelledError:
            return

        logger.info("Introduction fallback timer fired — transitioning to experience stage")
        userdata: InterviewData = self.session.userdata
        userdata.transition_source = "fallback"

        next_agent = PastExperienceAgent(
            chat_ctx=self.chat_ctx,
            cv_text=self._cv_text,
            candidate_name=userdata.candidate_name,
        )
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

        return PastExperienceAgent(
            chat_ctx=self.chat_ctx,
            cv_text=self._cv_text,
            candidate_name=candidate_name,
        )


class PastExperienceAgent(InterviewAgentBase):
    def __init__(
        self,
        *,
        chat_ctx: ChatContext | None = None,
        cv_text: str | None = None,
        candidate_name: str | None = None,
    ) -> None:
        super().__init__(
            instructions=build_experience_instructions(cv_text, candidate_name),
            chat_ctx=chat_ctx,
        )
        self._initial_instructions = self._instructions
        self._wrap_up_task: asyncio.Task[None] | None = None
        self._farewell_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def on_enter(self) -> None:
        self._wrap_up_task = asyncio.create_task(self._wrap_up_timer())
        self._farewell_task = asyncio.create_task(self._farewell_timer())

        userdata: InterviewData = self.session.userdata
        name = userdata.candidate_name or "candidate"

        if userdata.transition_source == "fallback":
            logger.info("Experience stage entered via fallback for %s", name)
            self.session.generate_reply(
                instructions=(
                    f"Smoothly transition to discussing {name}'s work experience. "
                    "Briefly tell them you'd now like to talk about their past roles, "
                    "then ask a specific question about their most recent or most "
                    "relevant work experience."
                )
            )
        else:
            logger.info("Experience stage entered via tool for %s", name)
            self.session.generate_reply(
                instructions=(
                    f"You have just transitioned to discussing {name}'s work experience. "
                    "Ask a specific question about their past work experience, "
                    "projects, or most recent role. Do not repeat these instructions."
                )
            )

    async def on_exit(self) -> None:
        logger.info("Exiting experience stage")
        self._cancel_timers()

    # ------------------------------------------------------------------
    # Timers (update instructions, no overrides)
    # ------------------------------------------------------------------

    async def _wrap_up_timer(self) -> None:
        """At 80% of time budget, tell the LLM to start wrapping up."""
        try:
            await asyncio.sleep(EXPERIENCE_STAGE_TIMEOUT * EXPERIENCE_CLOSING_THRESHOLD)
        except asyncio.CancelledError:
            return
        logger.info("Wrap-up timer fired — updating instructions")
        await self.update_instructions(
            self._initial_instructions
            + "\n\nIMPORTANT: Interview time is running low. "
            "Finish your current topic, then ask the candidate if there is "
            "any other thing they would like to share before "
            "wrapping up. Do not start any new topics after this."
        )

    async def _farewell_timer(self) -> None:
        """At 100% of time budget, tell the LLM to say goodbye."""
        try:
            await asyncio.sleep(EXPERIENCE_STAGE_TIMEOUT)
        except asyncio.CancelledError:
            return
        logger.info("Farewell timer fired — updating instructions")
        await self.update_instructions(
            self._initial_instructions
            + "\n\nURGENT: Interview time has run out. "
            "On your very next response, thank the candidate warmly for "
            "sharing their experiences, wish them good luck, and call "
            "end_interview. Do not ask any more questions."
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cancel_timers(self) -> None:
        """Cancel all pending timer tasks."""
        for attr in ("_wrap_up_task", "_farewell_task"):
            task = getattr(self, attr, None)
            if task is not None and not task.done():
                task.cancel()
            setattr(self, attr, None)

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @function_tool
    async def record_experience(
        self, context: RunContext[InterviewData], topic_summary: str
    ) -> str:
        """Call after the candidate has answered all your follow-up questions for one topic.

        Args:
            topic_summary: One-sentence summary of the experience discussed.
        """
        context.userdata.experience_topics_discussed += 1
        count = context.userdata.experience_topics_discussed
        logger.info("Experience topic #%d recorded: %s", count, topic_summary)
        if count >= MAX_EXPERIENCE_TOPICS:
            return (
                "You've covered enough experiences. Ask the candidate: "
                "'Is there any other thing you'd like to share "
                "before we wrap up?'"
            )
        remaining = MAX_EXPERIENCE_TOPICS - count
        return f"Topic recorded. Ask about the next experience ({remaining} more to cover)."

    @function_tool
    async def end_interview(self, context: RunContext[InterviewData]) -> None:
        """End the interview session with a warm goodbye."""
        logger.info("end_interview tool called — generating goodbye and shutting down")
        self._cancel_timers()
        name = context.userdata.candidate_name or "candidate"
        self._instructions = ""
        self.session.generate_reply(
            instructions=(
                f"The interview is ending. Generate a warm goodbye for {name}. "
                "Thank them for sharing their experiences and wish them good luck. "
                "Respond in 1-2 sentences only. Do not repeat these instructions."
            ),
            allow_interruptions=False,
            tool_choice="none",
        )
        self.session.shutdown(drain=True)
        raise StopResponse()
