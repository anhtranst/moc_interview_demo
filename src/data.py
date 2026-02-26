from dataclasses import dataclass


@dataclass
class InterviewData:
    """Shared state that persists across all interview agents via AgentSession.userdata."""

    interview_code: str | None = None
    started_at: float | None = None
    candidate_name: str | None = None
    introduction_summary: str | None = None
    transition_source: str | None = None  # "tool" or "fallback"
