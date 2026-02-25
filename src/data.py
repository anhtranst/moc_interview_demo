from dataclasses import dataclass


@dataclass
class InterviewData:
    """Shared state that persists across all interview agents via AgentSession.userdata."""

    candidate_name: str | None = None
    introduction_summary: str | None = None
    transition_source: str | None = None  # "tool" or "fallback"
    is_paused: bool = False
