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
    _matches_keywords,
)
from src.config import MAX_COMPLETION_TOKENS, PAUSE_KEYWORDS, RESUME_KEYWORDS, STOP_KEYWORDS
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

    def test_is_paused_defaults_to_false(self):
        data = InterviewData()
        assert data.is_paused is False

    def test_fields_are_settable(self):
        data = InterviewData()
        data.candidate_name = "Alice"
        data.introduction_summary = "Software engineer with 5 years experience"
        data.transition_source = "tool"
        assert data.candidate_name == "Alice"
        assert data.introduction_summary == "Software engineer with 5 years experience"
        assert data.transition_source == "tool"

    def test_pause_state_is_settable(self):
        data = InterviewData()
        data.is_paused = True
        assert data.is_paused is True


class TestKeywordMatching:
    @pytest.mark.parametrize("text", ["stop", "Stop", "STOP", "  stop  "])
    def test_stop_keywords_match(self, text: str):
        assert _matches_keywords(text, STOP_KEYWORDS)

    @pytest.mark.parametrize("text", ["quit", "end interview", "exit"])
    def test_other_stop_keywords(self, text: str):
        assert _matches_keywords(text, STOP_KEYWORDS)

    @pytest.mark.parametrize("text", ["pause", "wait", "hold on", "one moment"])
    def test_pause_keywords_match(self, text: str):
        assert _matches_keywords(text, PAUSE_KEYWORDS)

    @pytest.mark.parametrize("text", ["resume", "continue", "go on", "go ahead", "i'm ready"])
    def test_resume_keywords_match(self, text: str):
        assert _matches_keywords(text, RESUME_KEYWORDS)

    def test_normal_text_does_not_match_stop(self):
        assert not _matches_keywords("I worked at Google for 3 years", STOP_KEYWORDS)

    def test_normal_text_does_not_match_pause(self):
        assert not _matches_keywords("My background is in software engineering", PAUSE_KEYWORDS)

    def test_empty_text_does_not_match(self):
        assert not _matches_keywords("", STOP_KEYWORDS)

    def test_substring_match(self):
        assert _matches_keywords("please wait for a moment", PAUSE_KEYWORDS)

    def test_case_insensitive_substring(self):
        assert _matches_keywords("Can you Hold On please?", PAUSE_KEYWORDS)


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
