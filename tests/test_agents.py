"""Unit tests for agent construction, instructions, properties, and flow control."""

import pytest

from livekit.agents import ChatContext

from src.agents import (
    CONVERSATION_RULES,
    EXPERIENCE_INSTRUCTIONS,
    INTRODUCTION_INSTRUCTIONS,
    InterviewAgentBase,
    IntroductionAgent,
    PastExperienceAgent,
    _END_INTERVIEW_TEXT,
)
from src.config import MAX_COMPLETION_TOKENS, MAX_ENDPOINTING_DELAY, MIN_ENDPOINTING_DELAY
from src.data import InterviewData


class TestIntroductionAgent:
    def test_instructions_mention_self_introduction(self):
        agent = IntroductionAgent()
        assert "self-introduction" in agent.instructions.lower()

    def test_instructions_are_correct(self):
        agent = IntroductionAgent()
        assert agent.instructions == INTRODUCTION_INSTRUCTIONS

    def test_instructions_include_conversation_rules(self):
        agent = IntroductionAgent()
        assert "1-3 sentences" in agent.instructions

    def test_has_proceed_tool(self):
        agent = IntroductionAgent()
        tool_ids = [t.id for t in agent.tools]
        assert "proceed_to_experience" in tool_ids

    def test_accepts_chat_ctx(self):
        ctx = ChatContext()
        ctx.add_message(role="user", content="Hello")
        agent = IntroductionAgent(chat_ctx=ctx)
        assert agent.chat_ctx is not None

    def test_fallback_task_initially_none(self):
        agent = IntroductionAgent()
        assert agent._fallback_task is None

    def test_instructions_enforce_one_detail_per_question(self):
        agent = IntroductionAgent()
        assert "one detail at a time" in agent.instructions.lower()

    def test_instructions_mention_sequential_details(self):
        agent = IntroductionAgent()
        instructions_lower = agent.instructions.lower()
        assert "name" in instructions_lower
        assert "current role" in instructions_lower
        assert "background" in instructions_lower
        # Verify the sequence order: name before role before background
        name_pos = instructions_lower.index("ask for their name")
        role_pos = instructions_lower.index("current role")
        background_pos = instructions_lower.index("background or education")
        assert name_pos < role_pos < background_pos

    def test_inherits_from_interview_agent_base(self):
        agent = IntroductionAgent()
        assert isinstance(agent, InterviewAgentBase)


class TestPastExperienceAgent:
    def test_instructions_mention_experience(self):
        agent = PastExperienceAgent()
        assert "experience" in agent.instructions.lower()

    def test_instructions_are_correct(self):
        agent = PastExperienceAgent()
        assert agent.instructions == EXPERIENCE_INSTRUCTIONS

    def test_instructions_include_conversation_rules(self):
        agent = PastExperienceAgent()
        assert "1-3 sentences" in agent.instructions

    def test_has_end_interview_tool(self):
        agent = PastExperienceAgent()
        tool_ids = [t.id for t in agent.tools]
        assert "end_interview" in tool_ids

    def test_accepts_chat_ctx(self):
        ctx = ChatContext()
        ctx.add_message(role="assistant", content="Welcome!")
        ctx.add_message(role="user", content="Hi, I'm Alice.")
        agent = PastExperienceAgent(chat_ctx=ctx)
        assert agent.chat_ctx is not None

    def test_inherits_from_interview_agent_base(self):
        agent = PastExperienceAgent()
        assert isinstance(agent, InterviewAgentBase)


class TestInterviewData:
    def test_defaults_are_none(self):
        data = InterviewData()
        assert data.candidate_name is None
        assert data.introduction_summary is None
        assert data.transition_source is None

    def test_fields_are_settable(self):
        data = InterviewData()
        data.candidate_name = "Alice"
        data.introduction_summary = "Software engineer with 5 years experience"
        data.transition_source = "tool"
        assert data.candidate_name == "Alice"
        assert data.introduction_summary == "Software engineer with 5 years experience"
        assert data.transition_source == "tool"


class TestEndInterviewText:
    def test_end_interview_text_is_lowercase(self):
        assert _END_INTERVIEW_TEXT == _END_INTERVIEW_TEXT.lower()

    def test_end_interview_text_value(self):
        assert _END_INTERVIEW_TEXT == "end interview"


class TestConversationRules:
    def test_rules_mention_brevity(self):
        assert "1-3 sentences" in CONVERSATION_RULES

    def test_rules_mention_single_question(self):
        assert "one question at a time" in CONVERSATION_RULES

    def test_rules_appended_to_introduction(self):
        assert INTRODUCTION_INSTRUCTIONS.endswith(CONVERSATION_RULES)

    def test_rules_appended_to_experience(self):
        assert EXPERIENCE_INSTRUCTIONS.endswith(CONVERSATION_RULES)


class TestConfig:
    def test_max_completion_tokens_is_reasonable(self):
        assert 50 <= MAX_COMPLETION_TOKENS <= 500

    def test_endpointing_delays_are_reasonable(self):
        assert 1.0 <= MIN_ENDPOINTING_DELAY <= 5.0
        assert MAX_ENDPOINTING_DELAY > MIN_ENDPOINTING_DELAY


class TestEntrypointConfig:
    def test_google_stt_can_be_imported(self):
        """Verify google.STT is available for voice mode."""
        from livekit.plugins.google import STT

        assert STT is not None

    def test_room_input_options_accept_both(self):
        """Server should accept both text and audio input."""
        from livekit.agents import RoomInputOptions

        opts = RoomInputOptions(text_enabled=True, audio_enabled=True)
        assert opts.text_enabled is True
        assert opts.audio_enabled is True
