import asyncio
import logging
import time

from livekit.agents import Agent, ChatContext, RunContext, StopResponse
from livekit.agents.llm import ChatMessage, function_tool

from .config import (
    EXPERIENCE_CLOSING_THRESHOLD,
    EXPERIENCE_GRACE_PERIOD,
    EXPERIENCE_STAGE_TIMEOUT,
    INTRODUCTION_FALLBACK_TIMEOUT,
    MAX_EXPERIENCE_TOPICS,
    MAX_TURNS_PER_TOPIC,
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
    "When calling the tool, do NOT ask any questions about work experience — "
    "just briefly acknowledge what they shared. The next stage will ask the questions."
)

_EXPERIENCE_NO_CV = (
    "You are a professional interviewer conducting a mock interview. "
    "You are now in the past-experience stage. "
    "The candidate has already introduced themselves.\n\n"
    "Ask the candidate about their past work experience, projects, "
    "and professional achievements ONE topic at a time. "
    "Do NOT ask about education, degrees, certifications, or skills — "
    "focus ONLY on jobs, roles, and projects. "
    "Ask up to 2 follow-up questions to dig deeper "
    "into each experience, then call record_experience and move to the next one. "
    "Be conversational and encouraging.\n\n"
    "After you have fully explored one experience topic (asked your initial "
    "question and any follow-ups), call the record_experience tool with a brief "
    "summary before moving to the next topic.\n\n"
    "IMPORTANT: Do NOT call end_interview on your own initiative. "
    "The system will tell you when it is time to wrap up. "
    "When that happens, follow the system's instructions.\n"
    "When calling end_interview, your text response MUST be a warm goodbye "
    "thanking the candidate — do NOT ask any questions in the same message."
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
            "When calling the tool, do NOT ask any questions about work experience — "
            "just briefly acknowledge what they shared. The next stage will ask the questions.\n\n"
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
            "Select up to the most relevant or interesting ones to ask about. "
            "Ask about each experience ONE at a time with up to 2 follow-up questions "
            "to dig deeper into their contributions, challenges, and impact. "
            "Be conversational and encouraging.\n\n"
            "After you have fully explored one experience topic (asked your initial "
            "question and any follow-ups), call the record_experience tool with a brief "
            "summary before moving to the next topic.\n\n"
            "IMPORTANT: Do NOT call end_interview on your own initiative. "
            "The system will tell you when it is time to wrap up. "
            "When that happens, follow the system's instructions.\n"
            "When calling end_interview, your text response MUST be a warm goodbye "
            "thanking the candidate — do NOT ask any questions in the same message.\n\n"
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

    def _generate_override_reply(self, instructions: str, **kwargs) -> None:
        """Generate a reply using ONLY the given instructions, bypassing base instructions.

        The framework prepends ``self.instructions`` (base agent instructions)
        to the ``instructions`` parameter of ``generate_reply``.  For timer-
        based overrides the base instructions dominate and the LLM ignores the
        override.  This helper temporarily blanks the base instructions so that
        the LLM sees *only* the override text.

        ``generate_reply`` reads ``self.instructions`` synchronously at call
        time, so restoring immediately after is safe.
        """
        original = self._instructions
        self._instructions = ""
        try:
            self.session.generate_reply(instructions=instructions, **kwargs)
        finally:
            self._instructions = original

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        text = (new_message.text_content or "").strip().lower()

        if text == _END_INTERVIEW_TEXT:
            logger.info("User ended the interview via button")
            userdata: InterviewData = self.session.userdata
            name = userdata.candidate_name or "candidate"
            self._generate_override_reply(
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
        # Blank base instructions so the LLM sees ONLY the bridging directive
        # (otherwise the intro instructions dominate and produce a greeting).
        name = userdata.candidate_name or "there"
        original = self._instructions
        self._instructions = ""
        try:
            await self.session.generate_reply(
                instructions=(
                    f"Generate a brief transition message. Acknowledge what {name} has shared "
                    "and tell them you'd now like to discuss their work experience in more detail. "
                    "Respond in one sentence only. Do not repeat these instructions."
                ),
                allow_interruptions=False,
            )
        except asyncio.CancelledError:
            return  # Tool-based transition took over; abort fallback
        finally:
            self._instructions = original

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
        self._stage_start: float = 0.0
        self._closing_task: asyncio.Task[None] | None = None
        self._hard_stop_task: asyncio.Task[None] | None = None
        self._grace_task: asyncio.Task[None] | None = None
        self._time_expired: bool = False
        self._advance_pending: bool = False
        self._shutdown_initiated: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def on_enter(self) -> None:
        self._stage_start = time.monotonic()
        self._closing_task = asyncio.create_task(self._closing_transition())
        self._hard_stop_task = asyncio.create_task(self._hard_stop_transition())

        userdata: InterviewData = self.session.userdata
        name = userdata.candidate_name or "candidate"

        if userdata.transition_source == "fallback":
            logger.info("Experience stage entered via fallback for %s", name)
            self.session.generate_reply(
                instructions=(
                    f"The candidate {name} has already been told you're moving on to "
                    "discuss their work experience. Ask a specific question about their "
                    "past work experience or most recent role. Do NOT repeat that you're "
                    "transitioning -- just ask the question directly."
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

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        # Let the base class handle the "end interview" button first.
        await super().on_user_turn_completed(turn_ctx, new_message)

        text = (new_message.text_content or "").strip().lower()
        if text == _END_INTERVIEW_TEXT:
            return  # Already handled by super()

        userdata: InterviewData = self.session.userdata
        name = userdata.candidate_name or "candidate"

        # --- Hard stop: time expired, candidate just finished talking ---
        if self._time_expired:
            if self._shutdown_initiated:
                raise StopResponse()
            self._shutdown_initiated = True
            self._cancel_timers()
            logger.info("Time expired — wrapping up after candidate finished speaking")
            self._generate_override_reply(
                instructions=(
                    f"The interview time has ended. Generate a warm goodbye for {name}. "
                    "Thank them for sharing their experiences and wish them good luck. "
                    "Respond in 1-2 sentences only. Do not repeat these instructions."
                ),
                allow_interruptions=False,
                tool_choice="none",
            )
            self.session.shutdown(drain=True)
            raise StopResponse()

        # --- Deferred topic advance from previous turn ---
        # When the follow-up limit was reached on the PREVIOUS turn, we set a
        # flag and let the LLM finish its response naturally.  Now that the
        # candidate has responded, execute the advance.
        if self._advance_pending:
            self._advance_pending = False
            userdata.experience_topics_discussed += 1
            userdata.current_topic_turns = 0
            count = userdata.experience_topics_discussed
            logger.info(
                "Deferred advance — moving to topic #%d for %s",
                count + 1,
                name,
            )

            if not userdata.closing_question_asked and count >= MAX_EXPERIENCE_TOPICS:
                userdata.closing_question_asked = True
                self._cancel_task("_closing_task")
                self._generate_override_reply(
                    instructions=(
                        "You have covered enough experience topics. "
                        "Ask the candidate if there is any other meaningful experience "
                        "they would like to share before wrapping up. "
                        "Respond in 1-2 sentences only. Do not repeat these instructions."
                    ),
                )
            elif userdata.closing_question_asked:
                # Closing question already asked — wrap up the interview
                if self._shutdown_initiated:
                    raise StopResponse()
                self._shutdown_initiated = True
                logger.info("Closing already asked — ending interview for %s", name)
                self._generate_override_reply(
                    instructions=(
                        f"The interview is ending. Generate a warm goodbye for {name}. "
                        "Thank them for sharing their experiences and wish them good luck. "
                        "Respond in 1-2 sentences only. Do not repeat these instructions."
                    ),
                    allow_interruptions=False,
                    tool_choice="none",
                )
                self.session.shutdown(drain=True)
            else:
                remaining = MAX_EXPERIENCE_TOPICS - count
                self._generate_override_reply(
                    instructions=(
                        f"Briefly acknowledge what {name} just shared, then ask about "
                        f"their next work experience or role. "
                        f"You have {remaining} more experience(s) to cover. "
                        "Do not repeat these instructions."
                    ),
                )
            raise StopResponse()

        # --- Per-topic follow-up limit ---
        userdata.current_topic_turns += 1

        if userdata.current_topic_turns >= MAX_TURNS_PER_TOPIC:
            # Flag for deferred advance: let the current LLM reply play out
            # fully, then advance on the next candidate turn.
            logger.info(
                "Follow-up limit reached — will advance on next turn for %s",
                name,
            )
            self._advance_pending = True

    # ------------------------------------------------------------------
    # Timers
    # ------------------------------------------------------------------

    async def _closing_transition(self) -> None:
        """At 80 % of the time budget, ask the 'anything else?' question."""
        try:
            await asyncio.sleep(EXPERIENCE_STAGE_TIMEOUT * EXPERIENCE_CLOSING_THRESHOLD)
        except asyncio.CancelledError:
            return

        userdata: InterviewData = self.session.userdata
        if userdata.closing_question_asked:
            return  # Topic trigger already asked it

        userdata.closing_question_asked = True
        logger.info("Closing timer fired — asking closing question")
        await self.session.interrupt()
        self._generate_override_reply(
            instructions=(
                "The interview time is almost up. "
                "Ask the candidate if there is any other meaningful experience "
                "they would like to share before wrapping up. "
                "Respond in 1-2 sentences only. Do not repeat these instructions."
            ),
        )

    async def _hard_stop_transition(self) -> None:
        """At 100 % of the time budget, flag time-expired and start grace period."""
        try:
            await asyncio.sleep(EXPERIENCE_STAGE_TIMEOUT)
        except asyncio.CancelledError:
            return

        logger.info("Experience stage timeout — waiting for candidate to finish")
        self._time_expired = True
        self._grace_task = asyncio.create_task(self._grace_expired())

    async def _grace_expired(self) -> None:
        """If the candidate is still talking after the grace period, interrupt."""
        try:
            await asyncio.sleep(EXPERIENCE_GRACE_PERIOD)
        except asyncio.CancelledError:
            return

        userdata: InterviewData = self.session.userdata
        name = userdata.candidate_name or "candidate"
        logger.info("Grace period expired — interrupting politely")

        try:
            await self.session.interrupt()
        except asyncio.CancelledError:
            return

        if self._shutdown_initiated:
            return
        self._shutdown_initiated = True

        self._generate_override_reply(
            instructions=(
                f"The interview time has run out. Generate a warm goodbye for {name}. "
                "Apologize briefly for the interruption, thank them for sharing their "
                "experiences, and wish them good luck. "
                "Respond in 1-2 sentences only. Do not repeat these instructions."
            ),
            allow_interruptions=False,
            tool_choice="none",
        )
        self.session.shutdown(drain=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cancel_task(self, attr: str) -> None:
        """Cancel a single timer task by attribute name."""
        task: asyncio.Task[None] | None = getattr(self, attr, None)
        if task is not None and not task.done():
            task.cancel()
        setattr(self, attr, None)

    def _cancel_timers(self) -> None:
        """Cancel all pending timer tasks."""
        for attr in ("_closing_task", "_hard_stop_task", "_grace_task"):
            self._cancel_task(attr)

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @function_tool
    async def record_experience(
        self, context: RunContext[InterviewData], topic_summary: str
    ) -> str:
        """Call this after you have finished exploring one experience topic
        (initial question + any follow-ups). Do NOT call this mid-discussion.

        Args:
            topic_summary: One-sentence summary of the experience discussed.
        """
        context.userdata.experience_topics_discussed += 1
        context.userdata.current_topic_turns = 0
        self._advance_pending = False  # LLM advanced naturally; cancel deferred advance
        count = context.userdata.experience_topics_discussed
        logger.info("Experience topic #%d recorded: %s", count, topic_summary)

        if (
            not context.userdata.closing_question_asked
            and count >= MAX_EXPERIENCE_TOPICS
        ):
            context.userdata.closing_question_asked = True
            self._cancel_task("_closing_task")
            return (
                "You've covered enough experiences. Now ask the candidate: "
                "'Besides what we've discussed, is there any other meaningful "
                "experience you'd like to share before we wrap up?'"
            )
        remaining = MAX_EXPERIENCE_TOPICS - count
        return f"Noted. Ask about the next experience ({remaining} more to cover)."

    @function_tool
    async def end_interview(self, context: RunContext[InterviewData]) -> None:
        """Called AFTER you have thanked the candidate warmly in your text response.
        This tool closes the interview session."""
        logger.info("end_interview tool called — shutting down session")
        self._shutdown_initiated = True
        self._cancel_timers()
        self.session.shutdown(drain=True)
        raise StopResponse()
