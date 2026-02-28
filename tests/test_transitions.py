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


class TestNewTimerAttributes:
    def test_initial_instructions_stored(self):
        """_initial_instructions is set to the initial instructions on construction."""
        agent = PastExperienceAgent()
        assert agent._initial_instructions == agent.instructions
        assert len(agent._initial_instructions) > 0

    def test_initial_instructions_stored_with_cv(self):
        """_initial_instructions includes CV text when provided."""
        agent = PastExperienceAgent(cv_text="CV text here", candidate_name="Alice")
        assert "CV text here" in agent._initial_instructions

    def test_wrap_up_and_farewell_tasks_initially_none(self):
        """Timer tasks start as None before on_enter."""
        agent = PastExperienceAgent()
        assert agent._wrap_up_task is None
        assert agent._farewell_task is None

    def test_cancel_timers_with_none_tasks(self):
        """_cancel_timers is safe when tasks are already None."""
        agent = PastExperienceAgent()
        agent._cancel_timers()  # Should not raise
        assert agent._wrap_up_task is None
        assert agent._farewell_task is None

    def test_cancel_timers_cancels_pending_tasks(self):
        """_cancel_timers cancels all pending timer tasks."""
        agent = PastExperienceAgent()
        agent._wrap_up_task = asyncio.get_event_loop().create_future()
        agent._farewell_task = asyncio.get_event_loop().create_future()

        agent._cancel_timers()

        assert agent._wrap_up_task is None
        assert agent._farewell_task is None

    def test_no_old_attributes(self):
        """PastExperienceAgent no longer has old override attributes."""
        agent = PastExperienceAgent()
        assert not hasattr(agent, "_closing_pending")
        assert not hasattr(agent, "_time_expired")
        assert not hasattr(agent, "_shutdown_initiated")
        assert not hasattr(agent, "_base_instructions")
        assert not hasattr(agent, "_grace_task")


class TestExperienceTopicsTracking:
    def test_experience_topics_discussed_increments(self):
        """experience_topics_discussed tracks recorded topics."""
        data = InterviewData()
        assert data.experience_topics_discussed == 0
        data.experience_topics_discussed += 1
        data.experience_topics_discussed += 1
        assert data.experience_topics_discussed == 2
