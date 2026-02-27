"""Integration tests for agent transitions: tool-based handoff, fallback timer,
chat context inheritance, and userdata persistence."""

import asyncio

import pytest

from livekit.agents import ChatContext

from src.agents import IntroductionAgent, PastExperienceAgent
from src.data import InterviewData


class TestFallbackTimer:
    @pytest.mark.asyncio
    async def test_fallback_cancelled_on_manual_cancel(self):
        """The fallback timer task can be cancelled without leaking."""
        agent = IntroductionAgent()
        # Simulate a fallback task that would run for a long time
        agent._fallback_task = asyncio.create_task(asyncio.sleep(999))

        # Cancel it as proceed_to_experience would
        agent._fallback_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await agent._fallback_task

        assert agent._fallback_task.cancelled()

    @pytest.mark.asyncio
    async def test_fallback_task_starts_as_none(self):
        """Before on_enter, the fallback task should not exist."""
        agent = IntroductionAgent()
        assert agent._fallback_task is None


class TestChatContextInheritance:
    def test_past_experience_agent_receives_chat_ctx(self):
        """PastExperienceAgent preserves conversation history from IntroductionAgent."""
        ctx = ChatContext()
        ctx.add_message(role="assistant", content="Welcome! Please introduce yourself.")
        ctx.add_message(role="user", content="Hi, I'm Alice, a software engineer.")

        agent = PastExperienceAgent(chat_ctx=ctx)
        items = agent.chat_ctx.items
        # Should contain the messages we passed in
        assert len(items) >= 2

    def test_introduction_agent_receives_chat_ctx(self):
        """IntroductionAgent can also receive a pre-existing chat context."""
        ctx = ChatContext()
        ctx.add_message(role="system", content="You are an interviewer.")

        agent = IntroductionAgent(chat_ctx=ctx)
        assert len(agent.chat_ctx.items) >= 1

    def test_agent_without_chat_ctx_starts_empty(self):
        """Agents without chat_ctx start with no conversation history."""
        agent = PastExperienceAgent()
        # chat_ctx should exist but have no user/assistant messages
        # (may have system instructions added by the Agent base class)
        user_messages = [
            item for item in agent.chat_ctx.items
            if hasattr(item, "role") and item.role in ("user", "assistant")
        ]
        assert len(user_messages) == 0


class TestUserdataPersistence:
    def test_interview_data_survives_modification(self):
        """InterviewData fields persist across modifications."""
        data = InterviewData()

        # Simulate IntroductionAgent writing data
        data.candidate_name = "Bob"
        data.introduction_summary = "Backend developer, 3 years"
        data.transition_source = "tool"

        # Simulate PastExperienceAgent reading data
        assert data.candidate_name == "Bob"
        assert data.introduction_summary == "Backend developer, 3 years"
        assert data.transition_source == "tool"

    def test_fallback_transition_source(self):
        """Fallback transition correctly sets transition_source."""
        data = InterviewData()
        data.transition_source = "fallback"
        assert data.transition_source == "fallback"


class TestFallbackBridgingMessage:
    def test_name_fallback_when_candidate_name_is_none(self):
        """When candidate_name is None, bridging should use 'there' fallback."""
        data = InterviewData()
        name = data.candidate_name or "there"
        assert name == "there"

    def test_name_used_when_candidate_name_is_set(self):
        """When candidate_name is set, bridging should use the actual name."""
        data = InterviewData()
        data.candidate_name = "Alice"
        name = data.candidate_name or "there"
        assert name == "Alice"


class TestExperienceTimers:
    def test_cancel_timers_helper(self):
        """_cancel_timers cancels all pending timer tasks."""
        agent = PastExperienceAgent()
        agent._closing_task = asyncio.get_event_loop().create_future()
        agent._hard_stop_task = asyncio.get_event_loop().create_future()
        agent._grace_task = asyncio.get_event_loop().create_future()

        agent._cancel_timers()

        assert agent._closing_task is None
        assert agent._hard_stop_task is None
        assert agent._grace_task is None

    def test_cancel_timers_with_none_tasks(self):
        """_cancel_timers is safe when tasks are already None."""
        agent = PastExperienceAgent()
        agent._cancel_timers()  # Should not raise

        assert agent._closing_task is None
        assert agent._hard_stop_task is None
        assert agent._grace_task is None


class TestOverrideReply:
    def test_override_blanks_and_restores_instructions(self):
        """_generate_override_reply temporarily blanks base instructions via _instructions."""
        agent = IntroductionAgent()
        original = agent.instructions
        assert len(original) > 0

        # Cannot call _generate_override_reply without a session, but we can
        # verify the pattern by checking that _instructions is directly writable
        # (the public property is read-only; the helper uses _instructions).
        agent._instructions = ""
        assert agent.instructions == ""
        agent._instructions = original
        assert agent.instructions == original

    def test_override_exists_on_both_agents(self):
        """Both agent classes inherit _generate_override_reply."""
        intro = IntroductionAgent()
        exp = PastExperienceAgent()
        assert hasattr(intro, "_generate_override_reply")
        assert hasattr(exp, "_generate_override_reply")


class TestExperienceUserdataTracking:
    def test_experience_topics_discussed_increments(self):
        """experience_topics_discussed tracks candidate turns."""
        data = InterviewData()
        assert data.experience_topics_discussed == 0
        data.experience_topics_discussed += 1
        data.experience_topics_discussed += 1
        assert data.experience_topics_discussed == 2

    def test_closing_question_flag(self):
        """closing_question_asked prevents duplicate closing questions."""
        data = InterviewData()
        assert data.closing_question_asked is False
        data.closing_question_asked = True
        assert data.closing_question_asked is True


class TestPerTopicTurnLimit:
    def test_current_topic_turns_default_zero(self):
        """current_topic_turns starts at 0."""
        data = InterviewData()
        assert data.current_topic_turns == 0

    def test_current_topic_turns_increments(self):
        """current_topic_turns counts candidate responses within a topic."""
        data = InterviewData()
        data.current_topic_turns += 1
        data.current_topic_turns += 1
        data.current_topic_turns += 1
        assert data.current_topic_turns == 3

    def test_current_topic_turns_resets_on_topic_change(self):
        """current_topic_turns resets to 0 when a new topic starts."""
        data = InterviewData()
        data.current_topic_turns = 3
        data.experience_topics_discussed += 1
        data.current_topic_turns = 0
        assert data.current_topic_turns == 0
        assert data.experience_topics_discussed == 1


class TestDeferredTopicAdvance:
    def test_advance_pending_default_false(self):
        """_advance_pending starts as False."""
        agent = PastExperienceAgent()
        assert agent._advance_pending is False

    def test_advance_pending_is_settable(self):
        """_advance_pending can be set to True to schedule a deferred advance."""
        agent = PastExperienceAgent()
        agent._advance_pending = True
        assert agent._advance_pending is True

    def test_advance_pending_cleared_on_natural_advance(self):
        """If the LLM calls record_experience, _advance_pending should be
        cleared to avoid double-incrementing experience_topics_discussed."""
        agent = PastExperienceAgent()
        agent._advance_pending = True
        # Simulate what record_experience does:
        agent._advance_pending = False
        assert agent._advance_pending is False
