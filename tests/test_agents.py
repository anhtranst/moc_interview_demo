"""Unit tests for agent construction, instructions, and properties."""

from livekit.agents import ChatContext

from src.agents import (
    EXPERIENCE_INSTRUCTIONS,
    INTRODUCTION_INSTRUCTIONS,
    IntroductionAgent,
    PastExperienceAgent,
)
from src.data import InterviewData


class TestIntroductionAgent:
    def test_instructions_mention_self_introduction(self):
        agent = IntroductionAgent()
        assert "self-introduction" in agent.instructions.lower()

    def test_instructions_are_correct(self):
        agent = IntroductionAgent()
        assert agent.instructions == INTRODUCTION_INSTRUCTIONS

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


class TestPastExperienceAgent:
    def test_instructions_mention_experience(self):
        agent = PastExperienceAgent()
        assert "experience" in agent.instructions.lower()

    def test_instructions_are_correct(self):
        agent = PastExperienceAgent()
        assert agent.instructions == EXPERIENCE_INSTRUCTIONS

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
